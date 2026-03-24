"""
GEO scan job — runs the GEO analyzer on all KB chunks for an org.
"""
import sys
sys.path.insert(0, "/app/api_src")

import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.config import get_settings
from src.db.models import KBChunk, GEOReport, Organization
from src.services.geo.analyzer import analyze_chunks

settings = get_settings()
engine = create_engine(settings.database_url_sync, pool_pre_ping=True)


def get_sync_db():
    return Session(engine)


def run_geo_scan(org_id: str):
    with get_sync_db() as db:
        chunks_db = db.query(KBChunk).filter(KBChunk.org_id == uuid.UUID(org_id)).all()
        if not chunks_db:
            print(f"[geo] No chunks found for org {org_id}")
            return

        chunks_data = [
            {
                "id": str(c.id),
                "text": c.text,
                "metadata": c.metadata_ or {},
            }
            for c in chunks_db
        ]

        print(f"[geo] Analyzing {len(chunks_data)} chunks for org {org_id}")
        result = analyze_chunks(chunks_data)

        report = GEOReport(
            org_id=uuid.UUID(org_id),
            answerability_score=result["answerability_score"],
            contradictions=result["contradictions"],
            missing_questions=result["missing_questions"],
            outdated_pages=result["outdated_pages"],
            recommendations=result["recommendations"],
        )
        db.add(report)
        db.commit()
        print(f"[geo] GEO report saved for org {org_id} — score: {result['answerability_score']}")


def run_geo_scan_all_orgs():
    with get_sync_db() as db:
        orgs = db.query(Organization).filter(Organization.is_active == True).all()
        for org in orgs:
            try:
                run_geo_scan(str(org.id))
            except Exception as e:
                print(f"[geo] Failed for org {org.id}: {e}")


try:
    from src.worker import celery_app

    @celery_app.task(name="jobs.geo_scan.run_geo_scan", bind=True)
    def celery_run_geo_scan(self, org_id: str):
        run_geo_scan(org_id)

    @celery_app.task(name="jobs.geo_scan.run_geo_scan_all_orgs")
    def celery_run_geo_scan_all_orgs():
        run_geo_scan_all_orgs()

except ImportError:
    pass
