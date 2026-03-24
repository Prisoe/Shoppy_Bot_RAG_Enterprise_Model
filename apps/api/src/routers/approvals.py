import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, Approval, AgentRun, RunStatus
from src.deps import get_org

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class ApprovalDecision(BaseModel):
    decision: str  # "approved" | "rejected"
    reviewer_id: str
    notes: str = ""


@router.get("/pending", response_model=list[dict])
async def list_pending(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Approval, AgentRun)
        .join(AgentRun, Approval.run_id == AgentRun.id)
        .where(
            AgentRun.org_id == org.id,
            Approval.decision == None,
        )
        .order_by(Approval.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "approval_id": str(a.id),
            "run_id": str(r.id),
            "created_at": a.created_at.isoformat(),
            "input": r.input_payload,
            "output": r.output_payload,
            "agent_name": r.agent_name,
            "cost_usd": r.cost_usd,
        }
        for a, r in rows
    ]


@router.post("/{approval_id}/decide", response_model=dict)
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    result = await db.execute(
        select(Approval, AgentRun)
        .join(AgentRun, Approval.run_id == AgentRun.id)
        .where(Approval.id == uuid.UUID(approval_id), AgentRun.org_id == org.id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Approval not found")

    approval, run = row
    approval.decision = payload.decision
    approval.reviewer_id = payload.reviewer_id
    approval.notes = payload.notes
    approval.decided_at = datetime.utcnow()
    run.status = RunStatus.approved if payload.decision == "approved" else RunStatus.rejected

    await db.commit()
    return {"approval_id": approval_id, "decision": payload.decision}


@router.get("/history", response_model=list[dict])
async def approval_history(
    limit: int = 50,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Approval, AgentRun)
        .join(AgentRun, Approval.run_id == AgentRun.id)
        .where(AgentRun.org_id == org.id, Approval.decision != None)
        .order_by(Approval.decided_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "approval_id": str(a.id),
            "run_id": str(r.id),
            "decision": a.decision,
            "reviewer_id": a.reviewer_id,
            "notes": a.notes,
            "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        }
        for a, r in rows
    ]
