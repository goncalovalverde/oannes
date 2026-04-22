"""Alembic Database Migrations Setup

This module provides migration utilities and guidance for Alembic integration.

Current Status:
  The project uses manual schema migrations via migrate_schema() in database.py.
  This approach is suitable for small teams and simple schemas.

Migration to Alembic (future):
  When the schema becomes more complex or you need better version control:

  1. Install alembic:
     pip install alembic

  2. Initialize alembic:
     alembic init alembic

  3. Configure alembic/env.py:
     - Point to SQLAlchemy models
     - Configure SQLite URL
     - Enable automatic table detection

  4. Create first migration:
     alembic revision --autogenerate -m "Initial schema"

  5. Apply migrations:
     alembic upgrade head

  6. Integrate with app startup:
     from alembic.config import Config
     from alembic.script import ScriptDirectory
     from alembic.runtime.migration import MigrationContext
     from alembic.operations import Operations

Current Manual Approach Benefits:
  - Simple, no extra dependencies
  - Works well for small schemas (<20 tables)
  - Easy to understand and debug
  - No version tracking overhead
  - Fast startup

Reasons to Switch to Alembic:
  - Multi-environment deployments
  - Need to rollback migrations
  - Complex schema evolution
  - Team-wide migration auditing
  - Production change tracking

For now, keep using migrate_schema(). This will be refactored when needed.
"""

def get_current_schema_version() -> str:
    """Get the current schema version (for future Alembic integration)."""
    # Once Alembic is integrated, this would query the alembic_version table
    # For now, return a placeholder based on features present
    return "2.0.0-manual"


def list_pending_migrations():
    """List pending migrations that haven't been applied (future Alembic method)."""
    # Placeholder for future Alembic integration
    # Once Alembic is integrated, this would query pending migrations from scripts/
    return []
