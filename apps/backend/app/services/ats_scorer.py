"""ATS Scoring service using LLM."""

import json
import logging
from typing import Any, Optional

from app.llm import complete_json
from app.prompts.templates import ATS_SCORE_PROMPT, get_language_name
from app.services.refiner import calculate_keyword_match
from app.services.improver import extract_job_keywords
from app.database import db

logger = logging.getLogger(__name__)

import redis
from app.config import settings

# Initialize Redis client
redis_client = redis.from_url(settings.redis_url)

async def calculate_ats_score(
    resume_id: str,
    resume_data: dict[str, Any],
    job_id: str,
    job_description: str,
    job_keywords: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    """Calculate ATS score for a resume against a job description, with Redis caching."""
    # Try to fetch from cache first
    cache_key = f"ats_score:{resume_id}:{job_id}"
    try:
        cached_result = redis_client.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached ATS score for resume {resume_id} and job {job_id}")
            return json.loads(cached_result)
    except Exception as e:
        logger.warning(f"Redis cache fetch failed: {e}")

    language_name = get_language_name(language)
    
    # Calculate keyword match percentage locally to provide as a hint to the LLM
    try:
        kw_match_percentage = calculate_keyword_match(resume_data, job_keywords)
        kw_hint = f"\n\nReference Keyword Match Score (calculated locally): {kw_match_percentage:.1f}%\n"
        logger.info(f"Local keyword match calculated: {kw_match_percentage:.1f}%")
    except Exception as e:
        logger.warning(f"Failed to calculate local keyword match: {e}")
        kw_hint = ""

    prompt = ATS_SCORE_PROMPT.format(
        output_language=language_name,
        job_description=job_description,
        job_keywords=json.dumps(job_keywords, indent=2),
        resume_data=json.dumps(resume_data, indent=2),
    )
    
    # Append the hint if we have it
    if kw_hint:
        prompt += kw_hint

    result = await complete_json(prompt=prompt)
    
    # Cache result if successful
    if result:
        try:
            # Cache for 24 hours
            redis_client.setex(cache_key, 86400, json.dumps(result))
            logger.info(f"Cached ATS score for resume {resume_id} and job {job_id}")
        except Exception as e:
            logger.warning(f"Redis cache store failed: {e}")
            
    return result

async def score_and_update_resume(
    resume_id: str,
    processed_data: dict[str, Any],
    job_id: str,
    user_id: Optional[str] = None
) -> dict[str, Any]:
    """Calculate ATS score for a resume and update it in the database."""
    job = db.get_job(job_id)
    if not job:
        logger.warning(f"Job {job_id} not found for scoring resume {resume_id}")
        return {}

    # Get keywords (extract if missing)
    keywords = job.get("job_keywords")
    if not keywords:
        logger.info(f"Extracting keywords for job {job_id}")
        keywords = await extract_job_keywords(job["content"])
        # Update job with extracted keywords
        db.update_job(job_id, {"job_keywords": keywords})

    ats_result = await calculate_ats_score(
        resume_id=resume_id,
        resume_data=processed_data,
        job_id=job_id,
        job_description=job["content"],
        job_keywords=keywords or {},
    )
    
    if ats_result:
        # Map various possible score keys from LLM
        raw_score = (
            ats_result.get("totalScore") or 
            ats_result.get("total_score") or 
            ats_result.get("overall_score") or 
            ats_result.get("score")
        )
        
        # Sanitize score to integer
        score = 0
        if raw_score is not None:
            try:
                if isinstance(raw_score, (int, float)):
                    score = int(raw_score)
                else:
                    # Handle strings like "85%", "85/100", etc.
                    score_str = str(raw_score).split('/')[0].rstrip('%').strip()
                    # Extract digits only
                    score_digits = "".join(filter(str.isdigit, score_str))
                    if score_digits:
                        score = int(score_digits)
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse ATS score '{raw_score}' to integer")
        
        updates = {
            "ats_score": score,
            "ats_breakdown": ats_result.get("breakdown")
        }
        db.update_resume(resume_id, updates, user_id=user_id)
        return updates
    
    return {}
