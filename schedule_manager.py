#!/usr/bin/env python3
"""
Schedule Manager for ONM Phrase Crawling

Manages the hourly activation of phrases for crawling.
Ensures all 5400 phrases are activated every hour.
"""

import time
import logging
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

from config.settings import PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD

class ScheduleManager:
    """Manages hourly phrase activation schedule."""
    
    def __init__(self):
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [ScheduleManager] %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/var/log/crawler/schedule_manager.log')
            ]
        )
        self.logger = logging.getLogger('schedule_manager')
        
    def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=PG_HOST,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD,
            cursor_factory=RealDictCursor
        )
        
    def activate_phrases_for_hour(self):
        """Activate all phrases that need to be crawled this hour."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # First, reset any stuck processing phrases (older than 1 hour)
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
                
                stuck_count = cursor.rowcount
                if stuck_count > 0:
                    self.logger.warning(f"Reset {stuck_count} stuck phrases")
                
                # Activate phrases that haven't been crawled in the last hour
                # or have never been crawled
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
                
                # Get current stats
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM onm_phrases 
                    GROUP BY status
                """)
                
                stats = {row['status']: row['count'] for row in cursor.fetchall()}
                self.logger.info(f"Current phrase status: {stats}")
                
                return activated_count
                
        except Exception as e:
            self.logger.error(f"Error activating phrases: {e}")
            return 0
            
    def run_hourly_schedule(self):
        """Run the hourly scheduling loop."""
        self.logger.info("Schedule manager started")
        
        while True:
            try:
                # Wait for the top of the hour
                now = datetime.now()
                next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                sleep_seconds = (next_hour - now).total_seconds()
                
                self.logger.info(f"Waiting {sleep_seconds:.0f} seconds until next hour ({next_hour})")
                time.sleep(sleep_seconds)
                
                # Activate phrases for this hour
                activated = self.activate_phrases_for_hour()
                self.logger.info(f"Hourly activation completed: {activated} phrases activated")
                
            except KeyboardInterrupt:
                self.logger.info("Schedule manager stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in schedule loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying


if __name__ == "__main__":
    manager = ScheduleManager()
    manager.run_hourly_schedule()