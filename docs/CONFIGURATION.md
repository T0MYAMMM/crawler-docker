# Configuration Guide

This guide covers all configuration options for the ONM Crawler containerized Scrapyd deployment system.

## 📋 Table of Contents

- [Environment Variables](#environment-variables)
- [Scrapyd Configuration](#scrapyd-configuration)
- [Job Scheduler Configuration](#job-scheduler-configuration)
- [Database Configuration](#database-configuration)
- [Kubernetes Configuration](#kubernetes-configuration)
- [Docker Compose Configuration](#docker-compose-configuration)
- [Logging Configuration](#logging-configuration)
- [Performance Tuning](#performance-tuning)

## 🌍 Environment Variables

### Core System Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PG_HOST` | PostgreSQL database host | `localhost` | ✅ |
| `PG_DATABASE` | Database name | `onm` | ✅ |
| `PG_USER` | Database username | `onm_admin` | ✅ |
| `PG_PASSWORD` | Database password | - | ✅ |
| `PG_PORT` | Database port | `5432` | ❌ |

### Job Scheduler Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SCRAPYD_SERVICES` | Comma-separated Scrapyd URLs | - | ✅ |
| `BATCH_SIZE` | Phrases per job batch | `30` | ❌ |
| `MAX_CONCURRENT_JOBS` | Max jobs per Scrapyd instance | `4` | ❌ |
| `CHECK_INTERVAL` | Health check interval (seconds) | `10` | ❌ |
| `JOB_TIMEOUT` | Job timeout in minutes | `30` | ❌ |
| `API_PORT` | Scheduler API port | `8080` | ❌ |

### Scrapyd Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SCRAPYD_PORT` | Scrapyd service port | `6800` | ❌ |
| `MAX_PROC` | Maximum concurrent processes | `4` | ❌ |
| `MAX_PROC_PER_CPU` | Processes per CPU core | `2` | ❌ |
| `JOBS_TO_KEEP` | Jobs to keep in history | `5` | ❌ |
| `FINISHED_TO_KEEP` | Finished jobs to keep | `100` | ❌ |

### Logging Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOG_LEVEL` | Logging level | `INFO` | ❌ |
| `DEBUG` | Enable debug mode | `false` | ❌ |
| `LOG_FORMAT` | Log format style | `standard` | ❌ |
| `LOG_FILE` | Log file path | - | ❌ |

### Spider Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEFAULT_SPIDER` | Default spider to use | `google` | ❌ |
| `PAGE_REQUEST` | Pages to crawl per phrase | `1` | ❌ |
| `DOWNLOAD_DELAY` | Delay between requests | `2` | ❌ |
| `USER_AGENT_ROTATION` | Enable user agent rotation | `true` | ❌ |
| `PROXY_ROTATION` | Enable proxy rotation | `false` | ❌ |

## 🔧 Scrapyd Configuration

### Primary Configuration File: `scrapyd.conf`

```ini
[scrapyd]
# Core settings
eggs_dir    = eggs
logs_dir    = logs
items_dir   = items
dbs_dir     = dbs

# Job management
jobs_to_keep = 5
finished_to_keep = 100
poll_interval = 5.0

# Process limits
max_proc = 4
max_proc_per_cpu = 2

# Network settings
bind_address = 0.0.0.0
http_port = 6800

# System settings
debug = off
runner = scrapyd.runner
application = scrapyd.app.application
launcher = scrapyd.launcher.Launcher
webroot = scrapyd.website.Root

# API endpoints
[services]
schedule.json     = scrapyd.webservice.Schedule
cancel.json       = scrapyd.webservice.Cancel
addversion.json   = scrapyd.webservice.AddVersion
listprojects.json = scrapyd.webservice.ListProjects
listversions.json = scrapyd.webservice.ListVersions
listspiders.json  = scrapyd.webservice.ListSpiders
delproject.json   = scrapyd.webservice.DeleteProject
delversion.json   = scrapyd.webservice.DeleteVersion
listjobs.json     = scrapyd.webservice.ListJobs
daemonstatus.json = scrapyd.webservice.DaemonStatus
```

### Environment-Specific Configurations

#### Development (`scrapyd-dev.conf`)
```ini
[scrapyd]
eggs_dir    = eggs
logs_dir    = logs
items_dir   = items
jobs_to_keep = 3
finished_to_keep = 50
max_proc = 2
max_proc_per_cpu = 1
debug = on
poll_interval = 3.0
```

#### Production (`scrapyd-prod.conf`)
```ini
[scrapyd]
eggs_dir    = /app/eggs
logs_dir    = /app/logs
items_dir   = /app/items
jobs_to_keep = 10
finished_to_keep = 200
max_proc = 6
max_proc_per_cpu = 3
debug = off
poll_interval = 5.0
```

### High-Performance Configuration
```ini
[scrapyd]
# Optimized for high throughput
max_proc = 8
max_proc_per_cpu = 4
jobs_to_keep = 15
finished_to_keep = 300
poll_interval = 2.0

# Memory optimization
autothrottle_enabled = True
autothrottle_start_delay = 1
autothrottle_max_delay = 10
autothrottle_target_concurrency = 2.0
```

## 🎯 Job Scheduler Configuration

### Configuration File: `scheduler_config.py`

```python
import os
from typing import List

class SchedulerConfig:
    """Job Scheduler configuration settings."""
    
    # Database settings
    DB_HOST = os.getenv('PG_HOST', 'localhost')
    DB_NAME = os.getenv('PG_DATABASE', 'onm')
    DB_USER = os.getenv('PG_USER', 'onm_admin')
    DB_PASSWORD = os.getenv('PG_PASSWORD')
    DB_PORT = int(os.getenv('PG_PORT', '5432'))
    
    # Scrapyd cluster settings
    SCRAPYD_SERVICES = os.getenv('SCRAPYD_SERVICES', '').split(',')
    if not SCRAPYD_SERVICES or SCRAPYD_SERVICES == ['']:
        SCRAPYD_SERVICES = [
            'http://scrapyd-1:6800',
            'http://scrapyd-2:6800',
            'http://scrapyd-3:6800',
            'http://scrapyd-4:6800'
        ]
    
    # Job management
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '30'))
    MAX_CONCURRENT_JOBS_PER_SERVICE = int(os.getenv('MAX_CONCURRENT_JOBS', '4'))
    JOB_TIMEOUT_MINUTES = int(os.getenv('JOB_TIMEOUT', '30'))
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '10'))
    
    # API settings
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', '8080'))
    API_DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')
    
    # Scheduling settings
    HOURLY_ACTIVATION = os.getenv('HOURLY_ACTIVATION', 'true').lower() in ('true', '1', 'yes')
    ACTIVATION_HOUR_MINUTE = os.getenv('ACTIVATION_MINUTE', '0')  # Minute of hour to activate
    
    # Spider settings
    DEFAULT_SPIDER = os.getenv('DEFAULT_SPIDER', 'google')
    PROJECT_NAME = os.getenv('PROJECT_NAME', 'crawler')
    
    # Performance settings
    HEALTH_CHECK_TIMEOUT = int(os.getenv('HEALTH_CHECK_TIMEOUT', '5'))
    DEPLOYMENT_RETRY_COUNT = int(os.getenv('DEPLOYMENT_RETRY_COUNT', '3'))
    SERVICE_DISCOVERY_INTERVAL = int(os.getenv('SERVICE_DISCOVERY_INTERVAL', '60'))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.getenv('LOG_FORMAT', 'standard')
    LOG_FILE = os.getenv('LOG_FILE')
    
    @classmethod
    def validate(cls):
        """Validate configuration settings."""
        errors = []
        
        if not cls.DB_PASSWORD:
            errors.append("PG_PASSWORD is required")
            
        if not cls.SCRAPYD_SERVICES:
            errors.append("SCRAPYD_SERVICES is required")
            
        if cls.BATCH_SIZE <= 0:
            errors.append("BATCH_SIZE must be positive")
            
        if cls.MAX_CONCURRENT_JOBS_PER_SERVICE <= 0:
            errors.append("MAX_CONCURRENT_JOBS must be positive")
            
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
            
        return True
```

### Environment-Specific Scheduler Configs

#### Development
```bash
# config/dev.env
PG_HOST=postgres
DEBUG=true
LOG_LEVEL=DEBUG
BATCH_SIZE=10
MAX_CONCURRENT_JOBS=2
CHECK_INTERVAL=5
SCRAPYD_SERVICES=http://scrapyd-1:6800,http://scrapyd-2:6800
```

#### Staging
```bash
# config/staging.env
PG_HOST=staging-postgres.example.com
DEBUG=false
LOG_LEVEL=INFO
BATCH_SIZE=25
MAX_CONCURRENT_JOBS=3
CHECK_INTERVAL=10
HOURLY_ACTIVATION=true
```

#### Production
```bash
# config/prod.env
PG_HOST=prod-postgres.example.com
DEBUG=false
LOG_LEVEL=WARNING
BATCH_SIZE=30
MAX_CONCURRENT_JOBS=4
CHECK_INTERVAL=10
HOURLY_ACTIVATION=true
SERVICE_DISCOVERY_INTERVAL=30
```

## 🗄️ Database Configuration

### Connection Settings

```python
# config/database.py
import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

class DatabaseConfig:
    """Database configuration and connection management."""
    
    # Connection parameters
    HOST = os.getenv('PG_HOST', 'localhost')
    PORT = int(os.getenv('PG_PORT', '5432'))
    DATABASE = os.getenv('PG_DATABASE', 'onm')
    USER = os.getenv('PG_USER', 'onm_admin')
    PASSWORD = os.getenv('PG_PASSWORD')
    
    # Connection pool settings
    MIN_CONNECTIONS = int(os.getenv('DB_MIN_CONNECTIONS', '5'))
    MAX_CONNECTIONS = int(os.getenv('DB_MAX_CONNECTIONS', '20'))
    
    # Connection options
    CONNECT_TIMEOUT = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
    STATEMENT_TIMEOUT = int(os.getenv('DB_STATEMENT_TIMEOUT', '30000'))  # milliseconds
    
    @classmethod
    def get_connection_string(cls):
        """Get PostgreSQL connection string."""
        return (
            f"host={cls.HOST} "
            f"port={cls.PORT} "
            f"dbname={cls.DATABASE} "
            f"user={cls.USER} "
            f"password={cls.PASSWORD} "
            f"connect_timeout={cls.CONNECT_TIMEOUT}"
        )
    
    @classmethod
    def create_connection_pool(cls):
        """Create connection pool."""
        return ThreadedConnectionPool(
            cls.MIN_CONNECTIONS,
            cls.MAX_CONNECTIONS,
            cls.get_connection_string()
        )
```

### PostgreSQL Optimization

```sql
-- PostgreSQL configuration for crawler workload
-- Add to postgresql.conf

# Connection settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB

# Performance settings
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Logging
log_statement = 'mod'
log_min_duration_statement = 1000

# Autovacuum (important for high update workload)
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 20s
```

## ☸️ Kubernetes Configuration

### ConfigMap for Environment Variables

```yaml
# k8s-configmap.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crawler-config
  namespace: crawler-system
data:
  # Scheduler settings
  BATCH_SIZE: "30"
  MAX_CONCURRENT_JOBS: "4"
  CHECK_INTERVAL: "10"
  JOB_TIMEOUT: "30"
  
  # Scrapyd settings
  SCRAPYD_PORT: "6800"
  MAX_PROC: "4"
  MAX_PROC_PER_CPU: "2"
  JOBS_TO_KEEP: "5"
  
  # Spider settings
  DEFAULT_SPIDER: "google"
  PROJECT_NAME: "crawler"
  PAGE_REQUEST: "1"
  
  # Performance settings
  DOWNLOAD_DELAY: "2"
  CONCURRENT_REQUESTS: "16"
  AUTOTHROTTLE_ENABLED: "true"
  
  # Logging
  LOG_LEVEL: "INFO"
  DEBUG: "false"
```

### Secrets for Sensitive Data

```yaml
# k8s-secrets.yml
apiVersion: v1
kind: Secret
metadata:
  name: crawler-secrets
  namespace: crawler-system
type: Opaque
data:
  # Base64 encoded values
  PG_PASSWORD: <base64-encoded-password>
  API_KEY: <base64-encoded-api-key>
  KAFKA_PASSWORD: <base64-encoded-kafka-password>
```

### Resource Limits and Requests

```yaml
# Resource configuration in deployment
spec:
  containers:
  - name: scrapyd
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "500m"
  - name: scheduler
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "200m"
```

### Horizontal Pod Autoscaler

```yaml
# hpa-config.yml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: scrapyd-hpa
  namespace: crawler-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: scrapyd-cluster
  minReplicas: 4
  maxReplicas: 16
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: active_jobs_per_pod
      target:
        type: AverageValue
        averageValue: "3"
```

## 🐳 Docker Compose Configuration

### Development Environment

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  scrapyd-1:
    build:
      context: .
      dockerfile: dockerfiles/Dockerfile.scrapyd
    environment:
      - SCRAPYD_PORT=6800
      - MAX_PROC=2
      - MAX_PROC_PER_CPU=1
      - DEBUG=true
      - LOG_LEVEL=DEBUG
    volumes:
      - ./logs:/app/logs
      - ./config/scrapyd-dev.conf:/etc/scrapyd/scrapyd.conf
    
  job-scheduler:
    build:
      context: .
      dockerfile: dockerfiles/Dockerfile.scheduler
    environment:
      - DEBUG=true
      - LOG_LEVEL=DEBUG
      - BATCH_SIZE=10
      - MAX_CONCURRENT_JOBS=2
      - CHECK_INTERVAL=5
    env_file:
      - config/dev.env
```

### Production Environment

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  scrapyd-1:
    image: your-registry/crawler-scrapyd:latest
    environment:
      - SCRAPYD_PORT=6800
      - MAX_PROC=4
      - MAX_PROC_PER_CPU=2
      - DEBUG=false
      - LOG_LEVEL=INFO
    volumes:
      - scrapyd-logs:/app/logs
      - ./config/scrapyd-prod.conf:/etc/scrapyd/scrapyd.conf
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
    
  job-scheduler:
    image: your-registry/crawler-scheduler:latest
    environment:
      - DEBUG=false
      - LOG_LEVEL=INFO
    env_file:
      - config/prod.env
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.2'
```

## 📝 Logging Configuration

### Structured Logging Setup

```python
# config/logging.py
import os
import logging
import logging.config
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Setup structured logging configuration."""
    
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = os.getenv('LOG_FORMAT', 'standard')
    log_file = os.getenv('LOG_FILE')
    
    if log_format == 'json':
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    handlers = [console_handler]
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        handlers=handlers,
        force=True
    )
    
    # Set levels for specific loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('scrapy').setLevel(logging.INFO)
```

### Log Rotation Configuration

```yaml
# logrotate configuration for Docker
apiVersion: v1
kind: ConfigMap
metadata:
  name: logrotate-config
data:
  logrotate.conf: |
    /app/logs/*.log {
        daily
        rotate 7
        compress
        delaycompress
        missingok
        notifempty
        create 644 scrapyd scrapyd
        postrotate
            /usr/bin/pkill -HUP scrapyd
        endscript
    }
```

## 🚀 Performance Tuning

### Scrapyd Performance Optimization

```ini
# High-performance Scrapyd configuration
[scrapyd]
max_proc = 8
max_proc_per_cpu = 4
jobs_to_keep = 20
finished_to_keep = 500
poll_interval = 1.0

# Memory management
autothrottle_enabled = True
autothrottle_start_delay = 0.5
autothrottle_max_delay = 5
autothrottle_target_concurrency = 3.0
autothrottle_debug = False

# Request optimization
concurrent_requests = 32
concurrent_requests_per_domain = 16
download_delay = 1
randomize_download_delay = 0.5
```

### Scheduler Performance Settings

```python
# High-throughput scheduler configuration
class PerformanceConfig(SchedulerConfig):
    BATCH_SIZE = 50  # Larger batches
    MAX_CONCURRENT_JOBS_PER_SERVICE = 6  # More concurrent jobs
    CHECK_INTERVAL = 5  # More frequent checks
    HEALTH_CHECK_TIMEOUT = 3  # Faster health checks
    SERVICE_DISCOVERY_INTERVAL = 30  # More frequent service discovery
```

### Database Performance Tuning

```sql
-- Optimize onm_phrases table for high-volume updates
CREATE INDEX CONCURRENTLY idx_phrases_status_priority_created 
ON onm_phrases(status, priority DESC, created_at) 
WHERE status IN ('active', 'processing');

CREATE INDEX CONCURRENTLY idx_phrases_worker_timeout 
ON onm_phrases(assigned_worker_id, processing_timeout) 
WHERE assigned_worker_id IS NOT NULL;

-- Partition table by creation date (for very large datasets)
CREATE TABLE onm_phrases_2024_01 PARTITION OF onm_phrases
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Optimize function performance
CREATE OR REPLACE FUNCTION claim_phrases_for_worker_optimized(
    worker_id uuid, 
    batch_size integer DEFAULT 10,
    timeout_minutes integer DEFAULT 30
) RETURNS TABLE(phrase_id integer, phrase_text character varying)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Use advisory locks for better concurrency
    PERFORM pg_advisory_lock(hashtext('claim_phrases'));
    
    RETURN QUERY
    UPDATE onm_phrases
    SET status = 'processing',
        assigned_worker_id = worker_id,
        assigned_at = now(),
        processing_timeout = now() + (timeout_minutes || ' minutes')::INTERVAL,
        modified_at = now()
    WHERE id IN (
        SELECT p.id
        FROM onm_phrases p
        WHERE p.status = 'active'
        ORDER BY p.priority DESC, p.created_at ASC
        LIMIT batch_size
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, phrases;
    
    PERFORM pg_advisory_unlock(hashtext('claim_phrases'));
END;
$$;
```

### Monitoring Configuration

```yaml
# Prometheus monitoring configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    
    scrape_configs:
    - job_name: 'scrapyd'
      static_configs:
      - targets: ['scrapyd-service:6800']
      metrics_path: /metrics
      scrape_interval: 30s
    
    - job_name: 'scheduler'
      static_configs:
      - targets: ['scheduler-service:8080']
      metrics_path: /metrics
      scrape_interval: 15s
```

This configuration guide provides comprehensive coverage of all system components. Adjust settings based on your specific infrastructure and performance requirements. 