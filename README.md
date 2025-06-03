# ONM Crawler - Containerized Scrapyd Deployment

A distributed web scraping system using Dockerized Scrapyd instances with Kubernetes orchestration for processing 5,400 phrases hourly across multiple search engines.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Central Job Scheduler                     │
│            (Distributes 5.4k phrases)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP API calls
                      │ (sends job batches)
        ┌─────────────┼─────────────┐
        │             │             │
   Scrapyd Pod 1  Scrapyd Pod 2  Scrapyd Pod 3  Scrapyd Pod 4
 ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
 │ Scrapyd API  │ │ Scrapyd API  │ │ Scrapyd API  │ │ Scrapyd API  │
 │ Web UI :6800 │ │ Web UI :6800 │ │ Web UI :6800 │ │ Web UI :6800 │
 │              │ │              │ │              │ │              │
 │ Google Spider│ │ Google Spider│ │ Google Spider│ │ Google Spider│
 │ Bing Spider  │ │ Bing Spider  │ │ Bing Spider  │ │ Bing Spider  │
 │              │ │              │ │              │ │              │
 │ Job Queue    │ │ Job Queue    │ │ Job Queue    │ │ Job Queue    │
 └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## ✨ Features

- **Distributed Processing**: Multiple Scrapyd instances for parallel processing
- **Auto-scaling**: Kubernetes-based horizontal pod autoscaling
- **Load Balancing**: Intelligent job distribution across healthy services
- **Web Monitoring**: Built-in Scrapyd web interface and custom dashboard
- **Fault Tolerance**: Automatic recovery from failed services
- **Database Integration**: PostgreSQL with optimized phrase management functions
- **Hourly Scheduling**: Automated phrase activation every hour
- **Container Orchestration**: Full Docker and Kubernetes support

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Kubernetes cluster (for production)
- PostgreSQL database with `onm_phrases` table
- Python 3.11+

### Development Setup

1. **Clone the repository**
```bash
git clone <your-repo> crawler-cluster
cd crawler-cluster
```

2. **Start the development cluster**
```bash
docker-compose -f docker-compose.scrapyd.yml up --build
```

3. **Access the interfaces**
- Scrapyd Web UI: http://localhost:6801-6804
- Job Scheduler API: http://localhost:8080
- Unified Interface: http://localhost:80

### Production Deployment

1. **Build and push images**
```bash
docker build -f Dockerfile.scrapyd -t your-registry/crawler-scrapyd:latest .
docker build -f Dockerfile.scheduler -t your-registry/crawler-scheduler:latest .
docker push your-registry/crawler-scrapyd:latest
docker push your-registry/crawler-scheduler:latest
```

2. **Deploy to Kubernetes**
```bash
kubectl apply -f deployments/k8s-scrapyd-deployment.yml
```

3. **Verify deployment**
```bash
kubectl get pods -l app=scrapyd
kubectl get services
```

## 📁 Project Structure

```
crawler-cluster/
├── README.md                          # This file
├── docs/                             # Documentation
│   ├── DEPLOYMENT.md                 # Deployment guide
│   ├── API.md                       # API documentation
│   ├── CONFIGURATION.md             # Configuration guide
│   └── TROUBLESHOOTING.md           # Troubleshooting guide
├── deployments/                     # Deployment configurations
│   ├── k8s-scrapyd-deployment.yml   # Kubernetes deployment
│   ├── docker-compose.scrapyd.yml   # Docker Compose for dev
│   └── nginx.conf                   # Nginx configuration
├── dockerfiles/                     # Docker configurations
│   ├── Dockerfile.scrapyd           # Scrapyd container
│   └── Dockerfile.scheduler         # Scheduler container
├── job_scheduler.py                 # Central job scheduler
├── scrapyd.conf                    # Scrapyd configuration
├── scrapy_crawler/                 # Scrapy project
│   ├── spiders/                    # Spider implementations
│   ├── settings.py                 # Scrapy settings
│   └── pipelines.py               # Data processing pipelines
├── config/                         # Configuration files
│   └── settings.py                 # Database and API settings
└── requirements.txt                # Python dependencies
```

## 🎯 Key Components

### 1. Job Scheduler
- Centralized job distribution system
- Manages phrase batches and assigns to least loaded Scrapyd instances
- Provides REST API for monitoring and control
- Handles hourly phrase activation

### 2. Scrapyd Cluster
- Multiple containerized Scrapyd instances
- Each instance can run multiple concurrent spiders
- Built-in web interface for job monitoring
- Auto-discovery and health checking

### 3. Database Layer
- PostgreSQL with optimized phrase management
- Atomic phrase claiming with `claim_phrases_for_worker()`
- Automatic timeout handling and retry logic
- Status tracking and completion management

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SCRAPYD_SERVICES` | Comma-separated list of Scrapyd URLs | - |
| `PG_HOST` | PostgreSQL host | localhost |
| `PG_DATABASE` | Database name | onm |
| `PG_USER` | Database user | onm_admin |
| `PG_PASSWORD` | Database password | - |
| `BATCH_SIZE` | Phrases per job batch | 30 |
| `MAX_CONCURRENT_JOBS` | Max jobs per Scrapyd instance | 4 |

### Scrapyd Configuration

See `scrapyd.conf` for detailed Scrapyd settings including:
- Process limits and concurrency
- Log and data storage paths
- API endpoint configurations

## 📊 Monitoring

### Web Interfaces

1. **Scrapyd Web UI** (`http://your-domain/scrapyd/`)
   - View running, pending, and finished jobs
   - Monitor spider performance
   - Access logs and job details

2. **Job Scheduler Dashboard** (`http://your-domain/scheduler/`)
   - System overview and statistics
   - Service health status
   - Active job monitoring

### API Endpoints

- `GET /health` - System health check
- `GET /stats` - Overall system statistics
- `GET /services` - Scrapyd service status
- `GET /jobs` - Active job details

### Logs

- **Scrapyd logs**: Available through web interface and container logs
- **Scheduler logs**: Centralized logging with structured output
- **Kubernetes logs**: `kubectl logs -l app=scrapyd`

## 🔄 Workflow

1. **Hourly Activation**: Scheduler activates 5,400 phrases every hour
2. **Batch Creation**: Phrases grouped into batches of 30-50
3. **Service Selection**: Least loaded healthy Scrapyd instance selected
4. **Job Scheduling**: Batch sent to selected Scrapyd via REST API
5. **Spider Execution**: Scrapyd runs Google/Bing spider with phrase batch
6. **Status Updates**: Database updated with completion/failure status
7. **Monitoring**: Progress tracked through web interfaces

## 📈 Performance

- **Throughput**: ~1,350 phrases per server per hour
- **Concurrency**: 4 jobs per Scrapyd instance × 4 instances = 16 concurrent jobs
- **Batch Size**: 30 phrases per job for optimal performance
- **Processing Time**: ~2-3 minutes per batch average

## 🛠️ Development

### Adding New Spiders

1. Create spider in `scrapy_crawler/spiders/search/`
2. Update scheduler configuration
3. Rebuild Docker images
4. Deploy updated containers

### Scaling

**Horizontal Scaling** (more instances):
```bash
kubectl scale deployment scrapyd-cluster --replicas=8
```

**Vertical Scaling** (more resources):
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

## 🔍 Troubleshooting

### Common Issues

1. **No phrases being processed**
   - Check database connectivity
   - Verify phrase activation status
   - Review scheduler logs

2. **Scrapyd instances unhealthy**
   - Check container resource limits
   - Verify network connectivity
   - Review Scrapyd logs

3. **Jobs stuck in pending**
   - Check Scrapyd process limits
   - Verify spider deployment
   - Review job queue status

For detailed troubleshooting, see [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## 📚 Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) - Detailed deployment instructions
- [API Documentation](docs/API.md) - Complete API reference
- [Configuration Guide](docs/CONFIGURATION.md) - Configuration options
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests and documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Links

- [Scrapy Documentation](https://docs.scrapy.org/)
- [Scrapyd Documentation](https://scrapyd.readthedocs.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Documentation](https://docs.docker.com/) 