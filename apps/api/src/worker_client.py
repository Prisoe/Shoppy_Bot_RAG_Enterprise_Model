"""
Worker client — enqueues Celery tasks OR runs inline if worker is down.
Inline mode means KB ingestion works even without a working Celery worker.
"""
from celery import Celery
from src.config import get_settings

settings = get_settings()
celery_app = Celery("rag_worker", broker=settings.redis_url, backend=settings.redis_url)


def _try_enqueue(task_name: str, args: list) -> str:
    try:
        task = celery_app.send_task(task_name, args=args)
        return task.id
    except Exception as e:
        print(f"[worker_client] Celery unavailable: {e} — task will run inline")
        return "inline"


def enqueue_ingest(source_id: str, org_id: str) -> str:
    return _try_enqueue("jobs.kb_ingest.process_source", [source_id, org_id])


def enqueue_shopify_scrape(org_id: str, max_pages: int = 30, sections: list = None) -> str:
    return _try_enqueue("jobs.kb_ingest.scrape_shopify", [org_id, max_pages, sections])


def enqueue_eval_run(suite_id: str, org_id: str) -> str:
    return _try_enqueue("jobs.run_evals.run_eval_suite", [suite_id, org_id])


def enqueue_geo_scan(org_id: str) -> str:
    return _try_enqueue("jobs.geo_scan.run_geo_scan", [org_id])
