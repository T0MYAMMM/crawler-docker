# Deployment Guide

This guide provides detailed instructions for deploying the ONM Crawler containerized Scrapyd system in both development and production environments.

## 📋 Prerequisites

### System Requirements

**Development Environment:**
- Docker 20.10+ and Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 4 CPU cores minimum
- 50GB free disk space

**Production Environment:**
- Kubernetes cluster (1.23+)
- LoadBalancer service support
- Persistent volume support
- 32GB RAM across cluster
- 16 CPU cores across cluster
- 200GB persistent storage

### Database Setup

1. **PostgreSQL Configuration**
```sql
-- Create database and user
CREATE DATABASE onm;
CREATE USER onm_admin WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE onm TO onm_admin;

-- Connect to onm database and create tables
\c onm

-- Ensure onm_phrases table exists with required functions
-- (Your existing table structure is assumed to be in place)
```

2. **Environment Variables**
```bash
# Database configuration
export PG_HOST="your-postgres-host"
export PG_DATABASE="onm"
export PG_USER="onm_admin"
export PG_PASSWORD="your_secure_password"

# Registry configuration (for production)
export DOCKER_REGISTRY="your-registry.com"
export IMAGE_TAG="latest"
```

## 🔧 Development Deployment

### 1. Project Setup

```bash
# Clone the repository
git clone <your-repo-url> crawler-cluster
cd crawler-cluster

# Create environment file
cat > .env << EOF
PG_HOST=postgres
PG_DATABASE=onm
PG_USER=onm_admin
PG_PASSWORD=onmdb
BOOTSTRAP_SERVER=your-kafka-server:9092
SCRAPYD_SERVICES=http://scrapyd-1:6800,http://scrapyd-2:6800,http://scrapyd-3:6800,http://scrapyd-4:6800
EOF
```

### 2. Build and Start Services

```bash
# Build all images
docker-compose -f docker-compose.scrapyd.yml build

# Start the cluster
docker-compose -f docker-compose.scrapyd.yml up -d

# Check service health
docker-compose -f docker-compose.scrapyd.yml ps
```

### 3. Initialize and Deploy Spiders

```bash
# Wait for services to be ready
sleep 30

# Deploy spider project to all Scrapyd instances
for port in 6801 6802 6803 6804; do
    curl -X POST http://localhost:$port/addversion.json \
        -F project=crawler \
        -F version=1.0 \
        -F egg=@deployments/crawler.egg
done
```

### 4. Verify Deployment

```bash
# Check Scrapyd instances
curl http://localhost:6801/daemonstatus.json
curl http://localhost:6802/daemonstatus.json
curl http://localhost:6803/daemonstatus.json
curl http://localhost:6804/daemonstatus.json

# Check job scheduler
curl http://localhost:8080/health

# Check database connectivity
docker-compose exec postgres psql -U onm_admin -d onm -c "SELECT COUNT(*) FROM onm_phrases;"
```

### 5. Access Web Interfaces

- **Scrapyd Web UI**: 
  - Instance 1: http://localhost:6801
  - Instance 2: http://localhost:6802
  - Instance 3: http://localhost:6803
  - Instance 4: http://localhost:6804
- **Job Scheduler API**: http://localhost:8080
- **Unified Interface**: http://localhost:80

## 🚀 Production Deployment

### 1. Image Preparation

```bash
# Build production images
docker build -f dockerfiles/Dockerfile.scrapyd -t ${DOCKER_REGISTRY}/crawler-scrapyd:${IMAGE_TAG} .
docker build -f dockerfiles/Dockerfile.scheduler -t ${DOCKER_REGISTRY}/crawler-scheduler:${IMAGE_TAG} .

# Push to registry
docker push ${DOCKER_REGISTRY}/crawler-scrapyd:${IMAGE_TAG}
docker push ${DOCKER_REGISTRY}/crawler-scheduler:${IMAGE_TAG}
```

### 2. Kubernetes Configuration

```bash
# Create namespace
kubectl create namespace crawler-system

# Create secrets
kubectl create secret generic crawler-db-secret \
    --from-literal=host="${PG_HOST}" \
    --from-literal=database="${PG_DATABASE}" \
    --from-literal=username="${PG_USER}" \
    --from-literal=password="${PG_PASSWORD}" \
    --namespace=crawler-system

# Create configmap for Scrapyd configuration
kubectl create configmap scrapyd-config \
    --from-file=scrapyd.conf \
    --namespace=crawler-system
```

### 3. Deploy to Kubernetes

```bash
# Update image references in deployment file
sed -i "s|your-registry/crawler-scrapyd:latest|${DOCKER_REGISTRY}/crawler-scrapyd:${IMAGE_TAG}|g" deployments/k8s-scrapyd-deployment.yml
sed -i "s|your-registry/crawler-scheduler:latest|${DOCKER_REGISTRY}/crawler-scheduler:${IMAGE_TAG}|g" deployments/k8s-scrapyd-deployment.yml

# Apply deployment
kubectl apply -f deployments/k8s-scrapyd-deployment.yml --namespace=crawler-system

# Wait for deployment to complete
kubectl rollout status deployment/scrapyd-cluster --namespace=crawler-system
kubectl rollout status deployment/job-scheduler --namespace=crawler-system
```

### 4. Configure Ingress (Optional)

```yaml
# ingress.yml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: crawler-ingress
  namespace: crawler-system
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - crawler.yourdomain.com
    secretName: crawler-tls
  rules:
  - host: crawler.yourdomain.com
    http:
      paths:
      - path: /scrapyd
        pathType: Prefix
        backend:
          service:
            name: scrapyd-service
            port:
              number: 6800
      - path: /scheduler
        pathType: Prefix
        backend:
          service:
            name: scheduler-service
            port:
              number: 8080
```

```bash
kubectl apply -f ingress.yml
```

### 5. Horizontal Pod Autoscaling

```yaml
# hpa.yml
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
  maxReplicas: 12
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
```

```bash
kubectl apply -f hpa.yml
```

## 🔧 Configuration Management

### Environment-Specific Configurations

**Development (`config/dev.env`)**:
```bash
PG_HOST=postgres
DEBUG=true
LOG_LEVEL=DEBUG
BATCH_SIZE=10
MAX_CONCURRENT_JOBS=2
```

**Staging (`config/staging.env`)**:
```bash
PG_HOST=staging-postgres.example.com
DEBUG=false
LOG_LEVEL=INFO
BATCH_SIZE=20
MAX_CONCURRENT_JOBS=3
```

**Production (`config/prod.env`)**:
```bash
PG_HOST=prod-postgres.example.com
DEBUG=false
LOG_LEVEL=WARNING
BATCH_SIZE=30
MAX_CONCURRENT_JOBS=4
```

### Kubernetes Secrets Management

```bash
# Create environment-specific secrets
kubectl create secret generic crawler-config-prod \
    --from-env-file=config/prod.env \
    --namespace=crawler-system

# Update deployment to use secrets
kubectl patch deployment scrapyd-cluster \
    --namespace=crawler-system \
    --patch='{"spec":{"template":{"spec":{"containers":[{"name":"scrapyd","envFrom":[{"secretRef":{"name":"crawler-config-prod"}}]}]}}}}'
```

## 📊 Monitoring Setup

### 1. Prometheus Monitoring

```yaml
# monitoring.yml
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: crawler-monitoring
  namespace: crawler-system
spec:
  selector:
    matchLabels:
      app: scrapyd
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

### 2. Grafana Dashboard

```bash
# Add Grafana dashboard for crawler metrics
kubectl create configmap crawler-dashboard \
    --from-file=deployments/grafana-dashboard.json \
    --namespace=monitoring
```

### 3. Alerting Rules

```yaml
# alerts.yml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: crawler-alerts
  namespace: crawler-system
spec:
  groups:
  - name: crawler.rules
    rules:
    - alert: ScrapydInstanceDown
      expr: up{job="scrapyd"} == 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Scrapyd instance is down"
        description: "Scrapyd instance {{ $labels.instance }} has been down for more than 5 minutes."
    
    - alert: LowPhraseProcessingRate
      expr: rate(phrases_processed_total[5m]) < 0.1
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "Low phrase processing rate"
        description: "Phrase processing rate is below expected threshold."
```

## 🔄 Deployment Automation

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy Crawler

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push images
      run: |
        docker build -f dockerfiles/Dockerfile.scrapyd -t ${{ secrets.REGISTRY }}/crawler-scrapyd:${{ github.sha }} .
        docker build -f dockerfiles/Dockerfile.scheduler -t ${{ secrets.REGISTRY }}/crawler-scheduler:${{ github.sha }} .
        docker push ${{ secrets.REGISTRY }}/crawler-scrapyd:${{ github.sha }}
        docker push ${{ secrets.REGISTRY }}/crawler-scheduler:${{ github.sha }}
    
    - name: Deploy to Kubernetes
      run: |
        sed -i "s|your-registry/crawler-scrapyd:latest|${{ secrets.REGISTRY }}/crawler-scrapyd:${{ github.sha }}|g" deployments/k8s-scrapyd-deployment.yml
        sed -i "s|your-registry/crawler-scheduler:latest|${{ secrets.REGISTRY }}/crawler-scheduler:${{ github.sha }}|g" deployments/k8s-scrapyd-deployment.yml
        kubectl apply -f deployments/k8s-scrapyd-deployment.yml --namespace=crawler-system
```

### Helm Chart (Advanced)

```yaml
# helm/crawler/Chart.yaml
apiVersion: v2
name: crawler
description: ONM Crawler Helm Chart
version: 1.0.0
appVersion: "1.0.0"

# helm/crawler/values.yaml
scrapyd:
  replicaCount: 4
  image:
    repository: your-registry/crawler-scrapyd
    tag: latest
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"

scheduler:
  image:
    repository: your-registry/crawler-scheduler
    tag: latest
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "200m"
```

```bash
# Deploy using Helm
helm install crawler ./helm/crawler --namespace=crawler-system
```

## 🔍 Validation and Testing

### 1. Smoke Tests

```bash
# Test script: test-deployment.sh
#!/bin/bash

echo "Running deployment smoke tests..."

# Test Scrapyd instances
for service in scrapyd-1 scrapyd-2 scrapyd-3 scrapyd-4; do
    echo "Testing $service..."
    curl -f http://$service:6800/daemonstatus.json || exit 1
done

# Test job scheduler
echo "Testing job scheduler..."
curl -f http://job-scheduler:8080/health || exit 1

# Test database connectivity
echo "Testing database..."
kubectl exec -it deployment/job-scheduler -- python -c "
import psycopg2
from config.settings import PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD
conn = psycopg2.connect(host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD)
print('Database connection successful')
"

echo "All tests passed!"
```

### 2. Load Testing

```bash
# Load test with sample phrases
kubectl exec -it deployment/job-scheduler -- python -c "
from job_scheduler import JobScheduler
scheduler = JobScheduler(['http://scrapyd-service:6800'])
for i in range(10):
    phrases = [f'test phrase {j}' for j in range(30)]
    scheduler.schedule_job('http://scrapyd-service:6800', phrases)
    print(f'Scheduled batch {i+1}')
"
```

## 🔧 Maintenance

### Regular Tasks

1. **Log Rotation**
```bash
# Clean old logs (run weekly)
kubectl exec -it deployment/scrapyd-cluster -- find /app/logs -name "*.log" -mtime +7 -delete
```

2. **Database Maintenance**
```sql
-- Clean old completed phrases (run daily)
UPDATE onm_phrases 
SET status = 'inactive' 
WHERE status = 'completed' 
AND last_crawled_at < now() - INTERVAL '24 hours';
```

3. **Image Updates**
```bash
# Update images (automated via CI/CD)
kubectl set image deployment/scrapyd-cluster scrapyd=your-registry/crawler-scrapyd:new-tag --namespace=crawler-system
kubectl rollout status deployment/scrapyd-cluster --namespace=crawler-system
```

### Backup and Recovery

```bash
# Backup database
kubectl exec -it postgres-pod -- pg_dump -U onm_admin onm > backup-$(date +%Y%m%d).sql

# Backup configurations
kubectl get configmap,secret -n crawler-system -o yaml > config-backup.yml
```

This deployment guide provides comprehensive instructions for both development and production environments. Follow the steps sequentially and adjust configurations based on your specific infrastructure requirements. 