"""CSV import deduplication.

Prevents re-importing the same CSV file by comparing file hashes.
"""

import hashlib
import json
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, text

logger = __import__('logging').getLogger(__name__)


def compute_csv_hash(content: bytes) -> str:
    """Compute SHA256 hash of CSV content.
    
    Args:
        content: File content as bytes
        
    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(content).hexdigest()


def check_duplicate_csv(
    db: Session,
    project_id: int,
    csv_hash: str
) -> bool:
    """Check if this CSV file was already imported.
    
    Args:
        db: Database session
        project_id: Project ID
        csv_hash: SHA256 hash of CSV content
        
    Returns:
        True if file was already imported, False otherwise
    """
    # Check if a sync job for this project exists with matching hash metadata
    try:
        # Query for recent sync jobs with this CSV hash in metadata
        result = db.execute(text(
            "SELECT 1 FROM sync_jobs "
            "WHERE project_id = :project_id "
            "AND status = 'success' "
            "AND error_message LIKE '%csv_hash%' || :csv_hash || '%' "
            "LIMIT 1"
        ), {"project_id": project_id, "csv_hash": csv_hash})
        
        return result.first() is not None
    except Exception as e:
        logger.warning(f"Failed to check CSV duplicate: {e}")
        return False


def record_csv_import(
    db: Session,
    sync_job_id: int,
    csv_hash: str
) -> None:
    """Record that a CSV file was imported (for deduplication).
    
    Args:
        db: Database session
        sync_job_id: ID of the sync job
        csv_hash: SHA256 hash of CSV content
    """
    # Store hash in sync_job metadata (in error_message field as JSON)
    try:
        metadata = json.dumps({"csv_hash": csv_hash, "imported_at": datetime.now(timezone.utc).isoformat()})
        db.execute(text(
            "UPDATE sync_jobs SET error_message = :metadata WHERE id = :sync_job_id"
        ), {"metadata": metadata, "sync_job_id": sync_job_id})
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to record CSV import: {e}")
