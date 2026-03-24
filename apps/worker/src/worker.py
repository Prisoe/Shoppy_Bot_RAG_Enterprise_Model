"""
Celery worker entrypoint.
Run with: celery -A src.worker.celery_app worker --loglevel=info
"""
import sys
import os

# Inject the api src directory so worker can import api services
sys.path.insert(0, "/app/api_src")

from celery import Celery
from pydantic_settings import BaseSettings
from functools import lru_cache


class WorkerSettings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"


_settings = WorkerSettings()

celery_app = Celery(
    "rag_worker",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=[
        "src.jobs.kb_ingest",
        "src.jobs.run_evals",
        "src.jobs.geo_scan",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "jobs.kb_ingest.*": {"queue": "ingest"},
        "jobs.run_evals.*": {"queue": "evals"},
        "jobs.geo_scan.*": {"queue": "geo"},
    },
)
