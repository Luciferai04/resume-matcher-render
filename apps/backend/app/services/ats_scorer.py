"""ATS Scoring service using LLM."""

import json
import logging
from typing import Any

from app.llm import complete_json
from app.prompts import get_language_name
from app.prompts.templates import ATS_SCORE_PROMPT
from app.schemas import ATSScoreResponse

logger = logging.getLogger(__name__)

async def calculate_ats_score(
    resume_data: dict[str, Any],
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
    result = await complete_json(prompt=prompt)
    return result
