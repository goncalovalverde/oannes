from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
import logging
import sys

# Configure logging with detailed format for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
logger.info("🚀 Oannes Backend Starting (DEBUG mode enabled)")



@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    from database import init_db
    init_db()
    logger.info("Database initialized")

    yield

    # ── shutdown ─────────────────────────────────────────────────────────────
    pass


app = FastAPI(title="Oannes", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.projects import router as projects_router
from api.metrics import router as metrics_router
from api.connectors import router as connectors_router
from api.sync import router as sync_router

app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["metrics"])
app.include_router(connectors_router, prefix="/api/connectors", tags=["connectors"])
app.include_router(sync_router, prefix="/api/sync", tags=["sync"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
