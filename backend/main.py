from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
import logging
import sys

# Log level defaults to INFO in production; set LOG_LEVEL=DEBUG for verbose output
log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
logger.info("🚀 Oannes Backend Starting")



@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    from database import init_db, check_database_integrity, recover_stuck_sync_jobs
    init_db()
    logger.info("Database initialized")
    
    try:
        check_database_integrity()
        recover_stuck_sync_jobs()
    except RuntimeError as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield

    # ── shutdown ─────────────────────────────────────────────────────────────
    pass


app = FastAPI(title="Oannes", version="2.0.0", lifespan=lifespan)

# Register error handlers for consistent error responses
from api.errors import register_error_handlers
register_error_handlers(app)

_default_origins = "http://localhost:5173,http://localhost:3000"
_cors_origins = os.getenv("CORS_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.projects import router as projects_router
from api.metrics import router as metrics_router
from api.connectors import router as connectors_router
from api.sync import router as sync_router
from api.health import router as health_router

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["metrics"])
app.include_router(connectors_router, prefix="/api/connectors", tags=["connectors"])
app.include_router(sync_router, prefix="/api/sync", tags=["sync"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
