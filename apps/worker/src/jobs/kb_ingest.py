"""
Background job: process a KB source (URL or file) → chunk → embed → store.
"""
import sys
sys.path.insert(0, "/app/api_src")

import asyncio
import uuid
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import KBSource, KBChunk, KBSourceStatus, KBSourceType
from src.services.kb.chunker import chunk_text
from src.services.kb.embedder import embed_text
from src.services.kb.crawler import fetch_url, discover_shopify_urls, extract_text_from_html

settings = get_settings()

# Use sync engine in Celery workers
from sqlalchemy import create_engine
engine = create_engine(settings.database_url_sync, pool_pre_ping=True)


def get_sync_db():
    return Session(engine)


def process_source(source_id: str, org_id: str):
    """Main ingestion job: fetch → chunk → embed → store."""
    with get_sync_db() as db:
        source = db.query(KBSource).filter(KBSource.id == uuid.UUID(source_id)).first()
        if not source:
            print(f"[ingest] Source {source_id} not found")
            return

        source.status = KBSourceStatus.processing
        db.commit()

        try:
            # ── Fetch content ──────────────────────────────────
            if source.source_type in (KBSourceType.url, KBSourceType.shopify_help):
                content = asyncio.run(fetch_url(source.url))
                if not content:
                    raise ValueError(f"Failed to fetch URL: {source.url}")
                text = content["text"]
                title = content["title"] or source.title
                product_area = content["product_area"] or source.product_area or "general"

            elif source.source_type == KBSourceType.file:
                text, title, product_area = _read_file(source.file_path, source.title, source.product_area)
            else:
                raise ValueError(f"Unknown source type: {source.source_type}")

            if not text or len(text.strip()) < 50:
                raise ValueError("Fetched content is too short or empty")

            # ── Chunk ──────────────────────────────────────────
            chunks = chunk_text(
                text=text,
                source_title=title,
                source_url=source.url or "",
                product_area=product_area,
            )

            # ── Delete old chunks ──────────────────────────────
            db.query(KBChunk).filter(KBChunk.source_id == source.id).delete()
            db.commit()

            # ── Embed + store ──────────────────────────────────
            for chunk in chunks:
                embedding = embed_text(chunk["text"])
                kb_chunk = KBChunk(
                    source_id=source.id,
                    org_id=uuid.UUID(org_id),
                    text=chunk["text"],
                    embedding=embedding,
                    chunk_index=chunk["chunk_index"],
                    metadata_=chunk["metadata"],
                    token_count=chunk["token_count"],
                )
                db.add(kb_chunk)

            source.title = title
            source.status = KBSourceStatus.ready
            source.product_area = product_area
            source.version += 1
            db.commit()
            print(f"[ingest] Source {source_id} ready — {len(chunks)} chunks embedded")

        except Exception as e:
            source.status = KBSourceStatus.failed
            source.error_message = str(e)
            db.commit()
            print(f"[ingest] Source {source_id} FAILED: {e}")
            raise


def scrape_shopify(org_id: str, max_pages: int = 100, sections: list = None):
    """Discover and ingest Shopify Help Center articles."""
    urls = asyncio.run(discover_shopify_urls(max_pages=max_pages, sections=sections))
    print(f"[shopify] Discovered {len(urls)} URLs to ingest for org {org_id}")

    with get_sync_db() as db:
        for url in urls:
            # Skip if already ingested
            existing = db.query(KBSource).filter(
                KBSource.org_id == uuid.UUID(org_id),
                KBSource.url == url,
            ).first()
            if existing:
                continue

            source = KBSource(
                org_id=uuid.UUID(org_id),
                title=url,
                source_type=KBSourceType.shopify_help,
                url=url,
                product_area="general",
                status=KBSourceStatus.pending,
            )
            db.add(source)
            db.commit()
            db.refresh(source)

            # Ingest inline (could also enqueue sub-tasks)
            try:
                process_source(str(source.id), org_id)
            except Exception as e:
                print(f"[shopify] Failed to ingest {url}: {e}")
                continue

    print(f"[shopify] Scrape complete for org {org_id}")


def _read_file(file_path: str, title: str, product_area: str) -> tuple:
    """Read a local file and return (text, title, product_area)."""
    if not file_path:
        raise ValueError("No file path provided")

    ext = file_path.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            raise ValueError("pdfplumber not installed. Add to requirements.")

    elif ext in ("html", "htm"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = extract_text_from_html(f.read(), file_path)
            text = content["text"]
            title = content["title"] or title

    elif ext in ("md", "txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    return text, title, product_area or "general"


# Register as Celery tasks
try:
    from src.worker import celery_app

    @celery_app.task(name="jobs.kb_ingest.process_source", bind=True, max_retries=3)
    def celery_process_source(self, source_id: str, org_id: str):
        try:
            process_source(source_id, org_id)
        except Exception as exc:
            raise self.retry(exc=exc, countdown=30)

    @celery_app.task(name="jobs.kb_ingest.scrape_shopify", bind=True)
    def celery_scrape_shopify(self, org_id: str, max_pages: int = 100, sections: list = None):
        scrape_shopify(org_id, max_pages, sections)

except ImportError:
    pass
