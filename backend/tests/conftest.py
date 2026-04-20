"""Shared pytest fixtures for all backend tests."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Point DATA_DIR at a temp location so crypto key doesn't pollute home dir
os.environ.setdefault("DATA_DIR", "/tmp/oannes_test_data")

from database import Base, get_db  # noqa: E402  (must be after env setup)
# Import all models so SQLAlchemy knows about them before create_all
import models.project   # noqa: F401
import models.sync_job  # noqa: F401


# ---------------------------------------------------------------------------
# In-memory SQLite engine shared per test session via StaticPool.
# StaticPool ensures all connections share a single underlying connection,
# which is required for SQLite in-memory DBs to be visible across requests.
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite://"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Per-test session with SAVEPOINT-based isolation.

    Even when application code calls ``session.commit()``, we intercept at the
    SQLAlchemy level: those commits only release their savepoint, never the
    outer transaction that wraps the entire test.  The outer transaction is
    rolled back in teardown so the DB is pristine for the next test.
    """
    connection = engine.connect()
    outer_txn = connection.begin()

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestingSession()

    # Open initial SAVEPOINT so the first db.commit() inside a test lands here.
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, txn) -> None:
        # When an inner savepoint is committed/released, immediately open a new
        # one so subsequent db.commit() calls inside the same test are still safe.
        if txn.nested and not txn._parent.nested:
            sess.expire_all()
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_txn.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    """FastAPI TestClient wired to the test DB session."""
    from main import app

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_project(db):
    """Create a sample project for testing."""
    from models.project import Project, WorkflowStep
    
    project = Project(
        name="Test Project",
        platform="csv",
        config={"file_path": "/tmp/test.csv"},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Add workflow steps
    for i, (name, stage) in enumerate([("Backlog", "queue"), ("In Progress", "start"), ("Done", "done")]):
        step = WorkflowStep(
            project_id=project.id,
            display_name=name,
            stage=stage,
            position=i,
            source_statuses=[name],
        )
        db.add(step)
    db.commit()
    
    return project
