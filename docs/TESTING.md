# Testing Guide

This guide outlines comprehensive testing strategies for the ONM Crawler containerized Scrapyd deployment system.

## 📋 Testing Strategy Overview

### Test Pyramid Structure
```
                    E2E Tests
                 ┌─────────────────┐
                 │  User Journeys  │
                 │  API Workflows  │
                 └─────────────────┘
               Integration Tests
          ┌─────────────────────────────┐
          │  Component Interactions     │
          │  Database Operations        │
          │  Service Communications     │
          └─────────────────────────────┘
                  Unit Tests
     ┌─────────────────────────────────────────┐
     │  Individual Functions & Classes         │
     │  Business Logic & Algorithms            │
     │  Data Processing & Validation           │
     └─────────────────────────────────────────┘
```

## 🔬 Unit Tests

### 1. Job Scheduler Tests

```python
# tests/unit/test_job_scheduler.py
import pytest
import unittest.mock as mock
from job_scheduler import JobScheduler, ScrapydService

class TestJobScheduler:
    
    @pytest.fixture
    def scheduler(self):
        services = ['http://localhost:6801', 'http://localhost:6802']
        return JobScheduler(services)
    
    def test_select_least_loaded_service(self, scheduler):
        """Test service selection algorithm."""
        with mock.patch.object(scheduler, 'get_service_load') as mock_load:
            mock_load.side_effect = [3, 1]  # Service loads
            
            selected = scheduler.select_least_loaded_service()
            assert selected == 'http://localhost:6802'
    
    def test_batch_phrases_creation(self, scheduler):
        """Test phrase batching logic."""
        phrases = [f"phrase {i}" for i in range(75)]
        batches = scheduler.create_batches(phrases, batch_size=30)
        
        assert len(batches) == 3
        assert len(batches[0]) == 30
        assert len(batches[1]) == 30
        assert len(batches[2]) == 15
    
    @mock.patch('requests.post')
    def test_schedule_job_success(self, mock_post, scheduler):
        """Test successful job scheduling."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'status': 'ok', 'jobid': 'test-job-123'}
        
        phrases = ['test phrase 1', 'test phrase 2']
        result = scheduler.schedule_job('http://localhost:6801', phrases)
        
        assert result['status'] == 'success'
        assert result['job_id'] == 'test-job-123'
    
    @mock.patch('requests.post')
    def test_schedule_job_failure(self, mock_post, scheduler):
        """Test job scheduling failure handling."""
        mock_post.side_effect = requests.RequestException("Connection error")
        
        phrases = ['test phrase 1']
        result = scheduler.schedule_job('http://localhost:6801', phrases)
        
        assert result['status'] == 'error'
        assert 'Connection error' in result['error']

class TestScrapydService:
    
    def test_health_check_healthy(self):
        """Test healthy service detection."""
        with mock.patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'status': 'ok'}
            
            service = ScrapydService('http://localhost:6801')
            assert service.is_healthy() == True
    
    def test_health_check_unhealthy(self):
        """Test unhealthy service detection."""
        with mock.patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException()
            
            service = ScrapydService('http://localhost:6801')
            assert service.is_healthy() == False
```

### 2. Database Function Tests

```python
# tests/unit/test_database.py
import pytest
import psycopg2
from unittest.mock import patch, MagicMock
from utils.database import claim_phrases_for_worker, complete_phrase

class TestDatabaseFunctions:
    
    @pytest.fixture
    def mock_connection(self):
        """Mock database connection."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        return conn, cursor
    
    def test_claim_phrases_for_worker(self, mock_connection):
        """Test phrase claiming functionality."""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            (1, 'test phrase 1'),
            (2, 'test phrase 2')
        ]
        
        with patch('utils.database.get_db_connection', return_value=conn):
            result = claim_phrases_for_worker('test-worker', batch_size=2)
            
        assert len(result) == 2
        assert result[0]['phrase_text'] == 'test phrase 1'
        cursor.execute.assert_called_once()
    
    def test_complete_phrase_success(self, mock_connection):
        """Test successful phrase completion."""
        conn, cursor = mock_connection
        
        with patch('utils.database.get_db_connection', return_value=conn):
            result = complete_phrase(1, 'completed', results={'found': True})
            
        assert result == True
        cursor.execute.assert_called_once()
    
    def test_database_connection_failure(self):
        """Test database connection error handling."""
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError()):
            with pytest.raises(psycopg2.OperationalError):
                claim_phrases_for_worker('test-worker')
```

### 3. Spider Tests

```python
# tests/unit/test_spiders.py
import pytest
from scrapy.http import HtmlResponse, Request
from scrapy_crawler.spiders.search.google import GoogleSpider
from scrapy_crawler.spiders.search.bing import BingSpider

class TestGoogleSpider:
    
    def test_spider_initialization(self):
        """Test spider initialization with parameters."""
        spider = GoogleSpider(
            phrases='test phrase 1,test phrase 2',
            worker_id='test-worker',
            page_request='2'
        )
        
        assert len(spider.phrases) == 2
        assert spider.worker_id == 'test-worker'
        assert spider.page_request == 2
    
    def test_parse_search_results(self):
        """Test search results parsing."""
        spider = GoogleSpider(phrases='test phrase')
        
        # Create mock response
        html = '''
        <div class="g">
            <h3><a href="https://example.com">Test Result</a></h3>
            <span>Test description</span>
        </div>
        '''
        response = HtmlResponse(
            url='https://www.google.com/search?q=test+phrase',
            body=html.encode('utf-8')
        )
        
        results = list(spider.parse(response))
        assert len(results) > 0
        assert 'title' in results[0]
        assert 'url' in results[0]
    
    def test_handle_no_results(self):
        """Test handling of no search results."""
        spider = GoogleSpider(phrases='nonexistent phrase')
        
        html = '<div class="no-results">No results found</div>'
        response = HtmlResponse(
            url='https://www.google.com/search?q=nonexistent+phrase',
            body=html.encode('utf-8')
        )
        
        results = list(spider.parse(response))
        # Should still yield item with empty results
        assert len(results) == 1
        assert results[0]['results'] == []

class TestBingSpider:
    
    def test_bing_spider_initialization(self):
        """Test Bing spider initialization."""
        spider = BingSpider(phrases='bing test')
        assert spider.name == 'bing'
        assert len(spider.phrases) == 1
    
    def test_bing_search_url_generation(self):
        """Test Bing search URL generation."""
        spider = BingSpider(phrases='test query')
        request = spider.start_requests().__next__()
        
        assert 'bing.com' in request.url
        assert 'test+query' in request.url
```

## 🔗 Integration Tests

### 1. Service Communication Tests

```python
# tests/integration/test_service_communication.py
import pytest
import requests
import time
from testcontainers.postgres import PostgresContainer
from testcontainers.compose import DockerCompose

class TestServiceCommunication:
    
    @pytest.fixture(scope="class")
    def docker_services(self):
        """Start Docker services for testing."""
        with DockerCompose(".", compose_file_name="docker-compose.test.yml") as compose:
            # Wait for services to be ready
            self.wait_for_service("http://localhost:8080/health")
            self.wait_for_service("http://localhost:6801/daemonstatus.json")
            yield compose
    
    def wait_for_service(self, url, timeout=60):
        """Wait for service to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(2)
        raise TimeoutError(f"Service at {url} not ready within {timeout}s")
    
    def test_scheduler_to_scrapyd_communication(self, docker_services):
        """Test job scheduler can communicate with Scrapyd."""
        # Schedule a job through the scheduler
        job_data = {
            "phrases": ["integration test phrase"],
            "spider": "google",
            "priority": "medium"
        }
        
        response = requests.post(
            "http://localhost:8080/jobs/schedule",
            json=job_data
        )
        
        assert response.status_code == 201
        job_result = response.json()
        assert 'job_id' in job_result
        
        # Verify job appears in Scrapyd
        time.sleep(5)
        scrapyd_response = requests.get(
            "http://localhost:6801/listjobs.json?project=crawler"
        )
        jobs = scrapyd_response.json()
        
        # Job should be in pending or running state
        all_jobs = jobs['pending'] + jobs['running']
        job_ids = [job['id'] for job in all_jobs]
        assert job_result['job_id'] in job_ids
    
    def test_database_integration(self, docker_services):
        """Test database integration with scheduler."""
        # Check database stats endpoint
        response = requests.get("http://localhost:8080/database/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert 'phrase_status' in stats
        assert 'total_phrases' in stats
    
    def test_scrapyd_cluster_load_balancing(self, docker_services):
        """Test load balancing across Scrapyd instances."""
        # Schedule multiple jobs
        jobs = []
        for i in range(8):
            job_data = {
                "phrases": [f"load test phrase {i}"],
                "spider": "google"
            }
            response = requests.post(
                "http://localhost:8080/jobs/schedule",
                json=job_data
            )
            jobs.append(response.json())
        
        # Check distribution across services
        service_loads = {}
        for port in [6801, 6802, 6803, 6804]:
            response = requests.get(f"http://localhost:{port}/listjobs.json?project=crawler")
            jobs_data = response.json()
            active_jobs = len(jobs_data['running']) + len(jobs_data['pending'])
            service_loads[port] = active_jobs
        
        # Should have some distribution (not all on one service)
        active_services = sum(1 for load in service_loads.values() if load > 0)
        assert active_services > 1
```

### 2. Database Integration Tests

```python
# tests/integration/test_database_integration.py
import pytest
import psycopg2
from testcontainers.postgres import PostgresContainer
import uuid

class TestDatabaseIntegration:
    
    @pytest.fixture(scope="class")
    def postgres_container(self):
        """Start PostgreSQL container for testing."""
        with PostgresContainer("postgres:15") as postgres:
            # Initialize test database
            self.setup_test_database(postgres)
            yield postgres
    
    def setup_test_database(self, postgres):
        """Set up test database with required tables and functions."""
        conn = psycopg2.connect(postgres.get_connection_url())
        with conn.cursor() as cursor:
            # Create test table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS onm_phrases (
                    id SERIAL PRIMARY KEY,
                    phrases VARCHAR(500) NOT NULL,
                    priority INTEGER DEFAULT 1,
                    status VARCHAR(20) DEFAULT 'inactive',
                    assigned_worker_id UUID,
                    assigned_at TIMESTAMP,
                    processing_timeout TIMESTAMP,
                    last_crawled_at TIMESTAMP,
                    crawl_attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT now(),
                    modified_at TIMESTAMP DEFAULT now()
                );
            """)
            
            # Insert test data
            cursor.execute("""
                INSERT INTO onm_phrases (phrases, status, priority) VALUES
                ('test phrase 1', 'active', 1),
                ('test phrase 2', 'active', 2),
                ('test phrase 3', 'inactive', 1),
                ('test phrase 4', 'processing', 1);
            """)
            
            # Create claim function
            cursor.execute("""
                CREATE OR REPLACE FUNCTION claim_phrases_for_worker(
                    worker_id uuid,
                    batch_size integer DEFAULT 10,
                    timeout_minutes integer DEFAULT 30
                ) RETURNS TABLE(phrase_id integer, phrase_text character varying)
                LANGUAGE plpgsql AS $$
                BEGIN
                    RETURN QUERY
                    UPDATE onm_phrases
                    SET status = 'processing',
                        assigned_worker_id = worker_id,
                        assigned_at = now(),
                        processing_timeout = now() + (timeout_minutes || ' minutes')::INTERVAL,
                        modified_at = now()
                    WHERE id IN (
                        SELECT p.id FROM onm_phrases p
                        WHERE p.status = 'active'
                        ORDER BY p.priority DESC, p.created_at ASC
                        LIMIT batch_size
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id, phrases;
                END;
                $$;
            """)
        conn.commit()
        conn.close()
    
    def test_phrase_claiming_concurrency(self, postgres_container):
        """Test concurrent phrase claiming."""
        import threading
        import time
        
        results = []
        
        def claim_phrases(worker_id):
            conn = psycopg2.connect(postgres_container.get_connection_url())
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM claim_phrases_for_worker(%s, 2, 30);",
                    (str(uuid.uuid4()),)
                )
                phrases = cursor.fetchall()
                results.append(phrases)
            conn.close()
        
        # Run concurrent claims
        threads = []
        for i in range(3):
            thread = threading.Thread(target=claim_phrases, args=(f"worker-{i}",))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no duplicate claims
        all_phrase_ids = []
        for result in results:
            phrase_ids = [phrase[0] for phrase in result]
            all_phrase_ids.extend(phrase_ids)
        
        assert len(all_phrase_ids) == len(set(all_phrase_ids))  # No duplicates
    
    def test_timeout_handling(self, postgres_container):
        """Test phrase timeout and recovery."""
        conn = psycopg2.connect(postgres_container.get_connection_url())
        
        with conn.cursor() as cursor:
            # Claim a phrase
            worker_id = str(uuid.uuid4())
            cursor.execute(
                "SELECT * FROM claim_phrases_for_worker(%s, 1, 0);",  # 0 minute timeout
                (worker_id,)
            )
            claimed = cursor.fetchall()
            assert len(claimed) == 1
            
            # Simulate timeout by setting past timeout
            cursor.execute("""
                UPDATE onm_phrases 
                SET processing_timeout = now() - INTERVAL '1 hour'
                WHERE assigned_worker_id = %s;
            """, (worker_id,))
            
            # Should be able to claim again
            new_worker_id = str(uuid.uuid4())
            cursor.execute("""
                UPDATE onm_phrases
                SET status = 'active', assigned_worker_id = NULL
                WHERE processing_timeout < now();
            """)
            
            cursor.execute(
                "SELECT * FROM claim_phrases_for_worker(%s, 1, 30);",
                (new_worker_id,)
            )
            reclaimed = cursor.fetchall()
            assert len(reclaimed) == 1
        
        conn.commit()
        conn.close()
```

## 🌐 End-to-End Tests

### 1. Complete Workflow Tests

```python
# tests/e2e/test_complete_workflow.py
import pytest
import requests
import time
import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestCompleteWorkflow:
    
    @pytest.fixture
    def browser(self):
        """Set up headless browser for UI testing."""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        yield driver
        driver.quit()
    
    def test_phrase_to_completion_workflow(self):
        """Test complete phrase processing workflow."""
        # 1. Add phrase to database
        test_phrase = f"e2e test phrase {int(time.time())}"
        
        # Insert via API or direct DB
        response = requests.post("http://localhost:8080/jobs/schedule", json={
            "phrases": [test_phrase],
            "spider": "google",
            "priority": "high"
        })
        assert response.status_code == 201
        job_data = response.json()
        
        # 2. Monitor job progress
        job_id = job_data['job_id']
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = requests.get(f"http://localhost:8080/jobs/{job_id}")
            if response.status_code == 404:
                # Job completed
                break
            
            job_status = response.json()
            if job_status['status'] in ['completed', 'failed']:
                break
                
            time.sleep(10)
        
        # 3. Verify completion in database
        # (Database check would go here)
        
        # 4. Check results were processed
        stats_response = requests.get("http://localhost:8080/stats")
        stats = stats_response.json()
        assert stats['total_phrases_processed'] > 0
    
    def test_web_interface_monitoring(self, browser):
        """Test web interface functionality."""
        # Navigate to scheduler dashboard
        browser.get("http://localhost/scheduler/")
        
        # Wait for page to load
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Check health status is visible
        health_element = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "health-status"))
        )
        assert "healthy" in health_element.text.lower()
        
        # Navigate to Scrapyd interface
        browser.get("http://localhost/scrapyd-1/")
        
        # Check Scrapyd jobs page loads
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        # Verify job information is displayed
        tables = browser.find_elements(By.TAG_NAME, "table")
        assert len(tables) > 0
    
    def test_high_volume_processing(self):
        """Test system under high phrase volume."""
        # Schedule many jobs
        phrases = [f"high volume test {i}" for i in range(100)]
        batch_size = 10
        
        scheduled_jobs = []
        for i in range(0, len(phrases), batch_size):
            batch = phrases[i:i+batch_size]
            response = requests.post("http://localhost:8080/jobs/schedule", json={
                "phrases": batch,
                "spider": "google"
            })
            if response.status_code == 201:
                scheduled_jobs.append(response.json())
        
        # Monitor system health during processing
        start_time = time.time()
        while time.time() - start_time < 600:  # 10 minutes
            health_response = requests.get("http://localhost:8080/health")
            assert health_response.status_code == 200
            
            stats_response = requests.get("http://localhost:8080/stats")
            stats = stats_response.json()
            
            # Check no services are overloaded
            max_load = max(stats['service_loads'].values())
            assert max_load <= 8  # Reasonable limit
            
            time.sleep(30)
            
            # Break if all jobs complete
            if stats['active_jobs'] == 0:
                break
```

## ⚡ Performance Tests

### 1. Load Testing

```python
# tests/performance/test_load.py
import pytest
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor
import statistics

class TestPerformance:
    
    def test_scheduler_api_performance(self):
        """Test API response times under load."""
        def make_request():
            start_time = time.time()
            response = requests.get("http://localhost:8080/stats")
            end_time = time.time()
            return end_time - start_time, response.status_code
        
        # Run concurrent requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [future.result() for future in futures]
        
        response_times = [result[0] for result in results]
        status_codes = [result[1] for result in results]
        
        # All requests should succeed
        assert all(code == 200 for code in status_codes)
        
        # Performance requirements
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        
        assert avg_response_time < 0.5  # 500ms average
        assert p95_response_time < 1.0  # 1s 95th percentile
    
    async def test_concurrent_job_scheduling(self):
        """Test concurrent job scheduling performance."""
        async def schedule_job(session, phrase):
            start_time = time.time()
            async with session.post(
                "http://localhost:8080/jobs/schedule",
                json={"phrases": [phrase], "spider": "google"}
            ) as response:
                end_time = time.time()
                return await response.json(), end_time - start_time
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                schedule_job(session, f"perf test {i}")
                for i in range(50)
            ]
            results = await asyncio.gather(*tasks)
        
        response_times = [result[1] for result in results]
        avg_time = statistics.mean(response_times)
        
        assert avg_time < 1.0  # Average scheduling time under 1s
    
    def test_database_performance(self):
        """Test database operation performance."""
        import psycopg2
        
        # Test phrase claiming performance
        start_time = time.time()
        
        for i in range(100):
            conn = psycopg2.connect(
                host='localhost',
                database='onm',
                user='onm_admin',
                password='onmdb'
            )
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM claim_phrases_for_worker(%s, 5, 30);",
                    (f"perf-worker-{i}",)
                )
                cursor.fetchall()
            conn.close()
        
        end_time = time.time()
        avg_claim_time = (end_time - start_time) / 100
        
        assert avg_claim_time < 0.1  # Less than 100ms per claim operation
```

### 2. Stress Testing

```bash
# tests/performance/stress_test.sh
#!/bin/bash

echo "Starting stress tests..."

# Test 1: High concurrent API requests
echo "Test 1: API stress test"
ab -n 1000 -c 50 http://localhost:8080/health

# Test 2: Job scheduling stress
echo "Test 2: Job scheduling stress"
for i in {1..100}; do
    curl -X POST http://localhost:8080/jobs/schedule \
        -H "Content-Type: application/json" \
        -d "{\"phrases\": [\"stress test $i\"], \"spider\": \"google\"}" &
done
wait

# Test 3: Database connection stress
echo "Test 3: Database stress"
for i in {1..50}; do
    psql -h localhost -U onm_admin -d onm -c "SELECT COUNT(*) FROM onm_phrases;" &
done
wait

echo "Stress tests completed"
```

## 🔒 Security Tests

```python
# tests/security/test_security.py
import pytest
import requests
import subprocess

class TestSecurity:
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection."""
        malicious_payload = "'; DROP TABLE onm_phrases; --"
        
        response = requests.post("http://localhost:8080/jobs/schedule", json={
            "phrases": [malicious_payload],
            "spider": "google"
        })
        
        # Should not cause server error
        assert response.status_code in [200, 201, 400]
        
        # Database should still be intact
        stats_response = requests.get("http://localhost:8080/database/stats")
        assert stats_response.status_code == 200
    
    def test_rate_limiting(self):
        """Test API rate limiting."""
        # Make many rapid requests
        responses = []
        for i in range(100):
            response = requests.get("http://localhost:8080/health")
            responses.append(response.status_code)
        
        # Some requests should be rate limited
        rate_limited = sum(1 for code in responses if code == 429)
        assert rate_limited > 0
    
    def test_container_security(self):
        """Test container security configurations."""
        # Check if containers run as non-root
        result = subprocess.run([
            "docker", "exec", "scrapyd-1", "whoami"
        ], capture_output=True, text=True)
        
        assert result.stdout.strip() != "root"
    
    def test_input_validation(self):
        """Test input validation and sanitization."""
        # Test with malformed JSON
        response = requests.post(
            "http://localhost:8080/jobs/schedule",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        
        # Test with missing required fields
        response = requests.post(
            "http://localhost:8080/jobs/schedule",
            json={"spider": "google"}  # Missing phrases
        )
        assert response.status_code == 400
```

## 🏗️ Infrastructure Tests

```python
# tests/infrastructure/test_infrastructure.py
import pytest
import docker
import subprocess
import yaml

class TestInfrastructure:
    
    def test_docker_health_checks(self):
        """Test Docker container health checks."""
        client = docker.from_env()
        
        containers = [
            'scrapyd-1', 'scrapyd-2', 'scrapyd-3', 'scrapyd-4',
            'job-scheduler', 'crawler-postgres'
        ]
        
        for container_name in containers:
            container = client.containers.get(container_name)
            health = container.attrs['State']['Health']['Status']
            assert health == 'healthy'
    
    def test_kubernetes_deployment(self):
        """Test Kubernetes deployment health."""
        # Check pod status
        result = subprocess.run([
            "kubectl", "get", "pods", "-n", "crawler-system", "-o", "json"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            import json
            pods_data = json.loads(result.stdout)
            
            for pod in pods_data['items']:
                status = pod['status']['phase']
                assert status == 'Running'
    
    def test_resource_limits(self):
        """Test container resource usage."""
        client = docker.from_env()
        
        for container_name in ['scrapyd-1', 'job-scheduler']:
            container = client.containers.get(container_name)
            stats = container.stats(stream=False)
            
            # Check memory usage is reasonable
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100
            
            assert memory_percent < 90  # Less than 90% memory usage
    
    def test_network_connectivity(self):
        """Test inter-service network connectivity."""
        # Test scheduler can reach Scrapyd services
        result = subprocess.run([
            "docker", "exec", "job-scheduler",
            "curl", "-f", "http://scrapyd-1:6800/daemonstatus.json"
        ], capture_output=True)
        
        assert result.returncode == 0
        
        # Test Scrapyd can reach database
        result = subprocess.run([
            "docker", "exec", "scrapyd-1",
            "python", "-c", "import psycopg2; psycopg2.connect(host='postgres', user='onm_admin', database='onm', password='onmdb')"
        ], capture_output=True)
        
        assert result.returncode == 0
```

## 📊 Monitoring Tests

```python
# tests/monitoring/test_monitoring.py
import pytest
import requests
import time

class TestMonitoring:
    
    def test_health_endpoints(self):
        """Test all health check endpoints."""
        endpoints = [
            "http://localhost:8080/health",
            "http://localhost:6801/daemonstatus.json",
            "http://localhost:6802/daemonstatus.json",
            "http://localhost:6803/daemonstatus.json",
            "http://localhost:6804/daemonstatus.json"
        ]
        
        for endpoint in endpoints:
            response = requests.get(endpoint)
            assert response.status_code == 200
            
            data = response.json()
            if 'status' in data:
                assert data['status'] in ['healthy', 'ok']
    
    def test_metrics_collection(self):
        """Test metrics are being collected."""
        # Check stats endpoint
        response = requests.get("http://localhost:8080/stats")
        assert response.status_code == 200
        
        stats = response.json()
        required_metrics = [
            'active_jobs', 'service_loads', 'total_phrases_processed'
        ]
        
        for metric in required_metrics:
            assert metric in stats
    
    def test_log_generation(self):
        """Test log files are being generated."""
        import os
        
        log_files = [
            './logs/scheduler.log',
            './logs/scrapyd-1.log'
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                # Check file is not empty and recent
                stat = os.stat(log_file)
                assert stat.st_size > 0
                assert time.time() - stat.st_mtime < 3600  # Modified within last hour
```

## 🧪 Chaos Engineering Tests

```python
# tests/chaos/test_resilience.py
import pytest
import docker
import time
import requests
import subprocess

class TestChaosEngineering:
    
    def test_scrapyd_instance_failure(self):
        """Test system resilience when Scrapyd instance fails."""
        client = docker.from_env()
        
        # Stop one Scrapyd instance
        container = client.containers.get('scrapyd-1')
        container.stop()
        
        try:
            # System should still be functional
            time.sleep(10)  # Allow time for service discovery
            
            response = requests.get("http://localhost:8080/health")
            assert response.status_code == 200
            
            # Should be able to schedule jobs
            response = requests.post("http://localhost:8080/jobs/schedule", json={
                "phrases": ["chaos test"],
                "spider": "google"
            })
            assert response.status_code == 201
            
        finally:
            # Restart the container
            container.restart()
            time.sleep(10)
    
    def test_database_connection_loss(self):
        """Test handling of database connection loss."""
        client = docker.from_env()
        
        # Stop database
        db_container = client.containers.get('crawler-postgres')
        db_container.stop()
        
        try:
            time.sleep(5)
            
            # Scheduler should detect database issue
            response = requests.get("http://localhost:8080/health")
            # Should return degraded status or error
            assert response.status_code in [200, 503]
            
            if response.status_code == 200:
                health = response.json()
                assert health['status'] != 'healthy'
                
        finally:
            # Restart database
            db_container.restart()
            time.sleep(15)  # Allow time for full startup
    
    def test_high_memory_pressure(self):
        """Test system behavior under memory pressure."""
        # Schedule many concurrent jobs to create memory pressure
        jobs = []
        for i in range(20):
            response = requests.post("http://localhost:8080/jobs/schedule", json={
                "phrases": [f"memory pressure test {i}" for j in range(50)],
                "spider": "google"
            })
            if response.status_code == 201:
                jobs.append(response.json())
        
        # Monitor system health
        start_time = time.time()
        while time.time() - start_time < 300:  # 5 minutes
            response = requests.get("http://localhost:8080/health")
            # System should remain responsive
            assert response.status_code == 200
            time.sleep(10)
```

## 🔄 Test Automation

### Test Configuration

```yaml
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=.
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
    security: Security tests
    chaos: Chaos engineering tests
    slow: Slow running tests
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-mock
    - name: Run unit tests
      run: pytest tests/unit -m unit --cov

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: onmdb
          POSTGRES_USER: onm_admin
          POSTGRES_DB: onm
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
    - uses: actions/checkout@v3
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    - name: Start services
      run: docker-compose -f docker-compose.test.yml up -d
    - name: Wait for services
      run: |
        timeout 300 bash -c 'while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' localhost:8080/health)" != "200" ]]; do sleep 5; done'
    - name: Run integration tests
      run: pytest tests/integration -m integration

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Start full system
      run: docker-compose -f docker-compose.scrapyd.yml up -d
    - name: Wait for system ready
      run: |
        timeout 600 bash -c 'while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' localhost:8080/health)" != "200" ]]; do sleep 10; done'
    - name: Run E2E tests
      run: pytest tests/e2e -m e2e

  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v3
    - name: Start services
      run: docker-compose -f docker-compose.scrapyd.yml up -d
    - name: Run performance tests
      run: pytest tests/performance -m performance
    - name: Upload performance report
      uses: actions/upload-artifact@v3
      with:
        name: performance-report
        path: performance-report.html
```

This comprehensive testing strategy covers all aspects of your distributed crawler system and ensures reliability, performance, and security across all components. 