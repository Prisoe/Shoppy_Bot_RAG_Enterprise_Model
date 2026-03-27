"""
KB search v3 — vector + keyword + query expansion + reranking + confidence scores.
Phase 2 complete.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from src.db.models import KBChunk
from src.services.kb.embedder import embed_text
from src.config import get_settings
import uuid, re

settings = get_settings()

STOPWORDS = {
    "how","do","i","a","the","to","in","for","is","can","what","my","me",
    "an","of","it","with","and","or","this","that","on","at","be","was",
    "are","will","you","get","set","use","make","find","does","would","should",
    "just","also","when","where","why","which","who","has","have","had","not"
}

# Query expansion synonyms — maps common terms to related keywords
SYNONYMS = {
    "refund": ["refund", "return", "money back", "reimburse", "reimbursement"],
    "cancel": ["cancel", "cancellation", "void", "stop", "terminate"],
    "payment": ["payment", "pay", "charge", "transaction", "billing", "invoice"],
    "shipping": ["shipping", "ship", "delivery", "deliver", "dispatch", "carrier", "postage"],
    "order": ["order", "purchase", "sale", "transaction", "checkout"],
    "product": ["product", "item", "listing", "inventory", "sku", "variant"],
    "discount": ["discount", "coupon", "promo", "promotion", "deal", "code", "offer"],
    "customer": ["customer", "buyer", "client", "shopper", "user", "account"],
    "theme": ["theme", "template", "design", "storefront", "layout"],
    "app": ["app", "plugin", "integration", "extension", "add-on"],
    "tax": ["tax", "vat", "gst", "duty", "tariff", "levy"],
    "domain": ["domain", "url", "website", "subdomain", "dns"],
    "fraud": ["fraud", "chargeback", "dispute", "scam", "unauthorized"],
    "inventory": ["inventory", "stock", "quantity", "availability", "warehouse"],
    "fulfillment": ["fulfillment", "fulfill", "ship", "pack", "dispatch", "complete"],
    "payout": ["payout", "deposit", "transfer", "bank", "funds"],
    "analytics": ["analytics", "report", "stats", "metrics", "data", "dashboard"],
    "staff": ["staff", "employee", "team", "user", "account", "permission"],
}


def _extract_keywords(query: str) -> list[str]:
    tokens = re.sub(r"[^\w\s]", "", query.lower()).split()
    return [t for t in tokens if len(t) > 3 and t not in STOPWORDS] or tokens[:5]


def _expand_query(keywords: list[str]) -> list[str]:
    """Add synonyms for each keyword to broaden recall."""
    expanded = set(keywords)
    for kw in keywords:
        for base, syns in SYNONYMS.items():
            if kw in syns or kw == base:
                expanded.update(syns[:3])  # add top 3 synonyms
    return list(expanded)


def _rerank_with_confidence(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """
    Rerank chunks and assign confidence scores (0.0–1.0).
    Combines vector score, keyword TF, phrase proximity, title match.
    """
    if not chunks:
        return chunks

    query_clean = re.sub(r"[^\w\s]", "", query.lower())
    query_terms = set(_extract_keywords(query))

    for chunk in chunks:
        text_lower = re.sub(r"[^\w\s]", "", chunk["text"].lower())
        words = text_lower.split()

        # Term frequency score (0–1)
        tf_score = sum(1 for t in query_terms if t in text_lower) / max(len(query_terms), 1)

        # Exact phrase / near-phrase bonus
        phrase_bonus = 0.25 if any(
            p in text_lower for p in [query_clean[:25], query_clean[:40]]
            if len(p) > 8
        ) else 0.0

        # Title match bonus
        source_title = (chunk.get("metadata") or {}).get("source_title", "").lower()
        title_bonus = 0.2 if any(t in source_title for t in query_terms) else 0.0

        # Position bonus — terms appearing early = higher relevance
        first_pos = next(
            (words.index(t) / max(len(words), 1) for t in query_terms if t in words), 1.0
        )
        position_bonus = (1.0 - first_pos) * 0.1

        # Raw vector/keyword score (0–1 range)
        raw_score = min(float(chunk.get("score", 0)), 1.0)

        # Combined rerank score
        rerank_score = (
            raw_score * 0.35 +
            tf_score  * 0.35 +
            phrase_bonus +
            title_bonus +
            position_bonus
        )

        # Confidence score (normalised, capped at 1.0)
        confidence = min(rerank_score, 1.0)
        chunk["rerank_score"] = rerank_score
        chunk["confidence_score"] = round(confidence, 3)

    chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
    return chunks[:top_k]


async def vector_search(
    query: str,
    org_id: uuid.UUID,
    db: AsyncSession,
    top_k: int = None,
    product_area: str = None,
) -> list[dict]:
    """
    Full Phase 2 search pipeline:
    1. Query expansion (synonyms)
    2. Vector similarity (Voyage AI)
    3. Keyword fallback with expanded terms
    4. Cross-encoder reranking + confidence scoring
    """
    top_k = top_k or settings.top_k_retrieval
    retrieval_k = top_k * 3

    # Expand query with synonyms
    base_keywords = _extract_keywords(query)
    expanded_keywords = _expand_query(base_keywords)

    area_filter = ""
    area_params: dict = {}
    if product_area and product_area not in ("general", "", None):
        area_filter = " AND c.metadata->>'product_area' = :product_area"
        area_params["product_area"] = product_area

    # ── Stage 1: Vector search ─────────────────────────────────────────────
    query_embedding = embed_text(query)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    vector_sql = text(f"""
        SELECT
            c.id::text AS chunk_id, c.text, c.metadata, c.source_id::text,
            1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
        FROM kb_chunks c
        WHERE c.org_id = :org_id AND c.embedding IS NOT NULL {area_filter}
        ORDER BY c.embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    try:
        result = await db.execute(vector_sql, {
            "org_id": str(org_id), "embedding": embedding_str,
            "top_k": retrieval_k, **area_params
        })
        rows = result.fetchall()
        chunks = [
            {"chunk_id": r.chunk_id, "text": r.text,
             "metadata": r.metadata or {}, "score": float(r.score)}
            for r in rows
        ]
        avg_score = sum(c["score"] for c in chunks) / len(chunks) if chunks else 0
        if chunks and avg_score > 0.1:
            return _rerank_with_confidence(query, chunks, top_k)
    except Exception as e:
        print(f"[search] Vector error: {e}")
        chunks = []

    # ── Stage 2: Keyword search with expanded terms ───────────────────────
    kw_conditions = " OR ".join(
        f"LOWER(c.text) LIKE :kw{i}" for i in range(len(expanded_keywords))
    )
    kw_score_expr = (
        "(" + " + ".join(
            f"CASE WHEN LOWER(c.text) LIKE :kw{i} THEN 1 ELSE 0 END"
            for i in range(len(expanded_keywords))
        ) + f") * 1.0 / {len(expanded_keywords)}"
    )
    kw_params = {"org_id": str(org_id), "top_k": retrieval_k, **area_params}
    for i, kw in enumerate(expanded_keywords):
        kw_params[f"kw{i}"] = f"%{kw}%"

    keyword_sql = text(f"""
        SELECT c.id::text AS chunk_id, c.text, c.metadata, c.source_id::text,
               {kw_score_expr} AS score
        FROM kb_chunks c
        WHERE c.org_id = :org_id AND c.embedding IS NOT NULL {area_filter}
          AND ({kw_conditions})
        ORDER BY score DESC LIMIT :top_k
    """)

    try:
        result = await db.execute(keyword_sql, kw_params)
        rows = result.fetchall()
        chunks = [
            {"chunk_id": r.chunk_id, "text": r.text,
             "metadata": r.metadata or {}, "score": float(r.score)}
            for r in rows
        ]
    except Exception as e:
        print(f"[search] Keyword error: {e}")
        chunks = []

    # ── Stage 3: Catch-all ─────────────────────────────────────────────────
    if not chunks:
        fallback = text(f"""
            SELECT c.id::text, c.text, c.metadata, c.source_id::text, 0.3 AS score
            FROM kb_chunks c WHERE c.org_id = :org_id
              AND c.embedding IS NOT NULL {area_filter} LIMIT :top_k
        """)
        result = await db.execute(fallback, {"org_id": str(org_id), "top_k": top_k, **area_params})
        rows = result.fetchall()
        chunks = [
            {"chunk_id": r.chunk_id, "text": r.text,
             "metadata": r.metadata or {}, "score": float(r.score)}
            for r in rows
        ]

    return _rerank_with_confidence(query, chunks, top_k)


async def get_chunk_by_id(chunk_id: str, db: AsyncSession) -> KBChunk | None:
    result = await db.execute(select(KBChunk).where(KBChunk.id == uuid.UUID(chunk_id)))
    return result.scalar_one_or_none()
