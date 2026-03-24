"""Tests for the document chunker."""
import pytest
from src.services.kb.chunker import Chunker


def test_basic_chunking():
    chunker = Chunker(chunk_size=200, overlap=20)
    text = "\n\n".join([f"Paragraph {i}. " + ("word " * 30) for i in range(10)])
    chunks = chunker.chunk_text(text)
    assert len(chunks) > 1
    for c in chunks:
        assert "text" in c
        assert "chunk_index" in c
        assert len(c["text"]) > 0


def test_markdown_chunking():
    chunker = Chunker(chunk_size=300, overlap=30)
    md = """# Section One
    
This is the first section with some content about checkout settings.

## Subsection

More content here about payments.

# Section Two

Completely different topic about inventory management.
"""
    chunks = chunker.chunk_markdown(md)
    assert len(chunks) >= 2


def test_metadata_preserved():
    chunker = Chunker()
    chunks = chunker.chunk_text("Some text here.", metadata={"source_id": "test-123"})
    assert all(c["metadata"]["source_id"] == "test-123" for c in chunks)


def test_empty_text():
    chunker = Chunker()
    chunks = chunker.chunk_text("")
    assert chunks == []
