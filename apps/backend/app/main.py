"""FastAPI application entry point."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# Configure logging at the very start
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Fix for Windows: Use ProactorEventLoop for subprocess support (Playwright)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app import __version__
from app.config import settings
from app.database import db
from app.pdf import close_pdf_renderer, init_pdf_renderer
from app.routers import admin_router, config_router, enrichment_router, health_router, jobs_router, resumes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up Resume Matcher API...")
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Data directory verified: %s", settings.data_dir)
    except Exception as e:
        logger.error("Failed to create data directory: %s", e)
    
    logger.info("Startup complete.")
    yield
    # Shutdown - wrap each cleanup in try-except to ensure all resources are released
    logger.info("Shutting down Resume Matcher API...")
    try:
        await close_pdf_renderer()
        logger.info("PDF renderer closed.")
    except Exception as e:
        logger.error(f"Error closing PDF renderer: {e}")


app = FastAPI(
    title="Resume Matcher API",
    description="AI-powered resume tailoring for job descriptions",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware - origins configurable via CORS_ORIGINS env var
# In production with a proxy, we use allow_origin_regex or a more permissive setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.llm_provider == "ollama" else settings.cors_origins,
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(resumes_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(enrichment_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Resume Matcher API",
        "version": __version__,
        "debug_id": "rescore_fix_v4",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
