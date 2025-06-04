#!/usr/bin/env python3
"""
Central Job Scheduler for Scrapyd Cluster

Distributes phrase batches across multiple Scrapyd instances.
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
from flask import Flask, jsonify, request

from config.settings import PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD, PG_PORT

class JobScheduler:
    """Distributes crawling jobs across Scrapyd cluster."""
    
    def __init__(self, scrapyd_services: List[str]):
        """
        Initialize scheduler with Scrapyd service URLs.
        
        Args:
            scrapyd_services: List of Scrapyd service URLs
        """
        self.scrapyd_services = scrapyd_services
        self.project_name = 'crawler'
        self.active_jobs = {}  # {job_id: job_info}
        self.service_loads = {service: 0 for service in scrapyd_services}
        
        self.setup_logging()
        self.setup_api_server()
        
    def setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [JobScheduler] %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/var/log/crawler/job_scheduler.log')
            ]
        )
        self.logger = logging.getLogger('job_scheduler')
        
    def setup_api_server(self):
        """Setup Flask API server for monitoring."""
        self.app = Flask(__name__)
        
        @self.app.route('/health')
        def health_check():
            return jsonify({
                'status': 'healthy',
                'scrapyd_services': len(self.scrapyd_services),
                'active_jobs': len(self.active_jobs)
            })
            
        @self.app.route('/stats')
        def get_stats():
            return jsonify({
                'service_loads': self.service_loads,
                'active_jobs': len(self.active_jobs),
                'scrapyd_services': self.scrapyd_services
            })
            
        @self.app.route('/services')
        def list_services():
            return jsonify({
                'services': [
                    {
                        'url': service,
                        'status': self.check_service_health(service),
                        'load': self.service_loads[service]
                    }
                    for service in self.scrapyd_services
                ]
            })
            
        @self.app.route('/jobs')
        def list_active_jobs():
            return jsonify(self.active_jobs)
            
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
        
    def check_service_health(self, service_url: str) -> str:
        """Check if Scrapyd service is healthy."""
        try:
            response = requests.get(f"{service_url}/daemonstatus.json", timeout=5)
            if response.status_code == 200:
                return 'healthy'
            else:
                return 'unhealthy'
        except Exception:
            return 'unreachable'
            
    def get_healthy_services(self) -> List[str]:
        """Get list of healthy Scrapyd services."""
        healthy = []
        for service in self.scrapyd_services:
            if self.check_service_health(service) == 'healthy':
                healthy.append(service)
        return healthy
        
    def get_least_loaded_service(self) -> Optional[str]:
        """Get the least loaded healthy service."""
        healthy_services = self.get_healthy_services()
        if not healthy_services:
            return None
            
        return min(healthy_services, key=lambda s: self.service_loads[s])
        
    def claim_phrase_batch(self, batch_size: int = 50) -> List[Dict]:
        """Claim a batch of phrases for processing."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                worker_id = str(uuid.uuid4())
                cursor.execute(
                    "SELECT * FROM claim_phrases_for_worker(%s, %s, %s)",
                    (worker_id, batch_size, 30)
                )
                phrases = cursor.fetchall()
                conn.commit()
                return [dict(phrase) for phrase in phrases]
        except Exception as e:
            self.logger.error(f"Error claiming phrases: {e}")
            return []
            
    def deploy_project_to_service(self, service_url: str) -> bool:
        """Deploy crawler project to Scrapyd service."""
        try:
            # Package and deploy the project
            with open('setup.py', 'w') as f:
                f.write("""
from setuptools import setup, find_packages

setup(
    name='crawler',
    version='1.0',
    packages=find_packages(),
    entry_points={
        'scrapy': ['settings = scrapy_crawler.settings']
    }
)
""")
            
            # Create egg file (simplified - in production use scrapyd-deploy)
            import subprocess
            subprocess.run(['python', 'setup.py', 'bdist_egg'], check=True)
            
            # Deploy to Scrapyd
            with open('dist/crawler-1.0-py3.11.egg', 'rb') as egg_file:
                response = requests.post(f"{service_url}/addversion.json", 
                    data={
                        'project': self.project_name,
                        'version': '1.0'
                    },
                    files={'egg': egg_file}
                )
                
            if response.status_code == 200:
                result = response.json()
                return result.get('status') == 'ok'
                
        except Exception as e:
            self.logger.error(f"Error deploying to {service_url}: {e}")
            
        return False
        
    def schedule_job(self, service_url: str, phrases: List[str], 
                    spider: str = 'google') -> Optional[str]:
        """Schedule a job on a Scrapyd service."""
        job_id = str(uuid.uuid4())
        
        try:
            phrases_str = ','.join(phrases)
            
            response = requests.post(f"{service_url}/schedule.json", data={
                'project': self.project_name,
                'spider': spider,
                'jobid': job_id,
                'phrases': phrases_str,
                'worker_id': job_id,
                'page_request': '1'
            })
            
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'ok':
                    self.active_jobs[job_id] = {
                        'service': service_url,
                        'spider': spider,
                        'phrases': phrases,
                        'phrase_count': len(phrases),
                        'started_at': datetime.now(),
                        'status': 'running'
                    }
                    self.service_loads[service_url] += 1
                    
                    self.logger.info(f"Scheduled job {job_id} on {service_url} "
                                   f"with {len(phrases)} phrases")
                    return job_id
                else:
                    self.logger.error(f"Failed to schedule job: {result}")
            else:
                self.logger.error(f"HTTP error scheduling job: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error scheduling job on {service_url}: {e}")
            
        return None
        
    def check_job_status(self, service_url: str, job_id: str) -> str:
        """Check job status on Scrapyd service."""
        try:
            response = requests.get(f"{service_url}/listjobs.json", 
                                  params={'project': self.project_name})
            
            if response.status_code == 200:
                jobs = response.json()
                
                for job in jobs.get('running', []):
                    if job['id'] == job_id:
                        return 'running'
                        
                for job in jobs.get('finished', []):
                    if job['id'] == job_id:
                        return 'finished'
                        
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
            service_url = job_info['service']
            status = self.check_job_status(service_url, job_id)
            
            if status in ['finished', 'unknown']:
                completed_jobs.append(job_id)
                self.service_loads[service_url] = max(0, self.service_loads[service_url] - 1)
                
                duration = datetime.now() - job_info['started_at']
                self.logger.info(f"Job {job_id} completed in {duration.total_seconds():.1f}s "
                               f"({job_info['phrase_count']} phrases)")
                               
        for job_id in completed_jobs:
            del self.active_jobs[job_id]
            
        if completed_jobs:
            self.logger.info(f"Cleaned up {len(completed_jobs)} completed jobs")
            
    def process_phrase_batches(self):
        """Process available phrase batches."""
        self.monitor_jobs()
        
        # Check capacity
        max_concurrent_jobs = len(self.scrapyd_services) * 4
        if len(self.active_jobs) >= max_concurrent_jobs:
            return
            
        # Get batch of phrases
        batch_size = 30
        phrases_data = self.claim_phrase_batch(batch_size)
        
        if not phrases_data:
            return
            
        phrases = [p['phrases'] for p in phrases_data]
        
        # Get available service
        service = self.get_least_loaded_service()
        if not service:
            self.logger.warning("No healthy services available")
            return
            
        # Schedule job
        job_id = self.schedule_job(service, phrases)
        if job_id:
            self.logger.info(f"Scheduled batch of {len(phrases)} phrases")
            
    def activate_hourly_phrases(self):
        """Activate phrases for hourly crawling."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Reset stuck phrases
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
            
    def deploy_to_all_services(self):
        """Deploy crawler project to all healthy Scrapyd services."""
        healthy_services = self.get_healthy_services()
        
        for service in healthy_services:
            success = self.deploy_project_to_service(service)
            if success:
                self.logger.info(f"Successfully deployed to {service}")
            else:
                self.logger.error(f"Failed to deploy to {service}")
                
    def start_api_server(self):
        """Start API server in background thread."""
        import threading
        
        def run_server():
            self.app.run(host='0.0.0.0', port=8080, debug=False)
            
        api_thread = threading.Thread(target=run_server, daemon=True)
        api_thread.start()
        
    def run(self):
        """Run the job scheduler."""
        self.logger.info(f"Job Scheduler started with {len(self.scrapyd_services)} services")
        
        # Start API server
        self.start_api_server()
        
        # Deploy to all services
        self.deploy_to_all_services()
        
        # Schedule hourly phrase activation
        schedule.every().hour.at(":00").do(self.activate_hourly_phrases)
        
        # Initial activation
        self.activate_hourly_phrases()
        
        while True:
            try:
                schedule.run_pending()
                self.process_phrase_batches()
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.logger.info("Scheduler stopped")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(30)


if __name__ == "__main__":
    # Kubernetes service discovery or static configuration
    scrapyd_services = [
        'http://scrapyd-service-1:6800',
        'http://scrapyd-service-2:6800', 
        'http://scrapyd-service-3:6800',
        'http://scrapyd-service-4:6800'
    ]
    
    scheduler = JobScheduler(scrapyd_services)
    scheduler.run()