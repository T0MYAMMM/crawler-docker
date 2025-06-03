# conftest.py - Shared pytest fixtures

import pytest
import docker
import psycopg2
import requests
import time
import uuid
from testcontainers.postgres import PostgresContainer
from testcontainers.compose import DockerCompose

@pytest.fixture(scope="session")
def docker_client():
    """Docker client for container operations."""
    return docker.from_env()

@pytest.fixture(scope="session")
def test_database():
    """PostgreSQL test database container."""
    with PostgresContainer("postgres:15", 
                          username="test_user",
                          password="test_pass",
                          dbname="test_db") as postgres:
        # Initialize test schema
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
            test_phrases = [
                ('test phrase 1', 'active', 1),
                ('test phrase 2', 'active', 2),
                ('test phrase 3', 'inactive', 1),
                ('test phrase 4', 'processing', 1),
            ]
            
            cursor.executemany(
                "INSERT INTO onm_phrases (phrases, status, priority) VALUES (%s, %s, %s)",
                test_phrases
            )
            
            # Create functions
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
            
            cursor.execute("""
                CREATE OR REPLACE FUNCTION complete_phrase(
                    phrase_id integer,
                    new_status varchar(20),
                    crawl_results jsonb DEFAULT NULL
                ) RETURNS boolean
                LANGUAGE plpgsql AS $$
                BEGIN
                    UPDATE onm_phrases
                    SET status = new_status,
                        last_crawled_at = now(),
                        crawl_attempts = crawl_attempts + 1,
                        modified_at = now(),
                        assigned_worker_id = NULL,
                        processing_timeout = NULL
                    WHERE id = phrase_id;
                    
                    RETURN FOUND;
                END;
                $$;
            """)
        
        conn.commit()
        conn.close()
        yield postgres

@pytest.fixture(scope="session")
def docker_services():
    """Docker Compose services for integration testing."""
    compose_file = "docker-compose.test.yml"
    
    with DockerCompose(".", compose_file_name=compose_file) as compose:
        # Wait for services to be ready
        wait_for_service("http://localhost:8080/health", timeout=120)
        wait_for_service("http://localhost:6801/daemonstatus.json", timeout=60)
        yield compose

@pytest.fixture
def api_client():
    """HTTP client for API testing."""
    class APIClient:
        def __init__(self, base_url="http://localhost:8080"):
            self.base_url = base_url
            
        def get(self, endpoint, **kwargs):
            return requests.get(f"{self.base_url}{endpoint}", **kwargs)
            
        def post(self, endpoint, **kwargs):
            return requests.post(f"{self.base_url}{endpoint}", **kwargs)
            
        def delete(self, endpoint, **kwargs):
            return requests.delete(f"{self.base_url}{endpoint}", **kwargs)
    
    return APIClient()

@pytest.fixture
def scrapyd_client():
    """Scrapyd client for testing."""
    class ScrapydClient:
        def __init__(self, base_url="http://localhost:6801"):
            self.base_url = base_url
            
        def get_status(self):
            response = requests.get(f"{self.base_url}/daemonstatus.json")
            return response.json()
            
        def list_jobs(self, project="crawler"):
            response = requests.get(f"{self.base_url}/listjobs.json?project={project}")
            return response.json()
            
        def schedule_job(self, spider, **kwargs):
            data = {"project": "crawler", "spider": spider}
            data.update(kwargs)
            response = requests.post(f"{self.base_url}/schedule.json", data=data)
            return response.json()
    
    return ScrapydClient()

@pytest.fixture
def test_phrases():
    """Generate test phrases for testing."""
    return [
        f"test phrase {uuid.uuid4().hex[:8]}" for _ in range(10)
    ]

@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    # Cleanup code here if needed
    pass

def wait_for_service(url, timeout=60, interval=2):
    """Wait for a service to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    raise TimeoutError(f"Service at {url} not ready within {timeout}s")

# Pytest markers
pytest_plugins = ["pytest_html"]

# Custom pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "security: mark test as security test")
    config.addinivalue_line("markers", "chaos: mark test as chaos engineering test")
    config.addinivalue_line("markers", "slow: mark test as slow running test") 