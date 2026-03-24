"""
Eval runner — executes a test suite against the agent and scores results.
"""
import sys
sys.path.insert(0, "/app/api_src")

import json
import uuid
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.config import get_settings
from src.db.models import EvalSuite, EvalRun
from src.services.llm.client import call_llm
from src.services.agent_runtime.prompt_loader import build_system_prompt
from src.services.agent_runtime.response_schema import parse_agent_response

settings = get_settings()
engine = create_engine(settings.database_url_sync, pool_pre_ping=True)


def get_sync_db():
    return Session(engine)


def run_eval_suite(suite_id: str, org_id: str):
    """
    Loads a JSONL dataset and runs each case through the agent.
    Each line in the dataset:
    {
      "input": { "ticket": {...}, "kb_filters": {...} },
      "expected": {
        "must_contain": ["refund policy"],
        "must_not_contain": ["credit card"],
        "needs_approval": false,
        "has_citations": true
      }
    }
    """
    with get_sync_db() as db:
        suite = db.query(EvalSuite).filter(EvalSuite.id == uuid.UUID(suite_id)).first()
        if not suite:
            print(f"[evals] Suite {suite_id} not found")
            return

        dataset_path = os.path.join(settings.evals_dir, suite.dataset_path)
        if not os.path.exists(dataset_path):
            print(f"[evals] Dataset not found: {dataset_path}")
            return

        with open(dataset_path) as f:
            cases = [json.loads(line) for line in f if line.strip()]

        system_prompt = build_system_prompt("support_ops")
        failures = []
        passed = 0

        for i, case in enumerate(cases):
            ticket = case.get("input", {}).get("ticket", {})
            expected = case.get("expected", {})

            user_msg = f"""
Ticket: {ticket.get('customer_message', '')}
Channel: {ticket.get('channel', 'chat')}

Return only valid JSON matching the output schema.
"""
            try:
                result = call_llm(system_prompt, user_msg, max_tokens=1024)
                parsed = parse_agent_response(result["text"])
                score_result = _score_case(parsed, expected, i)

                if score_result["pass"]:
                    passed += 1
                else:
                    failures.append(score_result)

            except Exception as e:
                failures.append({"case_index": i, "error": str(e), "pass": False})

        scores = {
            "pass_rate": round(passed / max(len(cases), 1) * 100, 1),
            "total": len(cases),
            "passed": passed,
            "failed": len(failures),
        }

        eval_run = EvalRun(
            suite_id=suite.id,
            model_id=settings.bedrock_llm_model_id,
            scores=scores,
            failures=failures,
            total_cases=len(cases),
            passed=passed,
            failed=len(failures),
        )
        db.add(eval_run)
        db.commit()
        print(f"[evals] Suite {suite_id} complete — {passed}/{len(cases)} passed")


def _score_case(parsed: dict, expected: dict, index: int) -> dict:
    issues = []
    merchant_response = parsed.get("merchant_response", "").lower()
    ssa_guidance = str(parsed.get("ssa_guidance", "")).lower()
    combined = merchant_response + " " + ssa_guidance

    for term in expected.get("must_contain", []):
        if term.lower() not in combined:
            issues.append(f"Missing expected term: '{term}'")

    for term in expected.get("must_not_contain", []):
        if term.lower() in combined:
            issues.append(f"Contains forbidden term: '{term}'")

    if "needs_approval" in expected:
        actual = parsed.get("risk", {}).get("needs_approval", False)
        if actual != expected["needs_approval"]:
            issues.append(f"needs_approval expected {expected['needs_approval']} got {actual}")

    if expected.get("has_citations") and not parsed.get("citations"):
        issues.append("Expected citations but none found")

    return {
        "case_index": index,
        "pass": len(issues) == 0,
        "issues": issues,
    }


try:
    from src.worker import celery_app

    @celery_app.task(name="jobs.run_evals.run_eval_suite", bind=True)
    def celery_run_eval_suite(self, suite_id: str, org_id: str):
        run_eval_suite(suite_id, org_id)

except ImportError:
    pass
