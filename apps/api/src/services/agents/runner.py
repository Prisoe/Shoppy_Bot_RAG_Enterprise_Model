"""
Agent Runner — core orchestration pipeline for the Support Ops agent.
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.kb.search import similarity_search
from src.services.llm.client import chat_completion
from src.services.llm.prompts import build_support_ops_messages
from src.services.policy.engine import PolicyEngine
from src.services.policy.validators import validate_output_schema
from src.services.tracing.logger import TraceLogger

logger = logging.getLogger(__name__)


async def run_support_ops_agent(
    db: AsyncSession,
    org_id: str,
    ticket_text: str,
    ticket_id: Optional[str] = None,
    order_context: Optional[dict] = None,
    policy_yaml: Optional[str] = None,
    kb_top_k: int = 5,
) -> dict:
    """Full pipeline: policy pre-check → KB → LLM → validate → policy post → approval gate → log."""
    tracer = TraceLogger(db, org_id)
    run = await tracer.create_run(
        agent_name="support_ops",
        ticket_id=ticket_id,
        input_payload={"ticket_text": ticket_text, "order_context": order_context},
    )

    try:
        engine = PolicyEngine(policy_yaml or _default_policy())
        policy_constraints = engine.get_policy_constraints_text()

        pre_decisions = engine.evaluate_input(ticket_text)
        for d in pre_decisions:
            await tracer.log_policy_event(run.id, d, stage="pre")

        if engine.has_blocking_decision(pre_decisions):
            await tracer.finalize_run(run, status="blocked",
                output_payload={"error": "Blocked by policy", "flags": [d.rule_name for d in pre_decisions]})
            return {"status": "blocked", "run_id": str(run.id), "flags": [d.rule_name for d in pre_decisions]}

        kb_chunks = await similarity_search(db=db, org_id=org_id, query=ticket_text, top_k=kb_top_k)
        await tracer.update_retrieved_chunks(run.id, [c["chunk_id"] for c in kb_chunks])

        messages = build_support_ops_messages(ticket_text, kb_chunks, policy_constraints)
        llm_result = await chat_completion(messages=messages, temperature=0.2, max_tokens=2000,
            response_format={"type": "json_object"})

        is_valid, output_data, schema_errors = validate_output_schema(llm_result["content"])
        if not is_valid:
            messages.append({"role": "assistant", "content": llm_result["content"]})
            messages.append({"role": "user", "content": f"Fix schema errors: {schema_errors}. Return valid JSON."})
            llm_result = await chat_completion(messages=messages, temperature=0.1, max_tokens=2000)
            is_valid, output_data, schema_errors = validate_output_schema(llm_result["content"])

        if not is_valid:
            await tracer.finalize_run(run, status="failed",
                output_payload={"error": f"Schema failed: {schema_errors}"}, llm_result=llm_result)
            return {"status": "failed", "run_id": str(run.id), "errors": schema_errors}

        post_decisions = engine.evaluate_output(
            text=output_data.get("draft_reply", ""),
            citations=output_data.get("citations", []),
        )
        for d in post_decisions:
            await tracer.log_policy_event(run.id, d, stage="post")

        needs_approval = (engine.needs_approval(post_decisions) or
            output_data.get("risk", {}).get("needs_approval", False))
        final_status = "needs_approval" if needs_approval else "success"

        await tracer.finalize_run(run, status=final_status, output_payload=output_data, llm_result=llm_result)

        return {
            "status": final_status,
            "run_id": str(run.id),
            "output": output_data,
            "kb_sources_used": len(kb_chunks),
            "tokens": {
                "prompt": llm_result["prompt_tokens"],
                "completion": llm_result["completion_tokens"],
                "cost_usd": llm_result["cost_usd"],
            },
            "policy_flags": [d.rule_name for d in post_decisions],
        }

    except Exception as e:
        logger.exception(f"Agent run failed: {e}")
        await tracer.finalize_run(run, status="failed", output_payload={"error": str(e)})
        raise


def _default_policy() -> str:
    return """
rules:
  - name: No refund promises
    match: ["i will refund", "refund is guaranteed", "you will receive a refund"]
    action: require_approval
    reason: Refund commitments require human review
    prompt_hint: Do not promise or guarantee refunds in the draft reply.

  - name: Block sensitive data requests
    match: ["credit card number", "social security", "sin number", "password", "private key"]
    action: block
    reason: Must never request sensitive credentials

  - name: Require citations
    action: require_citations
    prompt_hint: Every factual claim must cite a KB source.

  - name: No negative language
    match: ["unfortunately", "i apologize for the inconvenience", "we cannot help"]
    action: require_approval
    reason: Shopivoice requires positive framing
    prompt_hint: Avoid apologetic or negative language. Use positive empowering phrasing.
"""
