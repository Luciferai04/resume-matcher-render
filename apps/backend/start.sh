#!/bin/bash

# Start Celery worker in the background (limiting concurrency to avoid OOM on free tier)
echo "Starting Celery worker..."
celery -A app.worker.celery_app worker --loglevel=info --concurrency=1 --max-tasks-per-child=50 &

# Start the FastAPI application (explicitly 1 worker)
echo "Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
