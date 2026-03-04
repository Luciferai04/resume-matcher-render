#!/bin/bash

# Start Celery worker in the background
echo "Starting Celery worker..."
celery -A app.worker.celery_app worker --loglevel=info &

# Start the FastAPI application
echo "Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000
