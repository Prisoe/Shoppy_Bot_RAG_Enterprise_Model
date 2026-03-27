"""Jobs package — Celery app with full production beat schedule."""
import sys, os
sys.path.insert(0, "/app/api_src")

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("rag_worker", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 3600},
    result_expires=86400,
    beat_schedule={
        # GEO scan daily at 2am UTC
        "daily-geo-scan": {
            "task": "jobs.geo_scan.run_geo_scan_all_orgs",
            "schedule": crontab(hour=2, minute=0),
        },
        # Archive old logs weekly on Sunday at 3am UTC
        "weekly-log-archive": {
            "task": "jobs.log_archive.archive_old_runs",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),
        },
        # Hourly health ping
        "hourly-health": {
            "task": "jobs.geo_scan.health_check",
            "schedule": crontab(minute=0),
        },
    },
)
