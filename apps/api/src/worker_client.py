"""
Thin client to enqueue Celery tasks from the API process.
"""
from celery import Celery
from src.config import get_settings

settings = get_settings()

celery_app = Celery("rag_worker", broker=settings.redis_url, backend=settings.redis_url)


def enqueue_ingest(source_id: str, org_id: str) -> str:
    task = celery_app.send_task("jobs.kb_ingest.process_source", args=[source_id, org_id])
    return task.id


def enqueue_shopify_scrape(org_id: str, max_pages: int = 100, sections: list = None) -> str:
    task = celery_app.send_task("jobs.kb_ingest.scrape_shopify", args=[org_id, max_pages, sections])
    return task.id


def enqueue_eval_run(suite_id: str, org_id: str) -> str:
    task = celery_app.send_task("jobs.run_evals.run_eval_suite", args=[suite_id, org_id])
    return task.id


def enqueue_geo_scan(org_id: str) -> str:
    task = celery_app.send_task("jobs.geo_scan.run_geo_scan", args=[org_id])
    return task.id
