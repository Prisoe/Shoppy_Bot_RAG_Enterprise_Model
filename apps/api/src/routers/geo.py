"""GEO router — runs scan inline when worker unavailable."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, GEOReport, KBChunk, KBSource
from src.deps import get_org
import uuid

router = APIRouter(prefix="/geo", tags=["GEO"])


@router.post("/scan")
async def trigger_geo_scan(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """Run GEO scan — inline (no worker needed)."""
    from src.services.geo.analyzer import analyze_chunks

    # Fetch all chunks with source info
    result = await db.execute(
        select(KBChunk, KBSource)
        .join(KBSource, KBChunk.source_id == KBSource.id)
        .where(KBChunk.org_id == org.id)
    )
    rows = result.all()

    if not rows:
        return {"message": "No KB chunks found. Add KB sources first.", "score": 0}

    chunks = [
        {
            "id": str(chunk.id),
            "text": chunk.text,
            "metadata": chunk.metadata_ or {},
            "source_title": source.title,
            "source_url": source.url or "",
        }
        for chunk, source in rows
    ]

    analysis = analyze_chunks(chunks)

    report = GEOReport(
        org_id=org.id,
        answerability_score=analysis.get("answerability_score", 0),
        contradictions=analysis.get("contradictions", []),
        missing_questions=analysis.get("missing_questions", []),
        outdated_pages=analysis.get("outdated_pages", []),
        recommendations=analysis.get("recommendations", []),
    )
    db.add(report)
    await db.flush()

    return {
        "message": "GEO scan complete",
        "answerability_score": analysis.get("answerability_score", 0),
        "contradictions_found": len(analysis.get("contradictions", [])),
        "missing_questions": len(analysis.get("missing_questions", [])),
        "report_id": str(report.id),
    }


@router.get("/reports", response_model=list[dict])
async def list_reports(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GEOReport).where(GEOReport.org_id == org.id)
        .order_by(GEOReport.created_at.desc()).limit(10)
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
        select(GEOReport).where(GEOReport.org_id == org.id)
        .order_by(GEOReport.created_at.desc()).limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        return {"message": "No GEO reports yet. Run a scan first."}
    return {
        "id": str(r.id),
        "answerability_score": r.answerability_score,
        "contradictions": r.contradictions or [],
        "missing_questions": r.missing_questions or [],
        "outdated_pages": r.outdated_pages or [],
        "recommendations": r.recommendations or [],
        "created_at": r.created_at.isoformat(),
    }
