"""Document parsing service using markitdown and LLM."""

import logging
import tempfile
from pathlib import Path
from typing import Any

from markitdown import MarkItDown

logger = logging.getLogger(__name__)

from app.llm import complete_json
from app.prompts import PARSE_RESUME_PROMPT
from app.prompts.templates import RESUME_SCHEMA_EXAMPLE
from app.schemas import ResumeData


async def parse_document(content: bytes, filename: str) -> str:
    """Convert PDF/DOCX to Markdown using markitdown.

    Args:
        content: Raw file bytes
        filename: Original filename for extension detection

    Returns:
        Markdown text content
    """
    suffix = Path(filename).suffix.lower()

    # Write to temp file for markitdown
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        md = MarkItDown()
        result = md.convert(str(tmp_path))
        return result.text_content
    finally:
        tmp_path.unlink(missing_ok=True)


async def parse_resume_to_json(markdown_text: str) -> dict[str, Any]:
    """Parse resume markdown to structured JSON using LLM.

    Args:
        markdown_text: The markdown content of the resume.

    Returns:
        Structured resume data as a dictionary.
    """
    logger.info("Parsing resume to structured JSON")
    
    # This now calls the globally mocked complete_json in app.llm
    result = await complete_json(
        prompt=PARSE_RESUME_PROMPT.format(
            resume_text=markdown_text, schema=RESUME_SCHEMA_EXAMPLE
        )
    )
    
    # Basic validation
    if not result or not isinstance(result, dict):
        raise ValueError("Failed to parse resume to a valid JSON object")
        
    return result
