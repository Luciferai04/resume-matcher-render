import os
import logging
import asyncio
from typing import Optional
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "resume_matcher",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

def run_async(coro):
    """Helper to run async coroutines in a synchronous context (Celery worker)."""
    try:
        # Standard approach for sync contexts
        return asyncio.run(coro)
    except RuntimeError as e:
        # If there's already a loop running (e.g. if worker is using an event loop based execution)
        if "already running" in str(e):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro)
        raise e

@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: str):
    """
    Background task to parse and process resume content using LLM.
    """
    from app.database import db
    from app.services.parser import parse_resume_to_json

    logger.info(f"Starting background processing for resume {resume_id}")
    
    resume = db.get_resume(resume_id)
    if not resume:
        logger.error(f"Resume {resume_id} not found for background processing")
        return

    try:
        processed_data = run_async(parse_resume_to_json(resume["content"]))
        
        db.update_resume(
            resume_id,
            {
                "processed_data": processed_data,
                "processing_status": "ready",
            },
        )
        logger.info(f"Successfully processed resume {resume_id}")
    except Exception as e:
        logger.error(f"Failed to process resume {resume_id}: {e}")
        db.update_resume(resume_id, {"processing_status": "failed"})

@celery_app.task(name="process_and_score_resume_task")
def process_and_score_resume_task(resume_id: str, job_id: Optional[str] = None):
    """
    Background task to parse resume and optionally calculate ATS score.
    """
    from app.database import db
    from app.services.parser import parse_resume_to_json
    from app.services.ats_scorer import calculate_ats_score
    from app.services.improver import extract_job_keywords

    logger.info(f"Starting integrated processing for resume {resume_id}")
    
    resume = db.get_resume(resume_id)
    if not resume:
        logger.error(f"Resume {resume_id} not found")
        return

    try:
        # 1. Parse to JSON
        processed_data = run_async(parse_resume_to_json(resume["content"]))
        
        updates = {
            "processed_data": processed_data,
            "processing_status": "ready",
        }

        # 2. Optionally score against job
        if job_id and job_id.strip():
            logger.info(f"Calculating ATS score for resume {resume_id} against job {job_id}")
            from app.services.ats_scorer import score_and_update_resume
            ats_updates = run_async(score_and_update_resume(resume_id, processed_data, job_id))
            if ats_updates:
                updates.update(ats_updates)

        db.update_resume(resume_id, updates)
        logger.info(f"Successfully processed (and scored) resume {resume_id} with status {updates.get('processing_status')} score {updates.get('ats_score')}")
    except Exception as e:
        logger.error(f"Failed to process/score resume {resume_id}: {e}", exc_info=True)
        db.update_resume(resume_id, {"processing_status": "failed"})

@celery_app.task(name="generate_tailored_resume_task")
def generate_tailored_resume_task(resume_id: str, job_id: str, prompt_id: str):
    """
    Background task to generate a tailored resume.
    """
    # This could be expanded to handle the full improvement pipeline asynchronously
    pass
