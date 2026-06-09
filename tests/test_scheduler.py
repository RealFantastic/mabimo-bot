import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler import DEFAULT_INTERVAL_MINUTES, create_scheduler


class SchedulerTest(unittest.TestCase):
    def test_default_interval_runs_immediately_without_overlapping_jobs(self) -> None:
        run_once = Mock()
        now = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)

        scheduler = create_scheduler(run_once, now=now)

        periodic_job = scheduler.get_job("detect-new-posts")
        self.assertEqual(DEFAULT_INTERVAL_MINUTES, 5)
        self.assertEqual(len(scheduler.get_jobs()), 1)
        self.assertIsInstance(periodic_job.trigger, IntervalTrigger)
        self.assertEqual(periodic_job.trigger.interval, timedelta(minutes=5))
        self.assertEqual(periodic_job.next_run_time, now)
        self.assertTrue(periodic_job.coalesce)
        self.assertEqual(periodic_job.max_instances, 1)


if __name__ == "__main__":
    unittest.main()
