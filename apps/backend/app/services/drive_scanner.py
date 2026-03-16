
import logging
import asyncio
import re
from typing import List, Optional
from app.pdf import init_pdf_renderer, _browser

logger = logging.getLogger(__name__)

async def discover_drive_files(folder_url: str) -> List[str]:
    """
    Search for PDF file links within a public Google Drive folder URL.
    Uses Playwright to render the folder view and extract direct file links.
    """
    if not _browser:
        await init_pdf_renderer()
    
    if not _browser:
        logger.error("Failed to initialize browser for Drive scanning")
        return []

    page = await _browser.new_page()
    try:
        logger.info("Scanning Drive folder: %s", folder_url)
        # Handle embedded folder view if possible for easier scraping
        target_url = folder_url
        if "/drive/folders/" in folder_url:
            folder_id = folder_url.split("/folders/")[1].split("?")[0]
            target_url = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
        
        await page.goto(target_url, wait_until="networkidle", timeout=30000)
        
        # Wait for some content to load
        await asyncio.sleep(2)
        
        # Extract all links that look like Drive files
        # Files in embedded view usually have direct links or IDs in data attributes
        links = await page.evaluate('''() => {
            const results = [];
            const anchors = document.querySelectorAll('a[href*="/file/d/"]');
            anchors.forEach(a => {
                if (a.href && !results.includes(a.href)) {
                    results.push(a.href);
                }
            });
            // Also check for grid view items
            const driveItems = document.querySelectorAll('[data-id]');
            driveItems.forEach(item => {
                const id = item.getAttribute('data-id');
                if (id && id.length > 20) { // Typical length
                     const link = `https://drive.google.com/file/d/${id}/view`;
                     if (!results.includes(link)) results.push(link);
                }
            });
            return results;
        }''')
        
        logger.info("Found %d potential files in Drive folder", len(links))
        return links
    except Exception as e:
        logger.error("Error scanning Drive folder %s: %s", folder_url, e)
        return []
    finally:
        await page.close()
