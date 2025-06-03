# Makefile for ONM Crawler Testing

.PHONY: help test test-unit test-integration test-e2e test-performance test-security test-chaos test-all
.PHONY: setup-test cleanup-test build-test start-test-services stop-test-services
.PHONY: lint format coverage report install-deps

# Default target
help:
	@echo "ONM Crawler Test Suite"
	@echo "======================"
	@echo ""
	@echo "Available targets:"
	@echo "  help              Show this help message"
	@echo "  install-deps      Install test dependencies"
	@echo "  lint              Run code linting"
	@echo "  format            Format code with black"
	@echo ""
	@echo "Test Targets:"
	@echo "  test              Run all tests except performance and chaos"
	@echo "  test-unit         Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-e2e          Run end-to-end tests only"
	@echo "  test-performance  Run performance tests only"
	@echo "  test-security     Run security tests only"
	@echo "  test-chaos        Run chaos engineering tests only"
	@echo "  test-all          Run ALL tests including performance and chaos"
	@echo ""
	@echo "Environment Management:"
	@echo "  setup-test        Set up test environment"
	@echo "  cleanup-test      Clean up test environment"
	@echo "  build-test        Build test Docker images"
	@echo "  start-test-services    Start test services"
	@echo "  stop-test-services     Stop test services"
	@echo ""
	@echo "Reports:"
	@echo "  coverage          Generate coverage report"
	@echo "  report            Generate comprehensive test report"

# Variables
PYTHON = python3
PIP = pip3
PYTEST = pytest
DOCKER_COMPOSE = docker-compose
TEST_COMPOSE_FILE = docker-compose.test.yml

# Install test dependencies
install-deps:
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-mock pytest-html pytest-timeout
	$(PIP) install pytest-asyncio pytest-docker testcontainers
	$(PIP) install requests selenium docker psycopg2-binary
	$(PIP) install black flake8 mypy safety bandit
	$(PIP) install locust  # For performance testing

# Code quality
lint:
	flake8 --max-line-length=100 --ignore=E203,W503 .
	mypy --ignore-missing-imports job_scheduler.py
	bandit -r . -x tests/

format:
	black --line-length=100 .

# Security checks
security-scan:
	safety check
	bandit -r . -f json -o reports/security-report.json || true

# Test environment setup
setup-test:
	@echo "Setting up test environment..."
	mkdir -p reports logs
	docker network create test-network 2>/dev/null || true
	$(MAKE) build-test

cleanup-test:
	@echo "Cleaning up test environment..."
	$(DOCKER_COMPOSE) -f $(TEST_COMPOSE_FILE) down -v
	docker network rm test-network 2>/dev/null || true
	docker system prune -f

build-test:
	@echo "Building test images..."
	$(DOCKER_COMPOSE) -f $(TEST_COMPOSE_FILE) build

start-test-services:
	@echo "Starting test services..."
	$(DOCKER_COMPOSE) -f $(TEST_COMPOSE_FILE) up -d
	@echo "Waiting for services to be ready..."
	./scripts/wait-for-services.sh

stop-test-services:
	@echo "Stopping test services..."
	$(DOCKER_COMPOSE) -f $(TEST_COMPOSE_FILE) down

# Test targets
test-unit:
	@echo "Running unit tests..."
	$(PYTEST) tests/unit -m unit --cov-report=term-missing

test-integration: start-test-services
	@echo "Running integration tests..."
	$(PYTEST) tests/integration -m integration --cov-report=term-missing
	$(MAKE) stop-test-services

test-e2e: start-test-services
	@echo "Running end-to-end tests..."
	$(PYTEST) tests/e2e -m e2e --cov-report=term-missing
	$(MAKE) stop-test-services

test-performance: start-test-services
	@echo "Running performance tests..."
	$(PYTEST) tests/performance -m performance --cov-report=term-missing
	$(MAKE) stop-test-services

test-security: start-test-services
	@echo "Running security tests..."
	$(PYTEST) tests/security -m security --cov-report=term-missing
	$(MAKE) stop-test-services

test-chaos: start-test-services
	@echo "Running chaos engineering tests..."
	$(PYTEST) tests/chaos -m chaos --cov-report=term-missing
	$(MAKE) stop-test-services

# Main test targets
test: test-unit test-integration test-e2e
	@echo "Core tests completed"

test-all: test test-performance test-security test-chaos
	@echo "All tests completed"

# Coverage and reporting
coverage:
	@echo "Generating coverage report..."
	$(PYTEST) tests/unit tests/integration --cov --cov-report=html --cov-report=term

report: test-all
	@echo "Generating comprehensive test report..."
	@echo "Test reports available in:"
	@echo "  - HTML Report: reports/pytest_report.html"
	@echo "  - Coverage Report: htmlcov/index.html"
	@echo "  - JUnit XML: reports/junit.xml"
	@echo "  - Security Report: reports/security-report.json"

# Quick development workflow
dev-test: format lint test-unit
	@echo "Development tests completed"

# CI/CD pipeline simulation
ci: format lint security-scan test-unit test-integration
	@echo "CI pipeline simulation completed"

# Performance benchmarking
benchmark:
	@echo "Running performance benchmarks..."
	locust -f tests/performance/locustfile.py --headless -u 10 -r 2 -t 60s --host=http://localhost:8080

# Database tests
test-db:
	@echo "Running database-specific tests..."
	$(PYTEST) tests/unit tests/integration -m database

# Network tests
test-network:
	@echo "Running network-specific tests..."
	$(PYTEST) tests/integration tests/e2e -m network

# Docker tests
test-docker:
	@echo "Running Docker-specific tests..."
	$(PYTEST) tests/integration tests/e2e -m docker

# Kubernetes tests (requires k8s cluster)
test-k8s:
	@echo "Running Kubernetes tests..."
	$(PYTEST) tests/infrastructure -m kubernetes

# Clean all generated files
clean:
	rm -rf htmlcov/
	rm -rf reports/
	rm -rf .pytest_cache/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete 