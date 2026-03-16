import os
import logging
import asyncio
from typing import Optional, Any
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "resume_matcher",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    broker_connection_retry_on_startup=True
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
        return asyncio.run(coro)
    except RuntimeError as e:
        if "already running" in str(e):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro)
        raise e

@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: str):
    """Background task to parse and process resume content using LLM."""
    from app.database import db
    from app.services.parser import parse_resume_to_json

    logger.info(f"Starting background processing for resume {resume_id}")
    
    resume = db.get_resume(resume_id)
    if not resume:
        logger.error(f"Resume {resume_id} not found")
        return

    try:
        processed_data = run_async(parse_resume_to_json(resume["content"]))
        db.update_resume(resume_id, {
            "processed_data": processed_data,
            "processing_status": "ready",
        })
        logger.info(f"Successfully processed resume {resume_id}")
    except Exception as e:
        logger.error(f"Failed to process resume {resume_id}: {e}")
        db.update_resume(resume_id, {
            "processing_status": "failed",
            "error_message": str(e)
        })

@celery_app.task(name="process_and_score_resume_task")
def process_and_score_resume_task(resume_id: str, job_id: Optional[str] = None):
    """Background task to parse resume and optionally calculate ATS score."""
    from app.database import db
    from app.services.ats_scorer import parse_and_score_integrated, extract_score, score_and_update_resume
    from app.services.improver import extract_job_keywords
    from app.services.parser import parse_resume_to_json

    logger.info(f"Starting integrated processing for resume {resume_id}")
    
    resume = db.get_resume(resume_id)
    if not resume:
        logger.error(f"Resume {resume_id} not found")
        return

    try:
        # OPTIMIZATION: Combine parse and score into a single LLM call
        if job_id and job_id.strip():
            job = db.get_job(job_id)
            if job:
                keywords = job.get("job_keywords")
                if not keywords:
                    keywords = run_async(extract_job_keywords(job["content"]))
                    db.update_job(job_id, {"job_keywords": keywords})
                
                logger.info(f"Running integrated parse & score for resume {resume_id}")
                result = run_async(parse_and_score_integrated(
                    resume["content"], 
                    job_id, 
                    job["content"], 
                    keywords or {}
                ))
                
                if result and "parsed_resume" in result and "ats_analysis" in result:
                    processed_data = result["parsed_resume"]
                    ats_analysis = result["ats_analysis"]
                    score = extract_score(ats_analysis)
                    
                    db.update_resume(resume_id, {
                        "processed_data": processed_data,
                        "ats_score": score,
                        "ats_breakdown": ats_analysis.get("breakdown") or {},
                        "processing_status": "ready"
                    })
                    logger.info(f"Integrated processing complete for {resume_id}: Score {score}")
                    return

        # Fallback: Parse then Score
        processed_data = run_async(parse_resume_to_json(resume["content"]))
        updates = {
            "processed_data": processed_data,
            "processing_status": "ready",
        }

        if job_id and job_id.strip():
            ats_updates = run_async(score_and_update_resume(resume_id, processed_data, job_id))
            if ats_updates:
                updates.update(ats_updates)

        db.update_resume(resume_id, updates)
        logger.info(f"Processed resume {resume_id} via fallback")

    except Exception as e:
        logger.error(f"Failed to process/score resume {resume_id}: {e}", exc_info=True)
        db.update_resume(resume_id, {
            "processing_status": "failed",
            "error_message": str(e)
        })

@celery_app.task(name="capture_pdf_snapshot_task")
def capture_pdf_snapshot_task(resume_id: str, url: str, job_id: Optional[str] = None, user_id: Optional[str] = None):
    """Background task to capture a PDF snapshot, parse it, and trigger scoring."""
    from app.database import db
    from app.pdf import render_resume_pdf
    from app.services.parser import parse_document
    from app.services.downloader import download_file

    logger.info(f"Starting PDF capture for resume {resume_id} from {url}")

    try:
        if "drive.google.com" in url:
            content = run_async(download_file(url))
        else:
            content = run_async(render_resume_pdf(url, selector=None))

        if not content:
            raise ValueError(f"Failed to acquire content from {url}")

        markdown_content = run_async(parse_document(content, f"resume_{resume_id}.pdf"))
        db.update_resume(resume_id, {
            "content": markdown_content,
            "processing_status": "processing",
        }, user_id=user_id)

        process_and_score_resume_task.delay(resume_id, job_id=job_id)
        logger.info(f"Successfully captured and queued processing for resume {resume_id}")

    except Exception as e:
        logger.error(f"Failed to capture PDF for resume {resume_id}: {e}")
        db.update_resume(resume_id, {
            "processing_status": "failed",
            "error_message": str(e)
        }, user_id=user_id)
