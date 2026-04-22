"""Unified error response handling.

Provides consistent error responses across all endpoints for frontend error display.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors with user-friendly messages."""
    
    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or status_code
        super().__init__(self.message)


class ValidationError(APIError):
    """Validation or input error."""
    def __init__(self, message: str):
        super().__init__(message, 400, "VALIDATION_ERROR")


class NotFoundError(APIError):
    """Resource not found."""
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", 404, "NOT_FOUND")


class SyncError(APIError):
    """Sync operation failed."""
    def __init__(self, message: str):
        super().__init__(message, 500, "SYNC_ERROR")


class RateLimitError(APIError):
    """Rate limit exceeded."""
    def __init__(self, message: str):
        super().__init__(message, 429, "RATE_LIMIT_EXCEEDED")


def register_error_handlers(app: FastAPI):
    """Register error handlers on the FastAPI app."""
    
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "error_code": exc.error_code,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "An unexpected error occurred. Please try again.",
                "error_code": "INTERNAL_ERROR",
                "path": str(request.url.path)
            }
        )
