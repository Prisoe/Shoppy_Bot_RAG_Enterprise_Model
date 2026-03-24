"""
Embeddings via Anthropic's voyage-3 model through the voyageai SDK,
OR simple fallback using the Anthropic API itself.

We'll use the `voyageai` package for embeddings (1536-dim, excellent quality).
Alternatively uses a hash-based dummy for local dev if no key is set.

Install: voyageai is added to requirements.txt
Get a Voyage API key free at: dash.voyageai.com (sign in with Google/GitHub)
OR set VOYAGE_API_KEY=none to use the local fallback (no real embeddings,
search won't work but everything else will).
"""
import os
import hashlib
import math
from src.config import get_settings

settings = get_settings()


def embed_text(text: str) -> list[float]:
    """Embed a single text. Uses Voyage AI if key is set, else dummy vectors."""
    voyage_key = getattr(settings, "voyage_api_key", "") or ""

    if voyage_key and voyage_key.lower() != "none":
        try:
            import voyageai
            client = voyageai.Client(api_key=voyage_key)
            result = client.embed([text[:8000]], model="voyage-3")
            return result.embeddings[0]
        except Exception as e:
            print(f"[embedder] Voyage AI error: {e}, falling back to dummy")

    return _dummy_embed(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    voyage_key = getattr(settings, "voyage_api_key", "") or ""

    if voyage_key and voyage_key.lower() != "none":
        try:
            import voyageai
            client = voyageai.Client(api_key=voyage_key)
            # Voyage allows up to 128 texts per batch
            all_embeddings = []
            batch_size = 64
            for i in range(0, len(texts), batch_size):
                batch = [t[:8000] for t in texts[i:i+batch_size]]
                result = client.embed(batch, model="voyage-3")
                all_embeddings.extend(result.embeddings)
            return all_embeddings
        except Exception as e:
            print(f"[embedder] Voyage AI batch error: {e}, falling back to dummy")

    return [_dummy_embed(t) for t in texts]


def _dummy_embed(text: str) -> list[float]:
    """
    Deterministic pseudo-embedding for dev/testing when no embedding API is set.
    Uses SHA-256 to seed a 1024-dim unit vector.
    Search will work structurally but results won't be semantically meaningful.
    """
    h = hashlib.sha256(text.encode()).digest()
    vec = []
    for i in range(0, 1024):
        byte_idx = i % len(h)
        val = (h[byte_idx] - 128) / 128.0
        vec.append(val)
    # Normalize to unit vector
    magnitude = math.sqrt(sum(v * v for v in vec))
    if magnitude > 0:
        vec = [v / magnitude for v in vec]
    return vec