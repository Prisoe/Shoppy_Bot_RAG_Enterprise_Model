"""GEO scan Celery jobs."""
import sys, uuid
sys.path.insert(0, "/app/api_src")

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.config import get_settings
from src.db.models import KBChunk, KBSource, GEOReport, Organization
from src.services.geo.analyzer import analyze_chunks
from jobs import celery_app

settings = get_settings()
engine = create_engine(settings.database_url_sync, pool_pre_ping=True)


@celery_app.task(name="jobs.geo_scan.run_geo_scan", bind=True)
def run_geo_scan(self, org_id: str):
    """Run GEO scan for one org."""
    with Session(engine) as db:
        rows = db.query(KBChunk, KBSource).join(
            KBSource, KBChunk.source_id == KBSource.id
        ).filter(KBChunk.org_id == uuid.UUID(org_id)).all()

        if not rows:
            return {"error": "no chunks"}

        chunks = [
            {"id": str(c.id), "text": c.text, "metadata": c.metadata_ or {},
             "source_title": s.title, "source_url": s.url or ""}
            for c, s in rows
        ]

        analysis = analyze_chunks(chunks)
        report = GEOReport(
            org_id=uuid.UUID(org_id),
            answerability_score=analysis.get("answerability_score", 0),
            contradictions=analysis.get("contradictions", []),
            missing_questions=analysis.get("missing_questions", []),
            outdated_pages=analysis.get("outdated_pages", []),
            recommendations=analysis.get("recommendations", []),
        )
        db.add(report)
        db.commit()
        print(f"[geo] Report saved — score: {analysis.get('answerability_score')}%")
        return {"score": analysis.get("answerability_score"), "org_id": org_id}


@celery_app.task(name="jobs.geo_scan.run_geo_scan_all_orgs", bind=True)
def run_geo_scan_all_orgs(self):
    """Run GEO scan for every org — triggered by Celery Beat daily."""
    with Session(engine) as db:
        orgs = db.query(Organization).all()
        for org in orgs:
            run_geo_scan.delay(str(org.id))
        print(f"[geo-beat] Queued GEO scan for {len(orgs)} org(s)")
    return {"queued": len(orgs)}


@celery_app.task(name="jobs.kb_ingest.health_check")
def health_check():
    """Hourly health check ping."""
    return {"status": "ok"}
