#!/usr/bin/env python3
"""
Worker Manager for ONM Phrase Crawling System

Manages distributed crawling of phrases across multiple workers.
Each worker claims phrases from the database and processes them.
"""

import os
import sys
import time
import uuid
import signal
import asyncio
import logging
import argparse
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess

from config.settings import (
    PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD, PHRASES_TABLE
)

class WorkerManager:
    """Manages a single worker process for phrase crawling."""
    
    def __init__(self, worker_id: str, server_id: str, batch_size: int = 10, 
                 timeout_minutes: int = 30):
        self.worker_id = worker_id
        self.server_id = server_id
        self.batch_size = batch_size
        self.timeout_minutes = timeout_minutes
        self.is_running = False
        self.db_connection = None
        
        # Setup logging
        self.setup_logging()
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
    def setup_logging(self):
        """Setup logging for the worker."""
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s [Worker-{self.worker_id}] %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f'/var/log/crawler/worker_{self.worker_id}.log')
            ]
        )
        self.logger = logging.getLogger(f'worker_{self.worker_id}')
        
    def get_db_connection(self):
        """Get database connection."""
        if self.db_connection is None or self.db_connection.closed:
            self.db_connection = psycopg2.connect(
                host=PG_HOST,
                database=PG_DATABASE,
                user=PG_USER,
                password=PG_PASSWORD,
                cursor_factory=RealDictCursor
            )
        return self.db_connection
        
    def claim_phrases(self) -> List[Dict[str, Any]]:
        """Claim phrases for processing."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM claim_phrases_for_worker(%s, %s, %s)",
                    (self.worker_id, self.batch_size, self.timeout_minutes)
                )
                phrases = cursor.fetchall()
                conn.commit()
                return [dict(phrase) for phrase in phrases]
        except Exception as e:
            self.logger.error(f"Error claiming phrases: {e}")
            return []
            
    def complete_phrase(self, phrase_id: int) -> bool:
        """Mark phrase as completed."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT complete_phrase(%s, %s)",
                    (phrase_id, self.worker_id)
                )
                result = cursor.fetchone()
                conn.commit()
                return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error completing phrase {phrase_id}: {e}")
            return False
            
    def fail_phrase(self, phrase_id: int) -> bool:
        """Mark phrase as failed."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE onm_phrases 
                    SET status = 'failed',
                        crawl_attempts = crawl_attempts + 1,
                        assigned_worker_id = NULL,
                        assigned_at = NULL,
                        processing_timeout = NULL,
                        modified_at = now()
                    WHERE id = %s AND assigned_worker_id = %s
                """, (phrase_id, self.worker_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error failing phrase {phrase_id}: {e}")
            return False
            
    def run_spider(self, phrases: List[str], spider_type: str = 'google') -> bool:
        """Run spider for given phrases."""
        try:
            phrases_str = ','.join(phrases)
            cmd = [
                'scrapy', 'crawl', spider_type,
                '-a', f'phrases={phrases_str}',
                '-a', f'worker_id={self.worker_id}',
                '-a', 'page_request=1',
                '--nolog'  # Suppress scrapy logs to avoid conflicts
            ]
            
            self.logger.info(f"Starting spider for {len(phrases)} phrases")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.logger.info(f"Spider completed successfully for {len(phrases)} phrases")
                return True
            else:
                self.logger.error(f"Spider failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Spider timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error running spider: {e}")
            return False
            
    def process_batch(self):
        """Process a batch of phrases."""
        phrases = self.claim_phrases()
        
        if not phrases:
            self.logger.debug("No phrases available for processing")
            return 0
            
        self.logger.info(f"Processing batch of {len(phrases)} phrases")
        
        # Extract phrase texts for processing
        phrase_texts = [p['phrases'] for p in phrases]
        
        # Run spider with this batch
        success = self.run_spider(phrase_texts)
        
        # Update phrase status based on results
        processed_count = 0
        for phrase in phrases:
            if success:
                if self.complete_phrase(phrase['id']):
                    processed_count += 1
                    self.logger.debug(f"Completed phrase: {phrase['phrases']}")
            else:
                self.fail_phrase(phrase['id'])
                self.logger.warning(f"Failed phrase: {phrase['phrases']}")
                
        self.logger.info(f"Processed {processed_count}/{len(phrases)} phrases successfully")
        return processed_count
        
    def run_continuous(self, check_interval: int = 30):
        """Run worker continuously."""
        self.is_running = True
        self.logger.info(f"Worker started - Server: {self.server_id}, Batch size: {self.batch_size}")
        
        while self.is_running:
            try:
                processed = self.process_batch()
                
                if processed == 0:
                    # No work available, wait longer
                    time.sleep(check_interval)
                else:
                    # Work was processed, check immediately for more
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(check_interval)
                
        self.logger.info("Worker stopped")
        
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False


class ServerManager:
    """Manages multiple workers on a single server."""
    
    def __init__(self, server_id: str, num_workers: int = 3):
        self.server_id = server_id
        self.num_workers = num_workers
        self.workers = []
        self.worker_threads = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s [Server-{server_id}] %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(f'server_{server_id}')
        
    def start_workers(self):
        """Start all workers on this server."""
        for i in range(self.num_workers):
            worker_id = f"{self.server_id}-{i+1}"
            worker = WorkerManager(worker_id, self.server_id)
            self.workers.append(worker)
            
            # Start worker in separate thread
            thread = threading.Thread(
                target=worker.run_continuous,
                name=f"Worker-{worker_id}"
            )
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)
            
            self.logger.info(f"Started worker {worker_id}")
            
        self.logger.info(f"All {self.num_workers} workers started")
        
    def stop_workers(self):
        """Stop all workers."""
        for worker in self.workers:
            worker.is_running = False
            
        # Wait for threads to finish
        for thread in self.worker_threads:
            thread.join(timeout=30)
            
        self.logger.info("All workers stopped")
        
    def run(self):
        """Run the server manager."""
        try:
            self.start_workers()
            
            # Keep main thread alive
            while True:
                time.sleep(60)
                # Log status every minute
                active_workers = sum(1 for w in self.workers if w.is_running)
                self.logger.info(f"Status: {active_workers}/{self.num_workers} workers running")
                
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop_workers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ONM Phrase Crawler Worker Manager')
    parser.add_argument('--server-id', required=True, help='Server identifier (1-4)')
    parser.add_argument('--workers', type=int, default=3, help='Number of workers per server')
    parser.add_argument('--mode', choices=['server', 'worker'], default='server',
                       help='Run as server manager or single worker')
    parser.add_argument('--worker-id', help='Worker ID for single worker mode')
    
    args = parser.parse_args()
    
    if args.mode == 'server':
        manager = ServerManager(args.server_id, args.workers)
        manager.run()
    else:
        if not args.worker_id:
            print("Worker ID required for worker mode")
            sys.exit(1)
        worker = WorkerManager(args.worker_id, args.server_id)
        worker.run_continuous()