import os
import logging
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

@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: str):
    """
    Background task to parse and process resume content using LLM.
    """
    from app.database import db
    from app.services.parser import parse_resume_to_json
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

@celery_app.task(name="process_and_score_resume_task")
def process_and_score_resume_task(resume_id: str, job_id: Optional[str] = None):
    """
    Background task to parse resume and optionally calculate ATS score.
    """
    from app.database import db
    from app.services.parser import parse_resume_to_json
    from app.services.ats_scorer import calculate_ats_score
    from app.services.improver import extract_job_keywords
    import asyncio

    logger.info(f"Starting integrated processing for resume {resume_id}")
    
    resume = db.get_resume(resume_id)
    if not resume:
        logger.error(f"Resume {resume_id} not found")
        return

    try:
        loop = asyncio.get_event_loop()
        
        # 1. Parse to JSON
        processed_data = loop.run_until_complete(parse_resume_to_json(resume["content"]))
        
        updates = {
            "processed_data": processed_data,
            "processing_status": "ready",
        }

        # 2. Optionally score against job
        if job_id:
            job = db.get_job(job_id)
            if job:
                logger.info(f"Calculating ATS score for resume {resume_id} against job {job_id}")
                # Get keywords (extract if missing)
                keywords = job.get("job_keywords")
                if not keywords:
                    logger.info(f"Extracting keywords for job {job_id}")
                    keywords = loop.run_until_complete(extract_job_keywords(job["content"]))
                    # Update job with extracted keywords
                    db.update_job(job_id, {"job_keywords": keywords})

                ats_result = loop.run_until_complete(calculate_ats_score(
                    resume_data=processed_data,
                    job_description=job["content"],
                    job_keywords=keywords or {},
                ))
                if ats_result:
                    updates["ats_score"] = ats_result.get("overall_score")
                    updates["ats_breakdown"] = ats_result.get("breakdown")
            else:
                logger.warning(f"Job {job_id} not found for scoring resume {resume_id}")

        db.update_resume(resume_id, updates)
        logger.info(f"Successfully processed (and scored) resume {resume_id}")
    except Exception as e:
        logger.error(f"Failed to process/score resume {resume_id}: {e}")
        db.update_resume(resume_id, {"processing_status": "failed"})

@celery_app.task(name="generate_tailored_resume_task")
def generate_tailored_resume_task(resume_id: str, job_id: str, prompt_id: str):
    """
    Background task to generate a tailored resume.
    """
    # This could be expanded to handle the full improvement pipeline asynchronously
    pass
