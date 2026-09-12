.PHONY: install test load-test benchmark qa-report ingest run docker-build docker-run help

PYTHON = ./venv/bin/python
PYTEST = ./venv/bin/pytest

help:
	@echo "Egyptian Agriculture AI Platform - Integration, QA & MLOps Commands"
	@echo "=================================================================="
	@echo "  make install      Install Python virtual environment and dependencies"
	@echo "  make test         Run unit and E2E automated test suite"
	@echo "  make load-test    Run load performance stress test"
	@echo "  make benchmark    Run RAG benchmark evaluation engine"
	@echo "  make qa-report    Generate automated QA report (reports/QA_Report.md)"
	@echo "  make ingest       Ingest text knowledge base documents"
	@echo "  make run          Start FastAPI Integration Gateway development server"
	@echo "  make docker-build Build Docker container image"
	@echo "  make docker-run   Start local multi-container stack via Docker Compose"

install:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt

test:
	PYTHONPATH=. $(PYTEST) rag/tests/ tests/e2e/ -v

load-test:
	PYTHONPATH=. $(PYTHON) tests/load/test_load_performance.py

benchmark:
	PYTHONPATH=. $(PYTHON) scripts/benchmark_eval.py

qa-report:
	PYTHONPATH=. $(PYTHON) scripts/generate_qa_report.py

ingest:
	PYTHONPATH=. $(PYTHON) scripts/ingest_knowledge_base.py --dir data/sample_knowledge_base

run:
	PYTHONPATH=. ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t agry-platform/api-gateway:latest .

docker-run:
	docker-compose up --build -d
