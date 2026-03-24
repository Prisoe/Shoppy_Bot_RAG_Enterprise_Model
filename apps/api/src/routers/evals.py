import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, EvalSuite, EvalRun
from src.deps import get_org
from src.schemas.evals import EvalSuiteCreate, EvalSuiteOut, EvalRunOut

router = APIRouter(prefix="/evals", tags=["Evals"])


@router.post("/suites", response_model=EvalSuiteOut)
async def create_suite(
    payload: EvalSuiteCreate,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    suite = EvalSuite(
        org_id=org.id,
        name=payload.name,
        dataset_path=payload.dataset_path,
        metrics_config=payload.metrics_config or {},
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return suite


@router.get("/suites", response_model=list[EvalSuiteOut])
async def list_suites(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvalSuite).where(EvalSuite.org_id == org.id).order_by(EvalSuite.created_at.desc())
    )
    return result.scalars().all()


@router.post("/suites/{suite_id}/run")
async def trigger_eval_run(
    suite_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvalSuite).where(EvalSuite.id == uuid.UUID(suite_id), EvalSuite.org_id == org.id)
    )
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(404, "Suite not found")

    from src.worker_client import enqueue_eval_run
    task_id = enqueue_eval_run(str(suite.id), str(org.id))
    return {"message": "Eval run queued", "task_id": task_id}


@router.get("/suites/{suite_id}/runs", response_model=list[EvalRunOut])
async def list_eval_runs(
    suite_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvalRun).where(EvalRun.suite_id == uuid.UUID(suite_id)).order_by(EvalRun.created_at.desc())
    )
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=EvalRunOut)
async def get_eval_run(
    run_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EvalRun).where(EvalRun.id == uuid.UUID(run_id)))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Eval run not found")
    return run
