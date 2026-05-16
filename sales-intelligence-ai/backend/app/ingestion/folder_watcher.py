"""
APScheduler job that scans data/comax_reports/ on an interval and imports new files.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..utils.logging import get_logger
from .importer import import_all_pending

log = get_logger(__name__)
_scheduler: BackgroundScheduler | None = None


def _job() -> None:
    try:
        results = import_all_pending()
        if results:
            log.info("watcher.tick processed=%d", len(results))
    except Exception:
        log.exception("watcher.error")


def start_watcher() -> None:
    global _scheduler
    if not settings.WATCHER_ENABLED or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _job,
        trigger=IntervalTrigger(seconds=settings.WATCHER_INTERVAL_SECONDS),
        id="folder_watcher",
        max_instances=1,
        coalesce=True,
        next_run_time=None,
    )
    _scheduler.start()
    log.info("watcher.started interval=%ds folder=%s",
             settings.WATCHER_INTERVAL_SECONDS, settings.COMAX_REPORTS_DIR)


def stop_watcher() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("watcher.stopped")
