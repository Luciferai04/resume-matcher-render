"""SWOT Analysis service using LLM."""

import json
import logging
from typing import Any

from app.llm import complete_json
from app.prompts import get_language_name
from app.prompts.templates import SWOT_ANALYSIS_PROMPT
from app.schemas import SWOTAnalysisResponse

logger = logging.getLogger(__name__)

async def generate_swot_analysis(
    resume_data: dict[str, Any],
    job_description: str,
    language: str = "en",
) -> dict[str, Any]:
    """Generate SWOT analysis for a candidate."""
    language_name = get_language_name(language)
    prompt = SWOT_ANALYSIS_PROMPT.format(
        output_language=language_name,
        job_description=job_description,
        resume_data=json.dumps(resume_data, indent=2),
    )
    result = await complete_json(prompt=prompt)
    return result
