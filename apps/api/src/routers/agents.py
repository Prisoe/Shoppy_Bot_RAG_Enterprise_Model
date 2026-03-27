"""
Agent router — standard + streaming, with vision + LLM tuning support.
POST /agent/run       → full JSON (supports images via base64)
POST /agent/stream    → SSE streaming
"""
import json, uuid, os, base64
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from src.db.session import get_db
from src.db.models import Organization, AgentRun
from src.deps import get_org
from src.schemas.agent import AgentRunRequest, AgentRunResponse
from src.services.agent_runtime.runner import run_agent
from src.services.agent_runtime.prompt_loader import build_system_prompt
from src.services.kb.search import vector_search
from src.middleware.redaction import redact_text

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/run", response_model=AgentRunResponse)
async def run_agent_endpoint(
    request: AgentRunRequest,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    history = [{"role": m.role, "content": m.content}
               for m in (request.conversation_history or [])]

    result = await run_agent(
        db=db, org_id=org.id,
        ticket=request.ticket.model_dump(),
        kb_filters=request.kb_filters.model_dump() if request.kb_filters else {},
        agent_name=request.agent_name,
        conversation_history=history,
        image_data=request.image_data or None,
        llm_overrides=request.llm_overrides or None,
    )
    return result


@router.post("/run-with-image")
async def run_with_image(
    message: str = Form(...),
    product_area: str = Form("general"),
    channel: str = Form("chat"),
    ticket_id: str = Form("UPLOAD-001"),
    api_key: str = Form(...),
    image: Optional[UploadFile] = File(None),
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image + message — the LLM analyzes the screenshot."""
    image_data = None
    if image:
        raw = await image.read()
        b64 = base64.b64encode(raw).decode()
        media_type = image.content_type or "image/png"
        image_data = [{"base64": b64, "media_type": media_type}]

    result = await run_agent(
        db=db, org_id=org.id,
        ticket={"id": ticket_id, "channel": channel, "customer_message": message},
        kb_filters={"product": product_area},
        agent_name="support_ops",
        image_data=image_data,
    )
    return result


@router.post("/stream")
async def stream_agent(
    request: AgentRunRequest,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming — returns merchant_response tokens in real time."""
    from src.config import get_settings
    import anthropic
    settings = get_settings()

    async def generate():
        try:
            raw_msg = request.ticket.customer_message
            redacted, _ = redact_text(raw_msg)
            kb_filters = request.kb_filters.model_dump() if request.kb_filters else {}

            yield f"data: {json.dumps({'type': 'status', 'text': 'Searching knowledge base...'})}\n\n"

            chunks = await vector_search(
                query=redacted, org_id=org.id, db=db,
                product_area=kb_filters.get("product") if kb_filters.get("product") not in (None, "general") else None,
            )

            context_block = "\n\n".join(
                f"[Source: {c['metadata'].get('source_title','Help')} | {c['metadata'].get('source_url','')} | Confidence: {c.get('confidence_score',0.5):.0%}]\n{c['text']}"
                for c in chunks
            ) if chunks else "No KB articles found."

            history = [{"role": m.role, "content": m.content}
                       for m in (request.conversation_history or [])]
            history_block = "\n".join(
                f"{'Merchant' if m['role']=='user' else 'Shoppy Bot'}: {m['content'][:300]}"
                for m in history[-4:]
            ) if history else ""

            system_prompt = build_system_prompt(request.agent_name or "support_ops", "")

            # Build content with optional image
            content_parts = []
            if request.image_data:
                for img in request.image_data:
                    content_parts.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": img.get("media_type","image/png"), "data": img["base64"]}
                    })

            user_text = f"""Ticket: {redacted}
Channel: {request.ticket.channel}
{f"History:{chr(10)}{history_block}" if history_block else ""}
KB Articles ({len(chunks)} found):
{context_block}

Respond with just the merchant_response — warm, human, empathetic. Ask probing questions if context is missing. Include source URL at end."""

            content_parts.append({"type": "text", "text": user_text})

            yield f"data: {json.dumps({'type': 'status', 'text': 'Generating response...'})}\n\n"

            overrides = request.llm_overrides or {}
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            full_text = ""
            input_tokens = output_tokens = 0

            with client.messages.stream(
                model=settings.llm_model_id or "claude-haiku-4-5-20251001",
                max_tokens=overrides.get("max_tokens", 1024),
                temperature=overrides.get("temperature", 0.3),
                system=system_prompt,
                messages=[{"role": "user", "content": content_parts if len(content_parts) > 1 else user_text}],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"
                final = stream.get_final_message()
                input_tokens  = final.usage.input_tokens
                output_tokens = final.usage.output_tokens

            model = settings.llm_model_id or ""
            cost = (input_tokens * (3.0 if "sonnet" in model else 0.80) +
                    output_tokens * (15.0 if "sonnet" in model else 4.0)) / 1_000_000

            citations = [
                {"source_title": c["metadata"].get("source_title",""),
                 "source_url":   c["metadata"].get("source_url",""),
                 "confidence_score": c.get("confidence_score", 0.5)}
                for c in chunks[:3]
            ]
            yield f"data: {json.dumps({'type':'done','cost_usd':cost,'chunks_used':len(chunks),'citations':citations,'input_tokens':input_tokens,'output_tokens':output_tokens})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type':'error','text':str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


@router.get("/runs", response_model=list[dict])
async def list_runs(limit: int = 50, status: str = None,
                    org: Organization = Depends(get_org), db: AsyncSession = Depends(get_db)):
    query = select(AgentRun).where(AgentRun.org_id == org.id).order_by(AgentRun.created_at.desc()).limit(limit)
    if status:
        query = query.where(AgentRun.status == status)
    result = await db.execute(query)
    return [{"run_id": str(r.id), "status": r.status.value, "agent_name": r.agent_name,
             "cost_usd": r.cost_usd, "latency_ms": r.latency_ms,
             "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
             "created_at": r.created_at.isoformat(), "output": r.output_payload}
            for r in result.scalars().all()]


@router.get("/runs/{run_id}", response_model=dict)
async def get_run(run_id: str, org: Organization = Depends(get_org), db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    result = await db.execute(select(AgentRun).where(AgentRun.id == uuid.UUID(run_id), AgentRun.org_id == org.id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    return {"run_id": str(run.id), "status": run.status.value, "agent_name": run.agent_name,
            "input": run.input_payload, "output": run.output_payload,
            "model_id": run.model_id, "cost_usd": run.cost_usd,
            "latency_ms": run.latency_ms, "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens, "created_at": run.created_at.isoformat()}
