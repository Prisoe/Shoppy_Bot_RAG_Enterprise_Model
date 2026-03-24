"""
KB ingestion service — saves source records and queues background jobs.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import KBSource, KBSourceStatus, KBSourceType
from src.config import get_settings

settings = get_settings()


async def create_kb_source(
    db: AsyncSession,
    org_id: uuid.UUID,
    title: str,
    source_type: KBSourceType,
    url: str = None,
    file_path: str = None,
    product_area: str = "general",
    language: str = "en",
) -> KBSource:
    source = KBSource(
        org_id=org_id,
        title=title,
        source_type=source_type,
        url=url,
        file_path=file_path,
        product_area=product_area,
        language=language,
        status=KBSourceStatus.pending,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


async def get_sources_for_org(db: AsyncSession, org_id: uuid.UUID) -> list[KBSource]:
    result = await db.execute(
        select(KBSource).where(KBSource.org_id == org_id).order_by(KBSource.created_at.desc())
    )
    return result.scalars().all()


async def mark_source_status(
    db: AsyncSession,
    source_id: uuid.UUID,
    status: KBSourceStatus,
    error: str = None,
):
    result = await db.execute(select(KBSource).where(KBSource.id == source_id))
    source = result.scalar_one_or_none()
    if source:
        source.status = status
        if error:
            source.error_message = error
        await db.flush()
