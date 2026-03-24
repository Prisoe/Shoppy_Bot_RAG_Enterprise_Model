"""Shared types used across API, worker, and console."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChunkResult:
    chunk_id: str
    text: str
    metadata: dict
    score: float


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_id: str
