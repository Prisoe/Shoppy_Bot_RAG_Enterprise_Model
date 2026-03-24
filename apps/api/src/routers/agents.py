from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, AgentRun
from src.deps import get_org
from src.schemas.agent import AgentRunRequest, AgentRunResponse
from src.services.agent_runtime.runner import run_agent
import uuid

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/run", response_model=AgentRunResponse)
async def run_agent_endpoint(
    request: AgentRunRequest,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """
    Main agent endpoint. Supports multi-turn conversation via conversation_history.
    """
    history = []
    if request.conversation_history:
        history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

    result = await run_agent(
        db=db,
        org_id=org.id,
        ticket=request.ticket.model_dump(),
        kb_filters=request.kb_filters.model_dump() if request.kb_filters else {},
        agent_name=request.agent_name,
        conversation_history=history,
    )
    return result


@router.get("/runs", response_model=list[dict])
async def list_runs(
    limit: int = 50,
    status: str = None,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    query = select(AgentRun).where(AgentRun.org_id == org.id).order_by(AgentRun.created_at.desc()).limit(limit)
    if status:
        query = query.where(AgentRun.status == status)
    result = await db.execute(query)
    runs = result.scalars().all()
    return [
        {
            "run_id": str(r.id),
            "status": r.status.value,
            "agent_name": r.agent_name,
            "cost_usd": r.cost_usd,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "created_at": r.created_at.isoformat(),
            "output": r.output_payload,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=dict)
async def get_run(
    run_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == uuid.UUID(run_id), AgentRun.org_id == org.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        from fastapi import HTTPException
        raise HTTPException(404, "Run not found")
    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "agent_name": run.agent_name,
        "input": run.input_payload,
        "output": run.output_payload,
        "retrieved_chunk_ids": run.retrieved_chunk_ids,
        "model_id": run.model_id,
        "cost_usd": run.cost_usd,
        "latency_ms": run.latency_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "created_at": run.created_at.isoformat(),
    }
