# API Documentation

This document provides comprehensive API reference for the ONM Crawler system, including the Job Scheduler API and Scrapyd API endpoints.

## 📋 Table of Contents

- [Job Scheduler API](#job-scheduler-api)
- [Scrapyd API](#scrapyd-api)
- [Authentication](#authentication)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

## 🎯 Job Scheduler API

The Job Scheduler provides a REST API for monitoring and controlling the distributed crawling system.

### Base URL
```
Development: http://localhost:8080
Production: http://your-domain/scheduler
```

### Endpoints

#### 1. Health Check

```http
GET /health
```

**Description**: Check the health status of the job scheduler.

**Response**:
```json
{
  "status": "healthy",
  "scrapyd_services": 4,
  "active_jobs": 12,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Status Codes**:
- `200 OK` - Service is healthy
- `503 Service Unavailable` - Service is unhealthy

---

#### 2. System Statistics

```http
GET /stats
```

**Description**: Get overall system statistics and performance metrics.

**Response**:
```json
{
  "service_loads": {
    "http://scrapyd-service-1:6800": 3,
    "http://scrapyd-service-2:6800": 2,
    "http://scrapyd-service-3:6800": 4,
    "http://scrapyd-service-4:6800": 1
  },
  "active_jobs": 10,
  "scrapyd_services": [
    "http://scrapyd-service-1:6800",
    "http://scrapyd-service-2:6800",
    "http://scrapyd-service-3:6800",
    "http://scrapyd-service-4:6800"
  ],
  "total_phrases_processed": 15420,
  "phrases_processed_last_hour": 1350,
  "average_job_duration": 125.5,
  "system_uptime": 86400
}
```

---

#### 3. Service Status

```http
GET /services
```

**Description**: Get the status of all Scrapyd services in the cluster.

**Response**:
```json
{
  "services": [
    {
      "url": "http://scrapyd-service-1:6800",
      "status": "healthy",
      "load": 3,
      "last_check": "2024-01-15T10:29:45Z",
      "response_time": 0.025
    },
    {
      "url": "http://scrapyd-service-2:6800",
      "status": "healthy",
      "load": 2,
      "last_check": "2024-01-15T10:29:45Z",
      "response_time": 0.031
    },
    {
      "url": "http://scrapyd-service-3:6800",
      "status": "unhealthy",
      "load": 0,
      "last_check": "2024-01-15T10:29:45Z",
      "error": "Connection timeout"
    },
    {
      "url": "http://scrapyd-service-4:6800",
      "status": "healthy",
      "load": 1,
      "last_check": "2024-01-15T10:29:45Z",
      "response_time": 0.019
    }
  ],
  "healthy_count": 3,
  "total_count": 4
}
```

**Status Values**:
- `healthy` - Service is responding normally
- `unhealthy` - Service is not responding or returning errors
- `unreachable` - Cannot connect to service

---

#### 4. Active Jobs

```http
GET /jobs
```

**Description**: Get details of all currently active crawling jobs.

**Response**:
```json
{
  "active_jobs": {
    "job-uuid-1": {
      "service": "http://scrapyd-service-1:6800",
      "spider": "google",
      "phrases": ["phrase 1", "phrase 2", "phrase 3"],
      "phrase_count": 3,
      "started_at": "2024-01-15T10:25:00Z",
      "status": "running",
      "duration": 300
    },
    "job-uuid-2": {
      "service": "http://scrapyd-service-2:6800",
      "spider": "bing",
      "phrases": ["phrase 4", "phrase 5"],
      "phrase_count": 2,
      "started_at": "2024-01-15T10:26:30Z",
      "status": "running",
      "duration": 210
    }
  },
  "total_active_jobs": 2
}
```

---

#### 5. Job Details

```http
GET /jobs/{job_id}
```

**Description**: Get detailed information about a specific job.

**Parameters**:
- `job_id` (string): The unique identifier of the job

**Response**:
```json
{
  "job_id": "job-uuid-1",
  "service": "http://scrapyd-service-1:6800",
  "spider": "google",
  "phrases": ["phrase 1", "phrase 2", "phrase 3"],
  "phrase_count": 3,
  "started_at": "2024-01-15T10:25:00Z",
  "status": "running",
  "duration": 300,
  "estimated_completion": "2024-01-15T10:32:00Z",
  "progress": {
    "processed": 1,
    "remaining": 2,
    "percentage": 33.3
  }
}
```

**Status Codes**:
- `200 OK` - Job found
- `404 Not Found` - Job not found

---

#### 6. Database Statistics

```http
GET /database/stats
```

**Description**: Get phrase database statistics.

**Response**:
```json
{
  "phrase_status": {
    "active": 1250,
    "processing": 150,
    "completed": 3800,
    "failed": 50,
    "inactive": 150
  },
  "total_phrases": 5400,
  "completed_last_hour": 1350,
  "failed_last_hour": 25,
  "average_processing_time": 145.2,
  "retry_queue_size": 75
}
```

---

#### 7. Manual Job Scheduling

```http
POST /jobs/schedule
```

**Description**: Manually schedule a crawling job with specific phrases.

**Request Body**:
```json
{
  "phrases": ["manual phrase 1", "manual phrase 2", "manual phrase 3"],
  "spider": "google",
  "priority": "high",
  "service": "auto"
}
```

**Parameters**:
- `phrases` (array): List of phrases to crawl
- `spider` (string): Spider type (`google` or `bing`)
- `priority` (string): Job priority (`low`, `medium`, `high`)
- `service` (string): Target service URL or `auto` for automatic selection

**Response**:
```json
{
  "job_id": "manual-job-uuid",
  "status": "scheduled",
  "service": "http://scrapyd-service-2:6800",
  "phrase_count": 3,
  "estimated_start": "2024-01-15T10:31:00Z"
}
```

**Status Codes**:
- `201 Created` - Job scheduled successfully
- `400 Bad Request` - Invalid request data
- `503 Service Unavailable` - No healthy services available

---

#### 8. Job Cancellation

```http
DELETE /jobs/{job_id}
```

**Description**: Cancel a running or pending job.

**Parameters**:
- `job_id` (string): The unique identifier of the job

**Response**:
```json
{
  "job_id": "job-uuid-1",
  "status": "cancelled",
  "cancelled_at": "2024-01-15T10:30:00Z"
}
```

**Status Codes**:
- `200 OK` - Job cancelled successfully
- `404 Not Found` - Job not found
- `409 Conflict` - Job cannot be cancelled (already completed)

---

## 🕷️ Scrapyd API

Scrapyd provides its own REST API for direct spider management. These endpoints are accessed through individual Scrapyd instances.

### Base URL
```
Development: http://localhost:6801-6804
Production: http://your-domain/scrapyd
```

### Core Endpoints

#### 1. Daemon Status

```http
GET /daemonstatus.json
```

**Description**: Get the status of the Scrapyd daemon.

**Response**:
```json
{
  "status": "ok",
  "running": 2,
  "pending": 1,
  "finished": 15,
  "node_name": "scrapyd-pod-1"
}
```

---

#### 2. Schedule Spider

```http
POST /schedule.json
```

**Description**: Schedule a spider to run.

**Form Data**:
- `project` (string): Project name
- `spider` (string): Spider name
- `jobid` (string, optional): Custom job ID
- `phrases` (string): Comma-separated phrases to crawl
- `worker_id` (string): Worker identifier
- `page_request` (string): Number of pages to request

**Response**:
```json
{
  "status": "ok",
  "jobid": "26d1b1a6fcaf11e1b0090800272a6d06"
}
```

---

#### 3. List Jobs

```http
GET /listjobs.json?project=crawler
```

**Description**: List all jobs for a project.

**Parameters**:
- `project` (string): Project name

**Response**:
```json
{
  "status": "ok",
  "pending": [
    {
      "id": "78391cc0fcaf11e1b0090800272a6d06",
      "spider": "google",
      "project": "crawler"
    }
  ],
  "running": [
    {
      "id": "422e608f9f28cef127b3d5ef93fe9399",
      "spider": "bing", 
      "project": "crawler",
      "pid": 8394,
      "start_time": "2024-01-15 10:25:35.033455"
    }
  ],
  "finished": [
    {
      "id": "2f16646cfcaf11e1b0090800272a6d06",
      "spider": "google",
      "project": "crawler", 
      "start_time": "2024-01-15 10:20:35.033455",
      "end_time": "2024-01-15 10:23:18.033455"
    }
  ]
}
```

---

#### 4. Cancel Job

```http
POST /cancel.json
```

**Description**: Cancel a running or pending job.

**Form Data**:
- `project` (string): Project name
- `job` (string): Job ID

**Response**:
```json
{
  "status": "ok",
  "prevstate": "running"
}
```

---

#### 5. List Spiders

```http
GET /listspiders.json?project=crawler
```

**Description**: List all spiders in a project.

**Response**:
```json
{
  "status": "ok", 
  "spiders": ["google", "bing"]
}
```

---

## 🔐 Authentication

Currently, the system does not implement authentication. For production deployments, consider implementing:

### API Key Authentication

```http
GET /stats
Authorization: Bearer your-api-key
```

### JWT Token Authentication

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "secure_password"
}
```

**Response**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

## ⚠️ Error Handling

### Standard Error Response Format

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request is invalid or malformed",
    "details": "Field 'phrases' is required but was not provided",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Request data is invalid or malformed |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

## ⏱️ Rate Limiting

### Default Limits

- **Job Scheduler API**: 100 requests/minute per IP
- **Scrapyd API**: 60 requests/minute per IP
- **Job Scheduling**: 10 jobs/minute per user

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 85
X-RateLimit-Reset: 1642248600
```

## 📝 Examples

### Python Client Example

```python
import requests
import time

class CrawlerClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        
    def get_health(self):
        """Get scheduler health status."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
        
    def get_stats(self):
        """Get system statistics."""
        response = requests.get(f"{self.base_url}/stats")
        return response.json()
        
    def schedule_job(self, phrases, spider="google"):
        """Schedule a manual crawling job."""
        data = {
            "phrases": phrases,
            "spider": spider,
            "priority": "medium",
            "service": "auto"
        }
        response = requests.post(f"{self.base_url}/jobs/schedule", json=data)
        return response.json()
        
    def wait_for_job(self, job_id, timeout=300):
        """Wait for a job to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = requests.get(f"{self.base_url}/jobs/{job_id}")
            
            if response.status_code == 404:
                return {"status": "completed"}
                
            job_data = response.json()
            if job_data["status"] in ["completed", "failed"]:
                return job_data
                
            time.sleep(10)
            
        return {"status": "timeout"}

# Usage example
client = CrawlerClient()

# Check system health
health = client.get_health()
print(f"System status: {health['status']}")

# Get statistics
stats = client.get_stats()
print(f"Active jobs: {stats['active_jobs']}")

# Schedule a job
phrases = ["example phrase 1", "example phrase 2", "example phrase 3"]
job = client.schedule_job(phrases)
print(f"Scheduled job: {job['job_id']}")

# Wait for completion
result = client.wait_for_job(job['job_id'])
print(f"Job result: {result['status']}")
```

### cURL Examples

#### Check Health
```bash
curl -X GET http://localhost:8080/health
```

#### Get Statistics
```bash
curl -X GET http://localhost:8080/stats | jq .
```

#### Schedule Job
```bash
curl -X POST http://localhost:8080/jobs/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "phrases": ["test phrase 1", "test phrase 2"],
    "spider": "google",
    "priority": "high"
  }'
```

#### Cancel Job
```bash
curl -X DELETE http://localhost:8080/jobs/job-uuid-123
```

#### Direct Scrapyd Interaction
```bash
# Schedule job directly on Scrapyd
curl -X POST http://localhost:6801/schedule.json \
  -d project=crawler \
  -d spider=google \
  -d phrases="direct phrase 1,direct phrase 2" \
  -d worker_id=manual-worker

# Check job status
curl http://localhost:6801/listjobs.json?project=crawler | jq .
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class CrawlerAPI {
    constructor(baseURL = 'http://localhost:8080') {
        this.client = axios.create({
            baseURL,
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }
    
    async getHealth() {
        const response = await this.client.get('/health');
        return response.data;
    }
    
    async getStats() {
        const response = await this.client.get('/stats');
        return response.data;
    }
    
    async scheduleJob(phrases, spider = 'google') {
        const data = {
            phrases,
            spider,
            priority: 'medium',
            service: 'auto'
        };
        
        const response = await this.client.post('/jobs/schedule', data);
        return response.data;
    }
    
    async getJobStatus(jobId) {
        try {
            const response = await this.client.get(`/jobs/${jobId}`);
            return response.data;
        } catch (error) {
            if (error.response?.status === 404) {
                return { status: 'completed' };
            }
            throw error;
        }
    }
}

// Usage
(async () => {
    const api = new CrawlerAPI();
    
    try {
        // Check health
        const health = await api.getHealth();
        console.log('System health:', health.status);
        
        // Schedule job
        const job = await api.scheduleJob(['nodejs test phrase']);
        console.log('Job scheduled:', job.job_id);
        
        // Monitor job
        let jobStatus;
        do {
            await new Promise(resolve => setTimeout(resolve, 5000));
            jobStatus = await api.getJobStatus(job.job_id);
            console.log('Job status:', jobStatus.status);
        } while (jobStatus.status === 'running');
        
    } catch (error) {
        console.error('API Error:', error.message);
    }
})();
```

This API documentation provides comprehensive coverage of all available endpoints and includes practical examples for integration with the ONM Crawler system. 