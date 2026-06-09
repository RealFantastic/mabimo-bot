from collections.abc import Callable
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler


DEFAULT_INTERVAL_MINUTES = 5


def create_scheduler(
    run_once: Callable[[], object],
    *,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    now: datetime | None = None,
) -> BackgroundScheduler:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be greater than 0")
    first_run_at = now or datetime.now(timezone.utc)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_once,
        "interval",
        minutes=interval_minutes,
        id="detect-new-posts",
        next_run_time=first_run_at,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    return scheduler
