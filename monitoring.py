#!/usr/bin/env python3
"""
Monitoring system for ONM Crawler

Provides health checks and performance monitoring.
"""

import time
import json
import logging
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from typing import Dict, Any

from config.settings import PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD, PG_PORT

class CrawlerMonitor:
    """Monitor crawler system health and performance."""
    
    def __init__(self):
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [Monitor] %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/var/log/crawler/monitor.log')
            ]
        )
        self.logger = logging.getLogger('monitor')
        
    def get_db_connection(self):
        return psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD,
            cursor_factory=RealDictCursor
        )
        
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                stats = {}
                
                # Overall phrase status
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM onm_phrases 
                    GROUP BY status
                """)
                stats['phrase_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Hourly completion rate
                cursor.execute("""
                    SELECT COUNT(*) as completed_last_hour
                    FROM onm_phrases 
                    WHERE last_crawled_at > now() - INTERVAL '1 hour'
                """)
                stats['completed_last_hour'] = cursor.fetchone()['completed_last_hour']
                
                # Worker activity
                cursor.execute("""
                    SELECT assigned_worker_id, COUNT(*) as active_phrases
                    FROM onm_phrases 
                    WHERE status = 'processing'
                    AND assigned_worker_id IS NOT NULL
                    GROUP BY assigned_worker_id
                """)
                stats['worker_activity'] = {row['assigned_worker_id']: row['active_phrases'] 
                                          for row in cursor.fetchall()}
                
                # Failed phrases
                cursor.execute("""
                    SELECT COUNT(*) as failed_phrases
                    FROM onm_phrases 
                    WHERE status = 'failed'
                    AND crawl_attempts >= max_retries
                """)
                stats['permanently_failed'] = cursor.fetchone()['failed_phrases']
                
                # Processing timeouts
                cursor.execute("""
                    SELECT COUNT(*) as timed_out
                    FROM onm_phrases 
                    WHERE status = 'processing'
                    AND processing_timeout < now()
                """)
                stats['timed_out_phrases'] = cursor.fetchone()['timed_out']
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}
            
    def check_health(self) -> Dict[str, Any]:
        """Perform health check."""
        health = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'issues': []
        }
        
        try:
            stats = self.get_system_stats()
            
            # Check if phrases are being processed
            if stats.get('completed_last_hour', 0) < 1000:  # Expect ~1350 per hour
                health['issues'].append('Low completion rate in last hour')
                health['status'] = 'warning'
                
            # Check for too many failed phrases
            if stats.get('permanently_failed', 0) > 100:
                health['issues'].append('High number of permanently failed phrases')
                health['status'] = 'warning'
                
            # Check for processing timeouts
            if stats.get('timed_out_phrases', 0) > 50:
                health['issues'].append('Many phrases have timed out')
                health['status'] = 'warning'
                
            # Check worker activity
            active_workers = len(stats.get('worker_activity', {}))
            if active_workers < 8:  # Expect 12 workers (3 per server * 4 servers)
                health['issues'].append(f'Only {active_workers} workers active')
                health['status'] = 'warning'
                
            health['stats'] = stats
            
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f'Health check failed: {str(e)}')
            
        return health
        
    def run_monitoring(self, interval: int = 300):
        """Run continuous monitoring."""
        self.logger.info("Monitoring started")
        
        while True:
            try:
                health = self.check_health()
                
                if health['status'] != 'healthy':
                    self.logger.warning(f"Health check: {health['status']} - {health['issues']}")
                else:
                    self.logger.info("System healthy")
                    
                # Log detailed stats every 5 checks
                if int(time.time()) % (interval * 5) == 0:
                    self.logger.info(f"Detailed stats: {json.dumps(health['stats'], indent=2)}")
                    
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped")
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    monitor = CrawlerMonitor()
    monitor.run_monitoring()