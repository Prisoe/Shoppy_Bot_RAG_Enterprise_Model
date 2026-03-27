"""Eval runner job stub."""
import sys
sys.path.insert(0, "/app/api_src")
from jobs import celery_app

@celery_app.task(name="jobs.run_evals.run_eval_suite", bind=True)
def run_eval_suite(self, suite_id: str, org_id: str):
    print(f"[evals] Running suite {suite_id} for org {org_id}")
    return {"status": "complete"}
