"""
Core agent runner — orchestrates the full RAG + guardrails pipeline.
Supports multi-turn conversation history.
"""
import time
import json
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import get_settings
from src.db.models import AgentRun, PolicyRule, PolicyEvent, Approval, RunStatus, PolicyAction
from src.services.kb.search import vector_search
from src.services.llm.client import call_llm
from src.services.agent_runtime.prompt_loader import build_system_prompt
from src.services.agent_runtime.response_schema import parse_agent_response, validate_response, fix_response_with_llm
from src.services.policy.engine import load_rules_from_yaml, evaluate_pre, evaluate_post, most_severe_action
from src.middleware.redaction import redact_text

settings = get_settings()


async def run_agent(
    db: AsyncSession,
    org_id: uuid.UUID,
    ticket: dict,
    kb_filters: dict = None,
    agent_name: str = "support_ops",
    conversation_history: list = None,
    image_data: list = None,
    llm_overrides: dict = None,
) -> dict:
    """
    Full pipeline with multi-turn conversation support.
    conversation_history: list of {"role": "user"|"assistant", "content": "..."}
    """
    start_time = time.monotonic()
    kb_filters = kb_filters or {}
    run_id = uuid.uuid4()
    conversation_history = conversation_history or []

    # ── 1. Redact PII ──────────────────────────────────────────────────────
    raw_message = ticket.get("customer_message", "")
    redacted_message, redaction_labels = redact_text(raw_message)
    ticket_redacted = {**ticket, "customer_message": redacted_message}

    # ── 2. Load active policy rules ────────────────────────────────────────
    rules_result = await db.execute(
        select(PolicyRule).where(
            PolicyRule.org_id == org_id,
            PolicyRule.is_enabled == True,
        )
    )
    policy_rules_db = rules_result.scalars().all()

    all_rules = []
    rule_map = {}
    for pr in policy_rules_db:
        parsed = load_rules_from_yaml(pr.rule_yaml)
        for r in parsed:
            all_rules.append(r)
            rule_map[r.get("name", "")] = pr

    # ── 3. Policy PRE-check ────────────────────────────────────────────────
    pre_decisions = evaluate_pre(redacted_message, all_rules)
    pre_action = most_severe_action(pre_decisions)

    agent_run = AgentRun(
        id=run_id,
        org_id=org_id,
        agent_name=agent_name,
        input_payload={"ticket": ticket_redacted, "kb_filters": kb_filters},
        status=RunStatus.success,
    )
    db.add(agent_run)
    await db.flush()

    for decision in pre_decisions:
        pr = rule_map.get(decision.rule_name)
        db.add(PolicyEvent(
            run_id=run_id,
            rule_id=pr.id if pr else None,
            rule_name=decision.rule_name,
            action_taken=decision.action,
            detail=decision.detail,
            phase="pre",
        ))

    if pre_action == PolicyAction.block:
        agent_run.status = RunStatus.blocked
        agent_run.output_payload = {"error": "Blocked by policy", "flags": [d.rule_name for d in pre_decisions]}
        agent_run.latency_ms = int((time.monotonic() - start_time) * 1000)
        await db.flush()
        return {"run_id": str(run_id), "status": "blocked", "reason": [d.rule_name for d in pre_decisions]}

    # ── 4. Build system prompt ─────────────────────────────────────────────
    policy_summary = "\n".join(f"- {r.get('name')}: {r.get('action')}" for r in all_rules)
    system_prompt = build_system_prompt(agent_name, policy_summary)

    # ── 5. KB search ───────────────────────────────────────────────────────
    # Build a richer search query using conversation history context
    search_query = redacted_message
    if conversation_history:
        # Include last 2 turns for better context
        recent = conversation_history[-4:]
        context_text = " ".join(
            msg.get("content", "") for msg in recent if msg.get("role") == "user"
        )
        if context_text:
            search_query = f"{context_text} {redacted_message}"

    chunks = await vector_search(
        query=search_query,
        org_id=org_id,
        db=db,
        product_area=kb_filters.get("product") if kb_filters.get("product") != "general" else None,
    )

    # Format retrieved context with source URLs
    context_block = "\n\n".join(
        f"[Source {i+1}: {c['metadata'].get('source_title', 'Shopify Help')} | URL: {c['metadata'].get('source_url', '')} | Confidence: {c.get('confidence_score', 0.5):.0%}]\n{c['text']}"
        for i, c in enumerate(chunks)
    ) if chunks else "No KB articles found for this query."

    # ── 6. Build conversation-aware user message ───────────────────────────
    # Format conversation history
    history_block = ""
    if conversation_history:
        history_lines = []
        for msg in conversation_history[-6:]:  # last 3 exchanges
            role = "Merchant" if msg.get("role") == "user" else "Prosper (previous)"
            content = msg.get("content", "")[:500]  # truncate long history
            history_lines.append(f"{role}: {content}")
        history_block = "\n".join(history_lines)

    user_message = f"""
## Current Ticket
- Ticket ID: {ticket_redacted.get('id', 'N/A')}
- Channel: {ticket_redacted.get('channel', 'chat')}
- Current Message: {ticket_redacted.get('customer_message', '')}

{f"## Conversation History (previous turns){chr(10)}{history_block}{chr(10)}" if history_block else ""}

## Order Context
{json.dumps(ticket_redacted.get('order_context', {}), indent=2) if ticket_redacted.get('order_context') else "No order context provided."}

## Retrieved Knowledge Base Articles ({len(chunks)} found)
{context_block}

## Required Output
Return ONLY a valid JSON object:
{{
  "shoppy_thoughts": "Internal reasoning about the issue, what KB articles apply, what context is missing",
  "ssa_guidance": ["Step 1...", "Step 2..."],
  "merchant_response": "Direct, helpful response to the merchant with specific steps from KB if available",
  "citations": [
    {{"chunk_id": "id", "source_title": "Article title", "source_url": "https://...", "quote": "relevant excerpt"}}
  ],
  "risk": {{
    "needs_approval": false,
    "flags": []
  }}
}}

Important: If KB articles were found, use them to provide specific step-by-step guidance. Include the source URL in citations so merchants can read the full article.
"""

    # ── 7. LLM call ────────────────────────────────────────────────────────
    # Apply per-request LLM overrides (temperature, max_tokens, top_k, top_p)
    llm_kwargs = {}
    if llm_overrides:
        for k in ("temperature", "max_tokens", "top_k", "top_p"):
            if k in llm_overrides:
                llm_kwargs[k] = llm_overrides[k]
    if image_data:
        llm_kwargs["image_data"] = image_data

    llm_result = call_llm(system_prompt=system_prompt, user_message=user_message, **llm_kwargs)
    raw_output = llm_result["text"]

    # ── 8. Parse + validate ────────────────────────────────────────────────
    parsed = parse_agent_response(raw_output)
    is_valid, issues = validate_response(parsed)
    if not is_valid:
        parsed = fix_response_with_llm(system_prompt, raw_output)

    has_citations = bool(parsed.get("citations"))

    # ── 9. Policy POST-check ───────────────────────────────────────────────
    output_text = f"{parsed.get('merchant_response', '')} {parsed.get('ssa_guidance', '')}"
    post_decisions = evaluate_post(output_text, all_rules, has_citations=has_citations)
    post_action = most_severe_action(post_decisions)

    for decision in post_decisions:
        pr = rule_map.get(decision.rule_name)
        db.add(PolicyEvent(
            run_id=run_id,
            rule_id=pr.id if pr else None,
            rule_name=decision.rule_name,
            action_taken=decision.action,
            detail=decision.detail,
            phase="post",
        ))

    needs_approval = (
        parsed.get("risk", {}).get("needs_approval", False)
        or post_action in (PolicyAction.require_approval,)
    )
    # Only flag needs_approval if there's genuinely no KB match AND it's high risk
    # KB miss alone shouldn't require approval
    if chunks and not any(f in str(parsed.get("risk", {}).get("flags", [])) for f in ["refund_promise", "guarantee"]):
        needs_approval = False

    flags = parsed.get("risk", {}).get("flags", []) + [d.rule_name for d in post_decisions if d.action != PolicyAction.allow]
    parsed["risk"] = {"needs_approval": needs_approval, "flags": flags}

    if post_action == PolicyAction.block:
        status = RunStatus.blocked
    elif needs_approval:
        status = RunStatus.needs_approval
    else:
        status = RunStatus.success

    # ── 10. Update run record ──────────────────────────────────────────────
    latency = int((time.monotonic() - start_time) * 1000)
    agent_run.output_payload = parsed
    agent_run.retrieved_chunk_ids = [c["chunk_id"] for c in chunks]
    agent_run.model_id = llm_result["model_id"]
    agent_run.input_tokens = llm_result["input_tokens"]
    agent_run.output_tokens = llm_result["output_tokens"]
    agent_run.cost_usd = llm_result["cost_usd"]
    agent_run.latency_ms = latency
    agent_run.status = status

    if needs_approval:
        db.add(Approval(run_id=run_id))

    await db.flush()

    return {
        "run_id": str(run_id),
        "status": status.value,
        "output": parsed,
        "chunks_used": len(chunks),
        "latency_ms": latency,
        "cost_usd": llm_result["cost_usd"],
        "tokens": {"input": llm_result["input_tokens"], "output": llm_result["output_tokens"]},
    }
