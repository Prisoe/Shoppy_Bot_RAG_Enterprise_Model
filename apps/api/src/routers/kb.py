import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.db.session import get_db
from src.db.models import Organization, KBSource, KBChunk, KBSourceType, KBSourceStatus
from src.deps import get_org
from src.schemas.kb import KBSourceCreate, KBSourceOut, KBQueryRequest, KBChunkOut, ShopifyScrapeRequest
from src.services.kb.ingest import create_kb_source, get_sources_for_org
from src.services.kb.search import vector_search
from src.config import get_settings
import os, shutil

settings = get_settings()
router = APIRouter(prefix="/kb", tags=["Knowledge Base"])


@router.post("/sources", response_model=KBSourceOut)
async def add_kb_source(
    payload: KBSourceCreate,
    background_tasks: BackgroundTasks,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """Register a URL-based KB source and kick off ingestion."""
    if payload.source_type == "url" and not payload.url:
        raise HTTPException(400, "URL required for type=url")

    source = await create_kb_source(
        db=db,
        org_id=org.id,
        title=payload.title,
        source_type=KBSourceType(payload.source_type),
        url=payload.url,
        product_area=payload.product_area,
        language=payload.language,
    )
    await db.commit()

    # Kick off background ingestion via Celery
    from src.worker_client import enqueue_ingest
    enqueue_ingest(str(source.id), str(org.id))

    return source


@router.post("/upload", response_model=KBSourceOut)
async def upload_kb_file(
    file: UploadFile = File(...),
    product_area: str = "general",
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file (PDF/TXT/MD/HTML) as a KB source."""
    os.makedirs(settings.local_storage_path, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    dest = os.path.join(settings.local_storage_path, f"{file_id}{ext}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    source = await create_kb_source(
        db=db,
        org_id=org.id,
        title=file.filename,
        source_type=KBSourceType.file,
        file_path=dest,
        product_area=product_area,
    )
    await db.commit()

    from src.worker_client import enqueue_ingest
    enqueue_ingest(str(source.id), str(org.id))

    return source


@router.post("/scrape-shopify")
async def scrape_shopify(
    payload: ShopifyScrapeRequest,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a crawl of the Shopify public Help Center."""
    from src.worker_client import enqueue_shopify_scrape
    task_id = enqueue_shopify_scrape(str(org.id), payload.max_pages, payload.sections)
    return {"message": "Shopify scrape queued", "task_id": task_id}


@router.get("/sources", response_model=list[KBSourceOut])
async def list_sources(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    sources = await get_sources_for_org(db, org.id)
    return sources


@router.get("/sources/{source_id}/chunks")
async def list_chunks(
    source_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KBChunk)
        .where(KBChunk.source_id == uuid.UUID(source_id), KBChunk.org_id == org.id)
        .order_by(KBChunk.chunk_index)
        .limit(100)
    )
    chunks = result.scalars().all()
    return [
        {
            "chunk_id": str(c.id),
            "text": c.text[:300] + "..." if len(c.text) > 300 else c.text,
            "chunk_index": c.chunk_index,
            "token_count": c.token_count,
            "metadata": c.metadata_,
            "has_embedding": c.embedding is not None,
        }
        for c in chunks
    ]


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KBSource).where(KBSource.id == uuid.UUID(source_id), KBSource.org_id == org.id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")
    await db.delete(source)
    await db.commit()
    return {"deleted": source_id}


@router.post("/query", response_model=list[KBChunkOut])
async def query_kb(
    payload: KBQueryRequest,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    """Direct KB query — returns top matching chunks."""
    results = await vector_search(
        query=payload.query,
        org_id=org.id,
        db=db,
        top_k=payload.top_k,
        product_area=payload.product_area,
    )
    return results


@router.get("/stats")
async def kb_stats(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    total_sources = await db.scalar(
        select(func.count(KBSource.id)).where(KBSource.org_id == org.id)
    )
    total_chunks = await db.scalar(
        select(func.count(KBChunk.id)).where(KBChunk.org_id == org.id)
    )
    embedded_chunks = await db.scalar(
        select(func.count(KBChunk.id)).where(
            KBChunk.org_id == org.id, KBChunk.embedding.isnot(None)
        )
    )
    ready_sources = await db.scalar(
        select(func.count(KBSource.id)).where(
            KBSource.org_id == org.id, KBSource.status == KBSourceStatus.ready
        )
    )
    return {
        "total_sources": total_sources,
        "ready_sources": ready_sources,
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
    }
