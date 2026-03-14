"""Health check and status endpoints."""

from fastapi import APIRouter

from app.database import db
from app.llm import check_llm_health, get_llm_config
from app.schemas import HealthResponse, StatusResponse

router = APIRouter(tags=["Health"])


import logging
logger = logging.getLogger(__name__)

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    llm_status = await check_llm_health()
    
    # Check Redis
    redis_healthy = False
    try:
        from app.services.ats_scorer import redis_client
        redis_healthy = redis_client.ping()
    except Exception:
        redis_healthy = False

    # Check Worker
    worker_status = {"healthy": False, "active_nodes": 0}
    try:
        from app.worker import celery_app
        i = celery_app.control.inspect()
        stats = i.stats()
        if stats:
            worker_status["healthy"] = True
            worker_status["active_nodes"] = len(stats)
            worker_status["nodes"] = list(stats.keys())
    except Exception as e:
        logger.warning(f"Worker health check failed: {e}")

    return HealthResponse(
        status="healthy" if llm_status.get("healthy") and redis_healthy and worker_status["healthy"] else "degraded",
        llm=llm_status,
        redis={"healthy": redis_healthy},
        worker=worker_status,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Get comprehensive application status.

    Returns:
        - LLM configuration status
        - Master resume existence
        - Database statistics
    """
    config = get_llm_config()
    llm_status = await check_llm_health(config)
    db_stats = db.get_stats()

    return StatusResponse(
        status="ready" if llm_status["healthy"] and db_stats["has_master_resume"] else "setup_required",
        llm_configured=bool(config.api_key) or config.provider == "ollama",
        llm_healthy=llm_status["healthy"],
        has_master_resume=db_stats["has_master_resume"],
        database_stats=db_stats,
    )
