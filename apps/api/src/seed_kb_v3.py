"""
seed_kb_v3.py — Force re-embed ALL existing KB chunks with Voyage AI.
Run after adding VOYAGE_API_KEY to .env to get real semantic search.

Usage: docker compose exec api python3 /app/src/seed_kb_v3.py
"""
import sys, asyncio, time
sys.path.insert(0, '/app')

from src.db.session import AsyncSessionLocal
from src.db.models import KBChunk, KBSource, KBSourceStatus
from src.services.kb.embedder import embed_text, embed_batch
from src.config import get_settings
from sqlalchemy import select

settings = get_settings()

async def reembed_all():
    key = getattr(settings, 'voyage_api_key', '') or ''
    if not key or key.lower() == 'none':
        print("ERROR: VOYAGE_API_KEY not set. Add it to .env first.")
        print("Get a free key at: dash.voyageai.com")
        return

    print(f"Voyage AI key detected: {key[:12]}...")
    print("Re-embedding all KB chunks with real semantic vectors...\n")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KBChunk))
        chunks = result.scalars().all()
        total = len(chunks)
        print(f"Found {total} chunks to re-embed\n")

        batch_size = 20  # Voyage free tier: 3 RPM, process in small batches with delay
        success = 0
        errors = 0

        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.text for c in batch]

            try:
                embeddings = embed_batch(texts)
                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = embedding
                    success += 1

                await db.commit()

                pct = min(100, round((i + len(batch)) / total * 100))
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"  [{bar}] {pct}% — {i + len(batch)}/{total} chunks embedded", end="\r")

                # Rate limit: 3 requests/min on free tier = 1 request every 20 seconds
                if i + batch_size < total:
                    time.sleep(21)

            except Exception as e:
                print(f"\n  ERROR batch {i//batch_size}: {e}")
                errors += 1
                await db.rollback()
                time.sleep(30)  # back off on error
                continue

        print(f"\n\n{'='*50}")
        print(f"Re-embedding complete!")
        print(f"  ✓ Success: {success} chunks")
        print(f"  ✗ Errors:  {errors} batches")
        print(f"\nYour KB now has real semantic search powered by Voyage AI.")
        print(f"Run a GEO scan to see the updated answerability score.")
        print(f"{'='*50}")

asyncio.run(reembed_all())
