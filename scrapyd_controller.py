#!/usr/bin/env python3
"""
Scrapyd Controller for ONM Phrase Crawling

Manages distributed phrase crawling across multiple Scrapyd instances.
"""

import time
import uuid
import json
import logging
import requests
import schedule
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from psycopg2.extras import RealDictCursor

from config.settings import PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD, PG_PORT

class ScrapydController:
    """Controls multiple Scrapyd instances for distributed crawling."""
    
    def __init__(self, scrapyd_servers: List[str]):
        """
        Initialize controller with Scrapyd server URLs.
        
        Args:
            scrapyd_servers: List of Scrapyd server URLs (e.g., ['http://server1:6800', ...])
        """
        self.scrapyd_servers = scrapyd_servers
        self.project_name = 'crawler'
        self.spider_name = 'google'  # or 'bing'
        self.setup_logging()
        
        # Job tracking
        self.active_jobs = {}  # {job_id: {server, phrases, started_at}}
        self.server_loads = {server: 0 for server in scrapyd_servers}
        
    def setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [ScrapydController] %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/var/log/crawler/scrapyd_controller.log')
            ]
        )
        self.logger = logging.getLogger('scrapyd_controller')
        
    def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD,
            cursor_factory=RealDictCursor
        )
        
    def claim_phrases_batch(self, batch_size: int = 50) -> List[Dict]:
        """Claim a batch of phrases for processing."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                worker_id = str(uuid.uuid4())
                cursor.execute(
                    "SELECT * FROM claim_phrases_for_worker(%s, %s, %s)",
                    (worker_id, batch_size, 30)  # 30 minute timeout
                )
                phrases = cursor.fetchall()
                conn.commit()
                return [dict(phrase) for phrase in phrases]
        except Exception as e:
            self.logger.error(f"Error claiming phrases: {e}")
            return []
            
    def get_least_loaded_server(self) -> Optional[str]:
        """Get the Scrapyd server with lowest load."""
        if not self.server_loads:
            return None
        return min(self.server_loads.keys(), key=lambda k: self.server_loads[k])
        
    def schedule_spider_job(self, server: str, phrases: List[str], 
                           job_id: Optional[str] = None) -> Optional[str]:
        """Schedule a spider job on a Scrapyd server."""
        if not job_id:
            job_id = str(uuid.uuid4())
            
        try:
            phrases_str = ','.join(phrases)
            
            response = requests.post(f"{server}/schedule.json", data={
                'project': self.project_name,
                'spider': self.spider_name,
                'jobid': job_id,
                'phrases': phrases_str,
                'page_request': '1',
                'worker_id': job_id  # Use job_id as worker_id for tracking
            })
            
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'ok':
                    self.active_jobs[job_id] = {
                        'server': server,
                        'phrases': phrases,
                        'started_at': datetime.now(),
                        'phrase_count': len(phrases)
                    }
                    self.server_loads[server] += 1
                    self.logger.info(f"Scheduled job {job_id} on {server} with {len(phrases)} phrases")
                    return job_id
                else:
                    self.logger.error(f"Failed to schedule job: {result}")
            else:
                self.logger.error(f"HTTP error scheduling job: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error scheduling job on {server}: {e}")
            
        return None
        
    def check_job_status(self, server: str, job_id: str) -> str:
        """Check job status on Scrapyd server."""
        try:
            response = requests.get(f"{server}/listjobs.json", params={
                'project': self.project_name
            })
            
            if response.status_code == 200:
                jobs = response.json()
                
                # Check in running jobs
                for job in jobs.get('running', []):
                    if job['id'] == job_id:
                        return 'running'
                        
                # Check in finished jobs
                for job in jobs.get('finished', []):
                    if job['id'] == job_id:
                        return 'finished'
                        
                # Check in pending jobs
                for job in jobs.get('pending', []):
                    if job['id'] == job_id:
                        return 'pending'
                        
                return 'unknown'
                
        except Exception as e:
            self.logger.error(f"Error checking job status: {e}")
            return 'error'
            
    def monitor_jobs(self):
        """Monitor and cleanup completed jobs."""
        completed_jobs = []
        
        for job_id, job_info in self.active_jobs.items():
            server = job_info['server']
            status = self.check_job_status(server, job_id)
            
            if status in ['finished', 'unknown']:
                completed_jobs.append(job_id)
                self.server_loads[server] = max(0, self.server_loads[server] - 1)
                
                duration = datetime.now() - job_info['started_at']
                self.logger.info(f"Job {job_id} completed in {duration.total_seconds():.1f}s "
                               f"({job_info['phrase_count']} phrases)")
                               
        # Remove completed jobs
        for job_id in completed_jobs:
            del self.active_jobs[job_id]
            
        if completed_jobs:
            self.logger.info(f"Cleaned up {len(completed_jobs)} completed jobs")
            
    def process_phrase_batches(self):
        """Process available phrase batches."""
        # Monitor existing jobs first
        self.monitor_jobs()
        
        # Check if we can schedule more jobs
        total_active_jobs = len(self.active_jobs)
        max_concurrent_jobs = len(self.scrapyd_servers) * 4  # 4 jobs per server max
        
        if total_active_jobs >= max_concurrent_jobs:
            self.logger.debug(f"Max concurrent jobs reached: {total_active_jobs}")
            return
            
        # Get phrases to process
        batch_size = 30  # Smaller batches for better distribution
        phrases_data = self.claim_phrases_batch(batch_size)
        
        if not phrases_data:
            self.logger.debug("No phrases available for processing")
            return
            
        # Extract phrase texts
        phrases = [p['phrase_text'] for p in phrases_data]
        
        # Get least loaded server
        server = self.get_least_loaded_server()
        if not server:
            self.logger.error("No available servers")
            return
            
        # Schedule the job
        job_id = self.schedule_spider_job(server, phrases)
        if job_id:
            self.logger.info(f"Scheduled batch of {len(phrases)} phrases on {server}")
        else:
            self.logger.error("Failed to schedule job")
            
    def activate_hourly_phrases(self):
        """Activate phrases for hourly crawling."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Reset stuck processing phrases
                cursor.execute("""
                    UPDATE onm_phrases 
                    SET status = 'active',
                        assigned_worker_id = NULL,
                        assigned_at = NULL,
                        processing_timeout = NULL,
                        modified_at = now()
                    WHERE status = 'processing' 
                    AND processing_timeout < now() - INTERVAL '1 hour'
                """)
                
                # Activate phrases for crawling
                cursor.execute("""
                    UPDATE onm_phrases 
                    SET status = 'active',
                        modified_at = now()
                    WHERE (
                        last_crawled_at IS NULL 
                        OR last_crawled_at < now() - INTERVAL '1 hour'
                    )
                    AND status IN ('inactive', 'completed', 'failed')
                    AND crawl_attempts < max_retries
                """)
                
                activated_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Activated {activated_count} phrases for crawling")
                return activated_count
                
        except Exception as e:
            self.logger.error(f"Error activating phrases: {e}")
            return 0
            
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT status, COUNT(*) FROM onm_phrases GROUP BY status")
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                cursor.execute("""
                    SELECT COUNT(*) FROM onm_phrases 
                    WHERE last_crawled_at > now() - INTERVAL '1 hour'
                """)
                completed_last_hour = cursor.fetchone()[0]
                
                return {
                    'phrase_status': status_counts,
                    'completed_last_hour': completed_last_hour,
                    'active_jobs': len(self.active_jobs),
                    'server_loads': self.server_loads.copy()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}
            
    def run_continuous(self):
        """Run the controller continuously."""
        self.logger.info(f"Scrapyd Controller started with servers: {self.scrapyd_servers}")
        
        # Schedule hourly phrase activation
        schedule.every().hour.at(":00").do(self.activate_hourly_phrases)
        
        # Initial activation
        self.activate_hourly_phrases()
        
        while True:
            try:
                # Run scheduled tasks
                schedule.run_pending()
                
                # Process phrase batches
                self.process_phrase_batches()
                
                # Log stats every 5 minutes
                if int(time.time()) % 300 == 0:
                    stats = self.get_system_stats()
                    self.logger.info(f"System stats: {json.dumps(stats, indent=2)}")
                
                time.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                self.logger.info("Controller stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(30)


if __name__ == "__main__":
    # Configure your Scrapyd servers
    scrapyd_servers = [
        'http://10.130.137.101:6800',  # Server 1
        'http://10.130.137.99:6800',   # Server 2  
        'http://10.130.137.100:6800',  # Server 3
        'http://195.35.22.151:6800'    # Server 4
    ]
    
    controller = ScrapydController(scrapyd_servers)
    controller.run_continuous()