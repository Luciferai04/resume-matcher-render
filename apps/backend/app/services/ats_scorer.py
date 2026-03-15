"""ATS Scoring service using LLM."""

import json
import logging
from typing import Any, Optional

from app.llm import complete_json
from app.prompts.templates import ATS_SCORE_PROMPT, get_language_name, PARSE_AND_SCORE_PROMPT, RESUME_SCHEMA_EXAMPLE
from app.services.refiner import calculate_keyword_match
from app.services.improver import extract_job_keywords
from app.database import db

logger = logging.getLogger(__name__)

async def calculate_ats_score(
    resume_id: str,
    resume_data: dict[str, Any],
    job_id: str,
    job_description: str,
    job_keywords: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    """Calculate ATS score for a resume against a job description."""
    language_name = get_language_name(language)
    
    prompt = ATS_SCORE_PROMPT.format(
        output_language=language_name,
        job_description=job_description,
        job_keywords=json.dumps(job_keywords, indent=2),
        resume_data=json.dumps(resume_data, indent=2),
    )
    
    return await complete_json(prompt=prompt)

async def calculate_general_resume_score(
    resume_data: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    """Calculate a general resume quality score when no job is provided."""
    from app.prompts.templates import GENERAL_RESUME_SCORE_PROMPT
    language_name = get_language_name(language)
    
    prompt = GENERAL_RESUME_SCORE_PROMPT.format(
        output_language=language_name,
        resume_data=json.dumps(resume_data, indent=2),
    )
    
    return await complete_json(prompt=prompt)

async def parse_and_score_integrated(
    resume_text: str,
    job_id: str,
    job_content: str,
    job_keywords: dict[str, Any],
    language: str = "en"
) -> dict[str, Any]:
    """Parse resume and calculate ATS score in a single LLM call."""
    language_name = get_language_name(language)
    
    prompt = PARSE_AND_SCORE_PROMPT.format(
        output_language=language_name,
        job_description=job_content,
        job_keywords=json.dumps(job_keywords, indent=2),
        resume_text=resume_text,
        resume_schema=RESUME_SCHEMA_EXAMPLE
    )
    
    result = await complete_json(prompt=prompt)
    if not result or "parsed_resume" not in result:
        logger.error("Integrated parse/score failed: missing 'parsed_resume' in response")
        return {}
        
    return result

def extract_score(ats_result: dict[str, Any]) -> int:
    """Robustly extract an integer score from LLM result."""
    score_keys = [
        "totalScore", "total_score", "ats_score", "atsScore", 
        "overall_score", "score", "match_percentage", "matchScore"
    ]
    
    raw_score = None
    for key in score_keys:
        if key in ats_result:
            raw_score = ats_result[key]
            break
    
    if raw_score is None:
        return 0
        
    try:
        if isinstance(raw_score, (int, float)):
            return int(raw_score)
        else:
            score_str = str(raw_score).split('/')[0].split(':')[0].rstrip('%').strip()
            score_digits = "".join(filter(str.isdigit, score_str))
            return int(score_digits) if score_digits else 0
    except (ValueError, TypeError):
        return 0

async def score_and_update_resume(
    resume_id: str,
    processed_data: dict[str, Any],
    job_id: str,
    user_id: Optional[str] = None
) -> dict[str, Any]:
    """Calculate ATS score for a resume and update it in the database."""
    # If no job_id or job doesn't exist, calculate a general score
    job = db.get_job(job_id) if job_id else None
    
    if not job:
        logger.info(f"No job provided for resume {resume_id}, calculating general score")
        ats_result = await calculate_general_resume_score(
            resume_data=processed_data,
        )
    else:
        # Get keywords (extract if missing)
        keywords = job.get("job_keywords")
        if not keywords:
            logger.info(f"Extracting keywords for job {job_id}")
            keywords = await extract_job_keywords(job["content"])
            db.update_job(job_id, {"job_keywords": keywords})

        ats_result = await calculate_ats_score(
            resume_id=resume_id,
            resume_data=processed_data,
            job_id=job_id,
            job_description=job["content"],
            job_keywords=keywords or {},
        )
    
    if ats_result:
        score = extract_score(ats_result)
        breakdown = ats_result.get("breakdown") or ats_result.get("ats_breakdown") or {}
        
        updates = {
            "ats_score": score,
            "ats_breakdown": breakdown
        }
        db.update_resume(resume_id, updates, user_id=user_id)
        logger.info(f"Updated resume {resume_id} with ATS score: {score}")
        return updates
    
    return {}
