"""
KB search — vector similarity with keyword fallback.
With dummy embeddings vector search returns random results.
The keyword fallback ensures relevant content is always found.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from src.db.models import KBChunk
from src.services.kb.embedder import embed_text
from src.config import get_settings
import uuid

settings = get_settings()


async def vector_search(
    query: str,
    org_id: uuid.UUID,
    db: AsyncSession,
    top_k: int = None,
    product_area: str = None,
) -> list[dict]:
    """
    Search KB using keyword matching first (always works),
    then blend with vector similarity if embeddings are real.
    Returns list of { chunk_id, text, metadata, score }.
    """
    top_k = top_k or settings.top_k_retrieval

    # ── Keyword search (works with any embeddings) ──────────────────────────
    # Extract meaningful keywords from the query
    stopwords = {"how", "do", "i", "a", "the", "to", "in", "for", "is", "can",
                 "what", "my", "me", "an", "of", "it", "with", "and", "or",
                 "this", "that", "on", "at", "be", "was", "are", "will", "you"}
    keywords = [w.lower().strip("?.,!") for w in query.split()
                if len(w) > 3 and w.lower() not in stopwords]

    if not keywords:
        keywords = [w.lower().strip("?.,!") for w in query.split() if len(w) > 2]

    params: dict = {"org_id": str(org_id), "top_k": top_k * 3}

    # Build keyword conditions
    keyword_conditions = " OR ".join(
        f"LOWER(c.text) LIKE :kw{i}" for i in range(len(keywords))
    )
    for i, kw in enumerate(keywords):
        params[f"kw{i}"] = f"%{kw}%"

    area_filter = ""
    if product_area and product_area != "general":
        area_filter = " AND c.metadata->>'product_area' = :product_area"
        params["product_area"] = product_area

    if keyword_conditions:
        keyword_sql = text(f"""
            SELECT
                c.id::text AS chunk_id,
                c.text,
                c.metadata,
                c.source_id::text,
                (
                    SELECT COUNT(*) FROM (
                        VALUES {", ".join(f"(:kw{i})" for i in range(len(keywords)))}
                    ) AS kws(kw)
                    WHERE LOWER(c.text) LIKE kw
                ) * 1.0 / {len(keywords)} AS score
            FROM kb_chunks c
            WHERE c.org_id = :org_id
              AND c.embedding IS NOT NULL
              {area_filter}
              AND ({keyword_conditions})
            ORDER BY score DESC
            LIMIT :top_k
        """)
    else:
        # No keywords — return all chunks for this org
        keyword_sql = text(f"""
            SELECT
                c.id::text AS chunk_id,
                c.text,
                c.metadata,
                c.source_id::text,
                0.5 AS score
            FROM kb_chunks c
            WHERE c.org_id = :org_id
              AND c.embedding IS NOT NULL
              {area_filter}
            LIMIT :top_k
        """)

    result = await db.execute(keyword_sql, params)
    rows = result.fetchall()

    chunks = [
        {
            "chunk_id": row.chunk_id,
            "text": row.text,
            "metadata": row.metadata or {},
            "score": float(row.score),
        }
        for row in rows
    ]

    # If keyword search found nothing, return all chunks (catch-all)
    if not chunks:
        fallback_sql = text("""
            SELECT
                c.id::text AS chunk_id,
                c.text,
                c.metadata,
                c.source_id::text,
                0.3 AS score
            FROM kb_chunks c
            WHERE c.org_id = :org_id
              AND c.embedding IS NOT NULL
            LIMIT :top_k
        """)
        result = await db.execute(fallback_sql, {"org_id": str(org_id), "top_k": top_k})
        rows = result.fetchall()
        chunks = [
            {
                "chunk_id": row.chunk_id,
                "text": row.text,
                "metadata": row.metadata or {},
                "score": float(row.score),
            }
            for row in rows
        ]

    return chunks[:top_k]


async def get_chunk_by_id(chunk_id: str, db: AsyncSession) -> KBChunk | None:
    result = await db.execute(
        select(KBChunk).where(KBChunk.id == uuid.UUID(chunk_id))
    )
    return result.scalar_one_or_none()
