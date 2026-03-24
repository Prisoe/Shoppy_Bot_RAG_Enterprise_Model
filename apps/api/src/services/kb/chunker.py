"""
Splits raw document text into overlapping chunks with metadata.
"""
import re
from src.config import get_settings

settings = get_settings()


def chunk_text(
    text: str,
    source_title: str,
    source_url: str = "",
    product_area: str = "",
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list[dict]:
    """
    Returns list of dicts:
      { text, chunk_index, metadata }
    """
    chunk_size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    # Split on paragraph boundaries first, then by token estimate
    paragraphs = re.split(r"\n\n+", text)

    chunks = []
    current = ""
    idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Rough token estimate: ~0.75 words per token, 1 word ≈ 5 chars
        estimated_tokens = len(current) // 4
        para_tokens = len(para) // 4

        if estimated_tokens + para_tokens > chunk_size and current:
            chunks.append(_make_chunk(current.strip(), idx, source_title, source_url, product_area))
            idx += 1
            # Overlap: carry last N chars of current into next chunk
            overlap_text = current[-overlap * 4:] if len(current) > overlap * 4 else current
            current = overlap_text + "\n\n" + para
        else:
            current = (current + "\n\n" + para).strip()

    if current.strip():
        chunks.append(_make_chunk(current.strip(), idx, source_title, source_url, product_area))

    return chunks


def _make_chunk(text: str, idx: int, title: str, url: str, product_area: str) -> dict:
    return {
        "text": text,
        "chunk_index": idx,
        "token_count": len(text) // 4,
        "metadata": {
            "source_title": title,
            "source_url": url,
            "product_area": product_area,
            "chunk_index": idx,
        },
    }
