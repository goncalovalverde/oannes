from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    poolclass=StaticPool,
    echo_pool=False,
)

# Enable SQLite WAL mode and safety features for concurrent access
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")          # Write-Ahead Logging for concurrent reads
    cursor.execute("PRAGMA synchronous=NORMAL")        # Safe with WAL, improves performance
    cursor.execute("PRAGMA foreign_keys=ON")           # Enforce foreign key constraints
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from models import project, sync_job
    Base.metadata.create_all(bind=engine)
    migrate_schema()

def migrate_schema() -> None:
    """Apply incremental schema migrations not handled by create_all.
    
    SQLAlchemy's create_all() only creates missing tables, it won't add new columns
    to existing tables. This function handles those ALTER TABLE additions.
    """
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Check and add status_transitions column to cached_items
        result = db.execute(text("PRAGMA table_info(cached_items)"))
        columns = {row[1] for row in result}
        if "status_transitions" not in columns:
            db.execute(text("ALTER TABLE cached_items ADD COLUMN status_transitions JSON"))
            db.commit()
            logger.info("Schema migration: added status_transitions column to cached_items")
        
        # Check and add rate limiting columns to projects
        result = db.execute(text("PRAGMA table_info(projects)"))
        columns = {row[1] for row in result}
        if "rate_limit_enabled" not in columns:
            db.execute(text("ALTER TABLE projects ADD COLUMN rate_limit_enabled BOOLEAN DEFAULT 1"))
            db.commit()
            logger.info("Schema migration: added rate_limit_enabled column to projects")
        if "rate_limit_retry_delay" not in columns:
            db.execute(text("ALTER TABLE projects ADD COLUMN rate_limit_retry_delay FLOAT"))
            db.commit()
            logger.info("Schema migration: added rate_limit_retry_delay column to projects")
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        db.rollback()
    finally:
        db.close()

def check_database_integrity() -> str:
    """Verify SQLite database is not corrupted using PRAGMA integrity_check."""
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError
    
    db = SessionLocal()
    try:
        result = db.execute(text("PRAGMA integrity_check"))
        status = result.scalar()
        
        if status != "ok":
            logger.error(f"Database integrity check failed: {status}")
            raise RuntimeError(
                f"Database corruption detected: {status}. "
                "Please delete the database file and restart the application to recreate it."
            )
        
        logger.info("Database integrity check passed ✓")
        return status
    except DatabaseError as e:
        logger.error(f"Failed to check database integrity: {e}")
        raise RuntimeError("Database is corrupted and unusable")
    finally:
        db.close()

def recover_stuck_sync_jobs(db: Optional['Session'] = None) -> None:
    """Reset any SyncJobs stuck in 'running' state to 'error' (e.g., from a crash).
    
    Called on startup to ensure no sync jobs are left in an invalid state.
    
    Args:
        db: Optional SQLAlchemy session. If not provided, a new session will be created.
    """
    from datetime import datetime, timezone
    from models.sync_job import SyncJob
    
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    
    try:
        stuck_jobs = db.query(SyncJob).filter(SyncJob.status == "running").all()
        if stuck_jobs:
            for job in stuck_jobs:
                logger.warning(
                    f"Found stuck SyncJob id={job.id} for project {job.project_id} — "
                    f"resetting from 'running' to 'error' (likely from backend crash)"
                )
                job.status = "error"
                job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                job.error_message = "Job was interrupted (backend crashed or restarted)"
            db.commit()
            logger.info(f"Recovered {len(stuck_jobs)} stuck sync jobs")
    except Exception as e:
        logger.error(f"Failed to recover stuck sync jobs: {e}")
        db.rollback()
    finally:
        if should_close:
            db.close()
