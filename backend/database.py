from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from config import settings
import logging

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
