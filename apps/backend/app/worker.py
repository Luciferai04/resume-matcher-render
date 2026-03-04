import os
import logging
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

@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: str):
    """
    Background task to parse and process resume content using LLM.
    """
    from app.database import db
    from app.routers.resumes import parse_resume_to_json
    import asyncio

    logger.info(f"Starting background processing for resume {resume_id}")
    
    resume = db.get_resume(resume_id)
    if not resume:
        logger.error(f"Resume {resume_id} not found for background processing")
        return

    try:
        # Run the async parser in the celery worker's event loop
        loop = asyncio.get_event_loop()
        processed_data = loop.run_until_complete(parse_resume_to_json(resume["content"]))
        
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

@celery_app.task(name="generate_tailored_resume_task")
def generate_tailored_resume_task(resume_id: str, job_id: str, prompt_id: str):
    """
    Background task to generate a tailored resume.
    """
    # This could be expanded to handle the full improvement pipeline asynchronously
    pass
