"""
Celery worker entrypoint.
Tasks live in /app/jobs/ to avoid src package collision.
"""
import sys
import os

sys.path.insert(0, "/app/api_src")
sys.path.insert(0, "/app")

from jobs import celery_app

# Import all task modules to register them
import jobs.kb_ingest  # noqa
import jobs.geo_scan   # noqa
import jobs.run_evals  # noqa

if __name__ == "__main__":
    celery_app.start()

# Import alerting signals (connects Celery task_failure etc.)
try:
    import jobs.alerting  # noqa — registers signal handlers
    import jobs.log_archive  # noqa — registers archive task
except ImportError as e:
    print(f"[worker] Warning: could not import optional modules: {e}")
