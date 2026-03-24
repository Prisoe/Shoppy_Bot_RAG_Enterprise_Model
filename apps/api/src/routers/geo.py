from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, GEOReport
from src.deps import get_org

router = APIRouter(prefix="/geo", tags=["GEO"])


@router.post("/scan")
async def trigger_geo_scan(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    from src.worker_client import enqueue_geo_scan
    task_id = enqueue_geo_scan(str(org.id))
    return {"message": "GEO scan queued", "task_id": task_id}


@router.get("/reports", response_model=list[dict])
async def list_reports(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GEOReport).where(GEOReport.org_id == org.id).order_by(GEOReport.created_at.desc()).limit(10)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "answerability_score": r.answerability_score,
            "contradictions_count": len(r.contradictions or []),
            "missing_questions_count": len(r.missing_questions or []),
            "outdated_pages_count": len(r.outdated_pages or []),
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/reports/latest", response_model=dict)
async def latest_report(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GEOReport).where(GEOReport.org_id == org.id).order_by(GEOReport.created_at.desc()).limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        return {"message": "No GEO reports yet. Run a scan first."}
    return {
        "id": str(r.id),
        "answerability_score": r.answerability_score,
        "contradictions": r.contradictions,
        "missing_questions": r.missing_questions,
        "outdated_pages": r.outdated_pages,
        "recommendations": r.recommendations,
        "created_at": r.created_at.isoformat(),
    }
