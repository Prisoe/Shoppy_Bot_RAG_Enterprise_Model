"""
KB ingestion job — runs in Celery worker.
Lives at /app/jobs/kb_ingest.py (outside src/ to avoid import collision).
"""
import sys
import os
sys.path.insert(0, "/app/api_src")

import asyncio
import uuid
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import KBSource, KBChunk, KBSourceStatus, KBSourceType
from src.services.kb.chunker import chunk_text
from src.services.kb.embedder import embed_text
from src.services.kb.crawler import fetch_url, discover_shopify_urls

settings = get_settings()
engine = create_engine(settings.database_url_sync, pool_pre_ping=True)

from jobs import celery_app  # import from jobs package


@celery_app.task(name="jobs.kb_ingest.process_source", bind=True, max_retries=3)
def process_source(self, source_id: str, org_id: str):
    """Fetch → chunk → embed → store a single KB source."""
    with Session(engine) as db:
        source = db.query(KBSource).filter(KBSource.id == uuid.UUID(source_id)).first()
        if not source:
            return {"error": f"Source {source_id} not found"}

        source.status = KBSourceStatus.processing
        db.commit()

        try:
            content = asyncio.run(fetch_url(source.url))
            if not content:
                source.status = KBSourceStatus.failed
                source.error_message = "Could not fetch URL (blocked or empty)"
                db.commit()
                return {"error": "fetch failed"}

            chunks = chunk_text(
                text=content["text"],
                source_title=content["title"] or source.title,
                source_url=source.url,
                product_area=content.get("product_area") or source.product_area or "general",
            )

            for chunk in chunks:
                embedding = embed_text(chunk["text"])
                db.add(KBChunk(
                    source_id=source.id,
                    org_id=source.org_id,
                    text=chunk["text"],
                    embedding=embedding,
                    chunk_index=chunk["chunk_index"],
                    metadata_=chunk["metadata"],
                    token_count=chunk["token_count"],
                ))

            source.status = KBSourceStatus.ready
            source.title = content["title"] or source.title
            db.commit()
            print(f"[ingest] {source.title} — {len(chunks)} chunks")
            return {"chunks": len(chunks)}

        except Exception as e:
            source.status = KBSourceStatus.failed
            source.error_message = str(e)[:500]
            db.commit()
            raise self.retry(exc=e, countdown=30)


@celery_app.task(name="jobs.kb_ingest.scrape_shopify", bind=True)
def scrape_shopify(self, org_id: str, max_pages: int = 30, sections: list = None):
    """Discover and ingest Shopify help center URLs."""
    urls = asyncio.run(discover_shopify_urls(max_pages=max_pages, sections=sections))
    print(f"[scrape] Found {len(urls)} URLs to ingest")

    with Session(engine) as db:
        existing = {s.url for s in db.query(KBSource).filter(KBSource.org_id == uuid.UUID(org_id)).all()}

    queued = 0
    for url in urls:
        if url in existing:
            continue
        with Session(engine) as db:
            source = KBSource(
                org_id=uuid.UUID(org_id),
                title=url.split("/")[-1].replace("-", " ").title(),
                source_type=KBSourceType.url,
                url=url,
                product_area=url.split("/")[5] if len(url.split("/")) > 5 else "general",
                status=KBSourceStatus.pending,
            )
            db.add(source)
            db.commit()
            process_source.delay(str(source.id), org_id)
            queued += 1

    print(f"[scrape] Queued {queued} new sources")
    return {"queued": queued}
