# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the ONM Crawler containerized Scrapyd deployment system.

## 📋 Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
- [System Health Checks](#system-health-checks)
- [Performance Issues](#performance-issues)
- [Network Problems](#network-problems)
- [Database Issues](#database-issues)
- [Container Issues](#container-issues)
- [Kubernetes Issues](#kubernetes-issues)
- [Log Analysis](#log-analysis)
- [Recovery Procedures](#recovery-procedures)

## 🩺 Quick Diagnostics

### Health Check Script

```bash
#!/bin/bash
# health-check.sh - Quick system diagnostics

echo "=== ONM Crawler System Health Check ==="
echo "Timestamp: $(date)"
echo

# Check Scrapyd instances
echo "🕷️  Checking Scrapyd instances..."
for port in 6801 6802 6803 6804; do
    if curl -s http://localhost:$port/daemonstatus.json > /dev/null; then
        echo "✅ Scrapyd-$((port-6800)) is healthy"
        status=$(curl -s http://localhost:$port/daemonstatus.json | jq -r .status)
        running=$(curl -s http://localhost:$port/daemonstatus.json | jq -r .running)
        echo "   Status: $status, Running jobs: $running"
    else
        echo "❌ Scrapyd-$((port-6800)) is unreachable"
    fi
done

# Check job scheduler
echo
echo "📊 Checking Job Scheduler..."
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ Job Scheduler is healthy"
    health=$(curl -s http://localhost:8080/health | jq .)
    echo "   Details: $health"
else
    echo "❌ Job Scheduler is unreachable"
fi

# Check database
echo
echo "🗄️  Checking Database..."
if command -v psql > /dev/null; then
    if psql -h localhost -U onm_admin -d onm -c "SELECT 1;" > /dev/null 2>&1; then
        echo "✅ Database is accessible"
        phrases_count=$(psql -h localhost -U onm_admin -d onm -t -c "SELECT COUNT(*) FROM onm_phrases;")
        active_count=$(psql -h localhost -U onm_admin -d onm -t -c "SELECT COUNT(*) FROM onm_phrases WHERE status='active';")
        processing_count=$(psql -h localhost -U onm_admin -d onm -t -c "SELECT COUNT(*) FROM onm_phrases WHERE status='processing';")
        echo "   Total phrases: $phrases_count"
        echo "   Active phrases: $active_count"
        echo "   Processing phrases: $processing_count"
    else
        echo "❌ Database is not accessible"
    fi
else
    echo "⚠️  psql not available for database check"
fi

# Check Docker containers
echo
echo "🐳 Checking Docker containers..."
if command -v docker > /dev/null; then
    running_containers=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(scrapyd|scheduler)" || echo "No crawler containers running")
    echo "$running_containers"
else
    echo "⚠️  Docker not available"
fi

# Check Kubernetes pods (if kubectl available)
echo
echo "☸️  Checking Kubernetes pods..."
if command -v kubectl > /dev/null; then
    pods=$(kubectl get pods -n crawler-system 2>/dev/null || echo "Kubernetes not configured or namespace not found")
    echo "$pods"
else
    echo "⚠️  kubectl not available"
fi

echo
echo "=== Health Check Complete ==="
```

### System Status Commands

```bash
# Quick status overview
curl http://localhost:8080/stats | jq .

# Database phrase status
psql -h localhost -U onm_admin -d onm -c "
SELECT status, COUNT(*) as count 
FROM onm_phrases 
GROUP BY status 
ORDER BY count DESC;"

# Container resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Kubernetes pod status
kubectl get pods -n crawler-system -o wide
```

## 🚨 Common Issues

### 1. No Phrases Being Processed

**Symptoms:**
- Job scheduler shows healthy but no active jobs
- Database shows phrases in 'active' status but not processing
- Scrapyd instances are idle

**Causes & Solutions:**

#### A. Database Connection Issues
```bash
# Check database connectivity
psql -h localhost -U onm_admin -d onm -c "SELECT version();"

# Test phrase claiming function
psql -h localhost -U onm_admin -d onm -c "
SELECT * FROM claim_phrases_for_worker('test-worker'::uuid, 5, 30);"
```

**Solution:**
```bash
# Verify database credentials
echo $PG_PASSWORD
echo $PG_HOST

# Check if database functions exist
psql -h localhost -U onm_admin -d onm -c "
\df claim_phrases_for_worker
\df complete_phrase"
```

#### B. Phrase Activation Issues
```sql
-- Check phrase status distribution
SELECT status, COUNT(*) FROM onm_phrases GROUP BY status;

-- Manually activate phrases
UPDATE onm_phrases 
SET status = 'active', modified_at = now() 
WHERE status = 'inactive' 
LIMIT 100;
```

#### C. Scheduler Configuration Issues
```bash
# Check scheduler logs
docker logs job-scheduler

# Verify environment variables
docker exec job-scheduler env | grep -E "(SCRAPYD|BATCH|PG_)"

# Test Scrapyd connectivity from scheduler
docker exec job-scheduler curl http://scrapyd-1:6800/daemonstatus.json
```

### 2. High Memory Usage

**Symptoms:**
- Containers being killed due to OOM
- Slow response times
- System becomes unresponsive

**Diagnosis:**
```bash
# Check memory usage
docker stats --no-stream
free -h
top -o %MEM

# Check for memory leaks in logs
docker logs scrapyd-1 | grep -i "memory\|oom"
kubectl describe pod scrapyd-cluster-xxx | grep -A 10 "Events:"
```

**Solutions:**

#### A. Reduce Batch Size
```bash
# Update environment variable
kubectl set env deployment/job-scheduler BATCH_SIZE=15 -n crawler-system

# Or update Docker Compose
docker-compose exec job-scheduler env BATCH_SIZE=15
```

#### B. Increase Memory Limits
```yaml
# In Kubernetes deployment
resources:
  limits:
    memory: "2Gi"
  requests:
    memory: "1Gi"
```

#### C. Enable Memory Monitoring
```python
# Add to scheduler code
import psutil
import gc

def log_memory_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    logger.info(f"Memory usage: RSS={memory_info.rss/1024/1024:.1f}MB, "
                f"VMS={memory_info.vms/1024/1024:.1f}MB")
    gc.collect()  # Force garbage collection
```

### 3. Scrapyd Instances Not Starting

**Symptoms:**
- Scrapyd containers crash on startup
- HTTP requests to Scrapyd fail
- Health checks fail

**Diagnosis:**
```bash
# Check container logs
docker logs scrapyd-1

# Check configuration
docker exec scrapyd-1 cat /etc/scrapyd/scrapyd.conf

# Test configuration syntax
docker exec scrapyd-1 scrapyd --help
```

**Common Causes & Solutions:**

#### A. Configuration Errors
```bash
# Validate scrapyd.conf syntax
# Check for typos in configuration file

# Test with minimal configuration
cat > scrapyd-minimal.conf << EOF
[scrapyd]
bind_address = 0.0.0.0
http_port = 6800
max_proc = 2
EOF
```

#### B. Port Conflicts
```bash
# Check if port is already in use
netstat -tlnp | grep 6800
lsof -i :6800

# Use different ports
docker run -p 6805:6800 your-scrapyd-image
```

#### C. Permission Issues
```bash
# Check file permissions
docker exec scrapyd-1 ls -la /app/logs /app/eggs

# Fix permissions
docker exec scrapyd-1 chown -R scrapyd:scrapyd /app
```

### 4. Jobs Stuck in Pending State

**Symptoms:**
- Jobs scheduled but never start running
- Scrapyd shows jobs in pending queue indefinitely
- No spider processes launched

**Diagnosis:**
```bash
# Check Scrapyd job queue
curl http://localhost:6801/listjobs.json?project=crawler | jq .

# Check process limits
curl http://localhost:6801/daemonstatus.json | jq .

# Check system resources
docker exec scrapyd-1 ps aux
docker exec scrapyd-1 free -m
```

**Solutions:**

#### A. Increase Process Limits
```ini
# In scrapyd.conf
[scrapyd]
max_proc = 6
max_proc_per_cpu = 3
```

#### B. Clear Stuck Jobs
```bash
# Cancel all pending jobs
for job_id in $(curl -s http://localhost:6801/listjobs.json?project=crawler | jq -r '.pending[].id'); do
    curl -X POST http://localhost:6801/cancel.json -d "project=crawler&job=$job_id"
done
```

#### C. Restart Scrapyd Services
```bash
# Docker Compose
docker-compose restart scrapyd-1 scrapyd-2 scrapyd-3 scrapyd-4

# Kubernetes
kubectl rollout restart deployment/scrapyd-cluster -n crawler-system
```

### 5. Database Deadlocks

**Symptoms:**
- Frequent timeout errors in logs
- Jobs failing to claim phrases
- Database connection errors

**Diagnosis:**
```sql
-- Check for locks
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.GRANTED;
```

**Solutions:**

#### A. Optimize Phrase Claiming Function
```sql
-- Use advisory locks to prevent contention
CREATE OR REPLACE FUNCTION claim_phrases_for_worker_safe(
    worker_id uuid,
    batch_size integer DEFAULT 10,
    timeout_minutes integer DEFAULT 30
) RETURNS TABLE(phrase_id integer, phrase_text character varying)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Get advisory lock
    IF NOT pg_try_advisory_lock(hashtext('claim_phrases')) THEN
        RETURN; -- Another process is claiming phrases
    END IF;
    
    BEGIN
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
    EXCEPTION
        WHEN OTHERS THEN
            PERFORM pg_advisory_unlock(hashtext('claim_phrases'));
            RAISE;
    END;
    
    PERFORM pg_advisory_unlock(hashtext('claim_phrases'));
END;
$$;
```

#### B. Reduce Connection Pool Size
```python
# In database configuration
MIN_CONNECTIONS = 3
MAX_CONNECTIONS = 10
```

#### C. Add Connection Timeout
```python
# In database connection code
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
        cursor_factory=RealDictCursor,
        connect_timeout=10,
        application_name='crawler-scheduler'
    )
```

## 📊 System Health Checks

### Automated Health Monitoring

```python
#!/usr/bin/env python3
# health_monitor.py - Continuous health monitoring

import time
import requests
import psycopg2
import logging
from datetime import datetime
from typing import Dict, List

class HealthMonitor:
    def __init__(self):
        self.setup_logging()
        self.scrapyd_services = [
            'http://localhost:6801',
            'http://localhost:6802', 
            'http://localhost:6803',
            'http://localhost:6804'
        ]
        self.scheduler_url = 'http://localhost:8080'
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [HealthMonitor] %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def check_scrapyd_health(self, service_url: str) -> Dict:
        """Check individual Scrapyd service health."""
        try:
            response = requests.get(f"{service_url}/daemonstatus.json", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'healthy',
                    'running_jobs': data.get('running', 0),
                    'pending_jobs': data.get('pending', 0),
                    'finished_jobs': data.get('finished', 0),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {'status': 'unhealthy', 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'status': 'unreachable', 'error': str(e)}
            
    def check_scheduler_health(self) -> Dict:
        """Check job scheduler health."""
        try:
            response = requests.get(f"{self.scheduler_url}/health", timeout=5)
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'data': response.json(),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {'status': 'unhealthy', 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'status': 'unreachable', 'error': str(e)}
            
    def check_database_health(self) -> Dict:
        """Check database connectivity and performance."""
        try:
            conn = psycopg2.connect(
                host='localhost',
                database='onm',
                user='onm_admin', 
                password='onmdb',
                connect_timeout=5
            )
            
            start_time = time.time()
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM onm_phrases WHERE status = 'active';")
                active_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM onm_phrases WHERE status = 'processing';")
                processing_count = cursor.fetchone()[0]
                
            response_time = time.time() - start_time
            conn.close()
            
            return {
                'status': 'healthy',
                'active_phrases': active_count,
                'processing_phrases': processing_count,
                'response_time': response_time
            }
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
            
    def run_health_checks(self) -> Dict:
        """Run all health checks and return comprehensive status."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'scrapyd_services': {},
            'scheduler': {},
            'database': {},
            'overall_status': 'healthy'
        }
        
        # Check Scrapyd services
        healthy_services = 0
        for service_url in self.scrapyd_services:
            service_name = service_url.split(':')[-1]
            results['scrapyd_services'][service_name] = self.check_scrapyd_health(service_url)
            if results['scrapyd_services'][service_name]['status'] == 'healthy':
                healthy_services += 1
                
        # Check scheduler
        results['scheduler'] = self.check_scheduler_health()
        
        # Check database
        results['database'] = self.check_database_health()
        
        # Determine overall status
        if healthy_services < len(self.scrapyd_services) // 2:
            results['overall_status'] = 'critical'
        elif (results['scheduler']['status'] != 'healthy' or 
              results['database']['status'] != 'healthy'):
            results['overall_status'] = 'degraded'
        elif healthy_services < len(self.scrapyd_services):
            results['overall_status'] = 'warning'
            
        return results
        
    def monitor_continuously(self, interval: int = 60):
        """Run continuous monitoring."""
        self.logger.info("Starting continuous health monitoring")
        
        while True:
            try:
                results = self.run_health_checks()
                
                if results['overall_status'] != 'healthy':
                    self.logger.warning(f"System status: {results['overall_status']}")
                    
                    # Log specific issues
                    for service, status in results['scrapyd_services'].items():
                        if status['status'] != 'healthy':
                            self.logger.error(f"Scrapyd {service}: {status}")
                            
                    if results['scheduler']['status'] != 'healthy':
                        self.logger.error(f"Scheduler: {results['scheduler']}")
                        
                    if results['database']['status'] != 'healthy':
                        self.logger.error(f"Database: {results['database']}")
                else:
                    self.logger.info("All systems healthy")
                    
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.logger.info("Health monitoring stopped")
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    monitor = HealthMonitor()
    monitor.monitor_continuously()
```

## 🔧 Performance Issues

### Slow Processing Speed

**Diagnosis:**
```bash
# Check processing rates
curl http://localhost:8080/stats | jq '.phrases_processed_last_hour'

# Monitor job durations
curl http://localhost:8080/jobs | jq '.active_jobs[] | {job_id, duration, phrase_count}'

# Check system resources
docker stats --no-stream
```

**Solutions:**

#### A. Optimize Batch Sizes
```bash
# Experiment with different batch sizes
export BATCH_SIZE=20  # Start smaller
export BATCH_SIZE=40  # Or larger

# Monitor impact on performance
watch -n 5 'curl -s http://localhost:8080/stats | jq .phrases_processed_last_hour'
```

#### B. Scale Horizontally
```bash
# Add more Scrapyd instances
docker-compose up --scale scrapyd=6

# Or in Kubernetes
kubectl scale deployment scrapyd-cluster --replicas=8 -n crawler-system
```

#### C. Optimize Database Queries
```sql
-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_phrases_active_priority 
ON onm_phrases(priority DESC, created_at ASC) 
WHERE status = 'active';

-- Analyze query performance
EXPLAIN ANALYZE 
SELECT * FROM claim_phrases_for_worker('test'::uuid, 30, 30);
```

### High CPU Usage

**Diagnosis:**
```bash
# Check CPU usage per container
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Check process details
docker exec scrapyd-1 top -bn1

# Identify bottlenecks
docker exec scrapyd-1 ps aux --sort=-%cpu
```

**Solutions:**

#### A. Reduce Concurrency
```ini
# In scrapyd.conf
[scrapyd]
max_proc = 2
max_proc_per_cpu = 1
concurrent_requests = 8
```

#### B. Add CPU Throttling
```yaml
# In Kubernetes deployment
resources:
  limits:
    cpu: "500m"  # Limit to 0.5 CPU cores
```

#### C. Enable AutoThrottle
```python
# In Scrapy settings
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5
```

## 🔍 Log Analysis

### Important Log Patterns

```bash
# Search for common error patterns
docker logs scrapyd-1 2>&1 | grep -E "(ERROR|CRITICAL|Exception|Failed)"

# Check for memory issues
docker logs scrapyd-1 2>&1 | grep -i "memory\|oom"

# Monitor job completion rates
docker logs job-scheduler 2>&1 | grep "completed\|failed"

# Database connection issues
docker logs job-scheduler 2>&1 | grep -i "database\|connection\|timeout"
```

### Log Analysis Script

```bash
#!/bin/bash
# analyze_logs.sh - Automated log analysis

echo "=== Log Analysis Report ==="
echo "Generated: $(date)"
echo

# Function to count log patterns
count_pattern() {
    local service=$1
    local pattern=$2
    local count=$(docker logs $service 2>&1 | grep -c "$pattern")
    echo "$pattern: $count"
}

# Analyze scheduler logs
echo "📊 Job Scheduler Logs (last 1000 lines):"
docker logs --tail 1000 job-scheduler 2>&1 | {
    echo "  Batch processing:"
    count_pattern job-scheduler "Processing batch"
    count_pattern job-scheduler "completed successfully"
    count_pattern job-scheduler "failed"
    
    echo "  Errors:"
    count_pattern job-scheduler "ERROR"
    count_pattern job-scheduler "Exception"
    count_pattern job-scheduler "timeout"
}

echo

# Analyze Scrapyd logs
for i in {1..4}; do
    echo "🕷️  Scrapyd-$i Logs (last 500 lines):"
    docker logs --tail 500 scrapyd-$i 2>&1 | {
        echo "  Job activity:"
        count_pattern scrapyd-$i "Job started"
        count_pattern scrapyd-$i "Job completed"
        count_pattern scrapyd-$i "Job failed"
        
        echo "  System issues:"
        count_pattern scrapyd-$i "Memory"
        count_pattern scrapyd-$i "ERROR"
        count_pattern scrapyd-$i "Exception"
    }
    echo
done

# Recent critical errors
echo "🚨 Recent Critical Errors:"
for service in job-scheduler scrapyd-1 scrapyd-2 scrapyd-3 scrapyd-4; do
    recent_errors=$(docker logs --since 1h $service 2>&1 | grep -E "(CRITICAL|ERROR)" | tail -3)
    if [ ! -z "$recent_errors" ]; then
        echo "  $service:"
        echo "$recent_errors" | sed 's/^/    /'
        echo
    fi
done

echo "=== Analysis Complete ==="
```

## 🔄 Recovery Procedures

### Automatic Recovery Script

```bash
#!/bin/bash
# auto_recovery.sh - Automated system recovery

set -e

echo "Starting automatic recovery procedures..."

# Function to restart service if unhealthy
restart_if_unhealthy() {
    local service_name=$1
    local health_check_url=$2
    
    echo "Checking $service_name..."
    
    if ! curl -f -s "$health_check_url" > /dev/null; then
        echo "⚠️  $service_name is unhealthy, restarting..."
        
        if command -v docker-compose > /dev/null; then
            docker-compose restart $service_name
        elif command -v kubectl > /dev/null; then
            kubectl rollout restart deployment/$service_name -n crawler-system
        else
            docker restart $service_name
        fi
        
        # Wait for service to recover
        echo "Waiting for $service_name to recover..."
        for i in {1..30}; do
            if curl -f -s "$health_check_url" > /dev/null; then
                echo "✅ $service_name recovered"
                return 0
            fi
            sleep 10
        done
        
        echo "❌ $service_name failed to recover"
        return 1
    else
        echo "✅ $service_name is healthy"
        return 0
    fi
}

# Recovery procedures
echo "1. Checking Scrapyd instances..."
restart_if_unhealthy "scrapyd-1" "http://localhost:6801/daemonstatus.json"
restart_if_unhealthy "scrapyd-2" "http://localhost:6802/daemonstatus.json"
restart_if_unhealthy "scrapyd-3" "http://localhost:6803/daemonstatus.json"
restart_if_unhealthy "scrapyd-4" "http://localhost:6804/daemonstatus.json"

echo "2. Checking job scheduler..."
restart_if_unhealthy "job-scheduler" "http://localhost:8080/health"

echo "3. Cleaning up stuck phrases..."
if command -v psql > /dev/null; then
    psql -h localhost -U onm_admin -d onm -c "
    UPDATE onm_phrases 
    SET status = 'active',
        assigned_worker_id = NULL,
        assigned_at = NULL,
        processing_timeout = NULL,
        modified_at = now()
    WHERE status = 'processing' 
    AND processing_timeout < now() - INTERVAL '1 hour';"
    
    echo "Cleaned up stuck phrases"
fi

echo "4. Clearing old logs..."
find /var/log/crawler -name "*.log" -mtime +7 -delete 2>/dev/null || true
docker system prune -f --volumes --filter until=168h > /dev/null || true

echo "Recovery procedures completed"
```

### Manual Recovery Steps

#### Complete System Reset

```bash
# 1. Stop all services
docker-compose down
# or
kubectl delete namespace crawler-system

# 2. Clean up resources
docker system prune -af
docker volume prune -f

# 3. Reset database (CAUTION: This will lose all data)
psql -h localhost -U onm_admin -d onm -c "
TRUNCATE TABLE onm_phrases RESTART IDENTITY CASCADE;
-- Re-import your phrases here
"

# 4. Restart services
docker-compose up -d
# or
kubectl apply -f deployments/k8s-scrapyd-deployment.yml
```

#### Partial Recovery

```bash
# Reset only processing phrases
psql -h localhost -U onm_admin -d onm -c "
UPDATE onm_phrases 
SET status = 'active',
    assigned_worker_id = NULL,
    assigned_at = NULL,
    processing_timeout = NULL,
    crawl_attempts = 0,
    modified_at = now()
WHERE status IN ('processing', 'failed');"

# Restart only problematic services
docker-compose restart scrapyd-1 job-scheduler

# Clear job queues
for port in 6801 6802 6803 6804; do
    # Cancel all pending jobs
    curl -s http://localhost:$port/listjobs.json?project=crawler | \
    jq -r '.pending[].id' | \
    xargs -I {} curl -X POST http://localhost:$port/cancel.json -d "project=crawler&job={}"
done
```

This troubleshooting guide covers the most common issues and provides systematic approaches to diagnose and resolve problems. Always start with the quick diagnostics before attempting more complex recovery procedures. 