"""Health check and monitoring endpoints."""

from fastapi import APIRouter
from sqlalchemy import text
from database import SessionLocal
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def health_check():
    """Health check endpoint for deployment monitoring.
    
    Returns 200 if the backend is running and database is accessible.
    Returns 503 if database connectivity fails.
    """
    db = SessionLocal()
    try:
        # Verify database connectivity with a simple query
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "oannes-backend",
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db.close()
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 503
    finally:
        db.close()
