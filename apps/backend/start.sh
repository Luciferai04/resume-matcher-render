#!/bin/bash

# Start Celery worker in the background (limiting concurrency to avoid OOM on free tier)
echo "Starting Celery worker..."
celery -A app.worker.celery_app worker --loglevel=info --concurrency=1 --max-tasks-per-child=50 &

# Start the FastAPI application (support dynamic port for Railway)
echo "Starting FastAPI backend on port ${PORT:-8000}..."
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
