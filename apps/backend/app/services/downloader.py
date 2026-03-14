"""Service for downloading files from external URLs, specifically Google Drive."""

import logging
import re
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# Regex to match Google Drive file IDs
GD_ID_PATTERN = re.compile(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)')

def get_google_drive_direct_link(url: str) -> Optional[str]:
    """Convert a Google Drive sharing link to a direct download link."""
    match = GD_ID_PATTERN.search(url)
    if not match:
        return None
    
    # Extract ID from either group (d/ID or id=ID)
    file_id = match.group(1) or match.group(2)
    return f"https://drive.google.com/uc?export=download&id={file_id}"

async def download_file(url: str) -> Optional[bytes]:
    """Download a file from a URL. Handles Google Drive links automatically."""
    target_url = url
    if "drive.google.com" in url:
        direct_link = get_google_drive_direct_link(url)
        if direct_link:
            target_url = direct_link
            logger.info("Converted Google Drive link to direct link: %s", target_url)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(target_url)
            response.raise_for_status()
            
            # Check for Google login page (indicates private file)
            # Look for common signatures of the Google accounts login page
            if "ServiceLogin" in str(response.url) or "accounts.google.com" in str(response.url):
                logger.error("Google Drive file is private and requires sign-in: %s", url)
                raise ValueError("Access denied: This Google Drive file is private. Please ensure 'Anyone with the link' can view it.")

            # Google Drive sometimes shows a "virus scan warning" page if file is large
            if "virus scan" in response.text.lower() and "confirm=" in response.text:
                confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', response.text)
                if confirm_match:
                    confirm_id = confirm_match.group(1)
                    target_url += f"&confirm={confirm_id}"
                    logger.info("Retrying Google Drive download with confirmation: %s", target_url)
                    response = await client.get(target_url)
                    response.raise_for_status()

            return response.content
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error downloading file from %s: %s", url, e)
        raise ValueError(f"Failed to download file: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error("Failed to download file from %s: %s", url, e)
        raise e
