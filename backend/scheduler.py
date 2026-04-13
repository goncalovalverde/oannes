from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)
_scheduler = None


def sync_all_projects() -> None:
    """Hourly job: create a pending SyncJob for every hourly-frequency project and run it.

    Each project is isolated in its own try/except so a single bad credential
    cannot abort the remaining projects in the batch.
    """
    from database import SessionLocal
    from models.project import Project
    from services.sync_service import SyncService

    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.sync_frequency == "hourly").all()
        for project in projects:
            try:
                logger.info("Scheduled sync for project %s: %s", project.id, project.name)
                svc = SyncService(db)
                svc.create_job(project.id)
                svc.run(project.id)
            except Exception:
                logger.exception(
                    "Scheduled sync failed for project %s (%s) — continuing with remaining projects",
                    project.id, project.name,
                )
    except Exception:
        logger.exception("Scheduler: unexpected error loading projects")
    finally:
        db.close()

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        sync_all_projects,
        trigger=IntervalTrigger(hours=1),
        id="hourly_sync",
        replace_existing=True
    )
    _scheduler.start()
    logger.info("Background scheduler started")

def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
