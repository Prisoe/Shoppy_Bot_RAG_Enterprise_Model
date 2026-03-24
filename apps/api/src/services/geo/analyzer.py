"""
GEO Analyzer — scans KB chunks to detect:
  1. Contradictions (same question, different answers)
  2. Missing common questions
  3. Outdated pages (stale language)
  4. Answerability score
"""
import re
from collections import defaultdict
from sqlalchemy.orm import Session
from src.db.models import KBChunk, KBSource
from sqlalchemy import select
import uuid


STALE_PATTERNS = [
    r"\b202[0-3]\b",  # years 2020-2023
    r"coming soon",
    r"beta feature",
    r"deprecated",
    r"will be available",
    r"not yet supported",
]

COMMON_SUPPORT_QUESTIONS = [
    "How do I process a refund?",
    "How do I cancel a subscription?",
    "How do I add a product?",
    "How do I set up shipping?",
    "How do I connect a payment provider?",
    "How do I add a discount code?",
    "How do I view my analytics?",
    "How do I manage inventory?",
    "How do I change my store theme?",
    "How do I export orders?",
    "What are Shopify fees?",
    "How do I set up taxes?",
    "How do I add staff accounts?",
    "How do I connect a domain?",
    "How do I manage customer accounts?",
]


def analyze_chunks(chunks: list[dict]) -> dict:
    """
    chunks: list of { id, text, metadata, source_title }
    Returns GEO analysis result.
    """
    contradictions = _find_contradictions(chunks)
    outdated = _find_outdated(chunks)
    missing = _find_missing_questions(chunks)
    score = _compute_answerability(chunks, missing)
    recommendations = _generate_recommendations(contradictions, outdated, missing, score)

    return {
        "answerability_score": score,
        "contradictions": contradictions,
        "missing_questions": missing,
        "outdated_pages": outdated,
        "recommendations": recommendations,
    }


def _find_contradictions(chunks: list[dict]) -> list[dict]:
    """
    Naive contradiction detection: look for chunks from different sources
    that discuss the same topic keyword but contain opposing signals.
    """
    contradictions = []
    keyword_chunks = defaultdict(list)

    # Group by rough topic keyword
    for chunk in chunks:
        text_lower = chunk["text"].lower()
        for kw in ["refund", "cancel", "shipping rate", "payment", "tax", "discount"]:
            if kw in text_lower:
                keyword_chunks[kw].append(chunk)

    POSITIVE = ["yes", "you can", "supported", "available", "enabled", "allowed"]
    NEGATIVE = ["no", "cannot", "not supported", "unavailable", "disabled", "not allowed"]

    for kw, kw_chunks in keyword_chunks.items():
        sources_positive = []
        sources_negative = []
        for c in kw_chunks:
            t = c["text"].lower()
            has_pos = any(p in t for p in POSITIVE)
            has_neg = any(n in t for n in NEGATIVE)
            if has_pos and not has_neg:
                sources_positive.append(c["metadata"].get("source_title", "Unknown"))
            elif has_neg and not has_pos:
                sources_negative.append(c["metadata"].get("source_title", "Unknown"))

        if sources_positive and sources_negative:
            contradictions.append({
                "topic": kw,
                "positive_sources": list(set(sources_positive))[:3],
                "negative_sources": list(set(sources_negative))[:3],
                "severity": "high" if len(sources_positive) + len(sources_negative) > 4 else "medium",
            })

    return contradictions[:20]


def _find_outdated(chunks: list[dict]) -> list[dict]:
    outdated = []
    seen_sources = set()
    for chunk in chunks:
        source_title = chunk["metadata"].get("source_title", "")
        if source_title in seen_sources:
            continue
        for pattern in STALE_PATTERNS:
            if re.search(pattern, chunk["text"], re.IGNORECASE):
                outdated.append({
                    "source_title": source_title,
                    "source_url": chunk["metadata"].get("source_url", ""),
                    "reason": f"Contains potentially stale content matching: '{pattern}'",
                    "snippet": chunk["text"][:200],
                })
                seen_sources.add(source_title)
                break
    return outdated[:20]


def _find_missing_questions(chunks: list[dict]) -> list[dict]:
    all_text = " ".join(c["text"].lower() for c in chunks)
    missing = []
    for q in COMMON_SUPPORT_QUESTIONS:
        keywords = [w.lower() for w in q.split() if len(w) > 4]
        matched = sum(1 for kw in keywords if kw in all_text)
        coverage = matched / max(len(keywords), 1)
        if coverage < 0.5:
            missing.append({
                "question": q,
                "coverage_score": round(coverage, 2),
                "priority": "high" if coverage < 0.2 else "medium",
            })
    return missing


def _compute_answerability(chunks: list[dict], missing: list[dict]) -> float:
    if not chunks:
        return 0.0
    total_questions = len(COMMON_SUPPORT_QUESTIONS)
    missing_count = len([m for m in missing if m["priority"] == "high"])
    covered = total_questions - missing_count
    base_score = covered / total_questions

    # Penalize if too few chunks
    if len(chunks) < 50:
        base_score *= 0.7
    elif len(chunks) < 200:
        base_score *= 0.85

    return round(min(base_score, 1.0) * 100, 1)


def _generate_recommendations(contradictions, outdated, missing, score) -> list[str]:
    recs = []
    if score < 60:
        recs.append("KB coverage is low. Add more help center articles, especially for common support topics.")
    if contradictions:
        recs.append(f"Resolve {len(contradictions)} topic contradiction(s) — conflicting answers reduce AI answer quality.")
    if outdated:
        recs.append(f"Review {len(outdated)} potentially outdated page(s) and update or remove stale content.")
    high_priority_missing = [m["question"] for m in missing if m["priority"] == "high"]
    if high_priority_missing:
        recs.append(f"Add KB content answering: {', '.join(high_priority_missing[:3])}")
    if score >= 80:
        recs.append("KB health is strong. Consider adding FAQ-style Q&A blocks to improve AI answer snippets.")
    return recs
