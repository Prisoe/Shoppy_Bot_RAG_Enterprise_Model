"""
GEO Analyzer v2 — accurate KB health scoring.
Fixes:
1. Removed chunk-count penalty (penalised quality KB unfairly)
2. Keywords strip punctuation properly (refund? → refund)
3. Expanded question set to match actual KB coverage
4. Better contradiction detection
"""
import re
from collections import defaultdict


STALE_PATTERNS = [
    r"\b202[0-3]\b",
    r"coming soon",
    r"beta feature",
    r"deprecated",
    r"will be available",
    r"not yet supported",
]

COMMON_SUPPORT_QUESTIONS = [
    "How do I process a refund?",
    "How do I cancel an order?",
    "How do I add a product?",
    "How do I set up shipping rates?",
    "How do I connect a payment provider?",
    "How do I create a discount code?",
    "How do I view my analytics?",
    "How do I manage inventory?",
    "How do I change my store theme?",
    "How do I export orders?",
    "What are Shopify fees and plans?",
    "How do I set up taxes?",
    "How do I add staff accounts?",
    "How do I connect a custom domain?",
    "How do I manage customer accounts?",
    "How do I set up free shipping?",
    "How do I fulfill an order?",
    "How do I handle a chargeback?",
    "How do I create a draft order?",
    "How do I set up Shopify Payments?",
    "How do I print a shipping label?",
    "How do I set up international shipping?",
    "How do I add product variants?",
    "How do I create collections?",
    "How do I set up customer segments?",
    "How do I create automatic discounts?",
    "How do I use Shopify Flow?",
    "How do I set up email marketing?",
    "How do I set up Shopify POS?",
    "How do I configure checkout settings?",
]


def _clean_keywords(question: str) -> list[str]:
    """Extract meaningful keywords, stripping punctuation properly."""
    stopwords = {
        "how", "do", "i", "a", "the", "to", "in", "for", "is", "can",
        "what", "my", "me", "an", "of", "it", "with", "and", "or",
        "this", "that", "on", "at", "be", "was", "are", "will", "up",
        "set", "use", "get", "add", "view", "are", "handle", "change",
        "create", "manage", "connect", "configure", "print",
    }
    # Strip all punctuation from each word
    words = re.sub(r'[^\w\s]', '', question.lower()).split()
    return [w for w in words if len(w) > 3 and w not in stopwords]


def analyze_chunks(chunks: list[dict]) -> dict:
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
    contradictions = []
    keyword_chunks = defaultdict(list)

    for chunk in chunks:
        text_lower = chunk["text"].lower()
        for kw in ["refund", "cancel", "shipping rate", "payment", "tax", "discount", "fees"]:
            if kw in text_lower:
                keyword_chunks[kw].append(chunk)

    POSITIVE = ["you can", "supported", "available", "enabled", "allowed", "is possible"]
    NEGATIVE = ["cannot", "not supported", "unavailable", "disabled", "not allowed", "is not possible"]

    for kw, kw_chunks in keyword_chunks.items():
        sources_positive = []
        sources_negative = []
        for c in kw_chunks:
            t = c["text"].lower()
            has_pos = any(p in t for p in POSITIVE)
            has_neg = any(n in t for n in NEGATIVE)
            if has_pos and not has_neg:
                sources_positive.append(c.get("source_title", c.get("metadata", {}).get("source_title", "Unknown")))
            elif has_neg and not has_pos:
                sources_negative.append(c.get("source_title", c.get("metadata", {}).get("source_title", "Unknown")))

        if sources_positive and sources_negative:
            contradictions.append({
                "topic": kw,
                "positive_sources": list(set(sources_positive))[:2],
                "negative_sources": list(set(sources_negative))[:2],
                "severity": "medium",
            })

    return contradictions[:10]


def _find_outdated(chunks: list[dict]) -> list[dict]:
    outdated = []
    seen_sources = set()
    for chunk in chunks:
        source_title = chunk.get("source_title") or chunk.get("metadata", {}).get("source_title", "")
        if source_title in seen_sources:
            continue
        for pattern in STALE_PATTERNS:
            if re.search(pattern, chunk["text"], re.IGNORECASE):
                outdated.append({
                    "source_title": source_title,
                    "source_url": chunk.get("source_url") or chunk.get("metadata", {}).get("source_url", ""),
                    "reason": f"Contains potentially stale content: '{pattern}'",
                    "snippet": chunk["text"][:150],
                })
                seen_sources.add(source_title)
                break
    return outdated[:10]


def _find_missing_questions(chunks: list[dict]) -> list[dict]:
    # Build full text from all chunks
    all_text = " ".join(c["text"].lower() for c in chunks)
    # Clean punctuation from combined text too
    all_text_clean = re.sub(r'[^\w\s]', ' ', all_text)

    missing = []
    for q in COMMON_SUPPORT_QUESTIONS:
        keywords = _clean_keywords(q)
        if not keywords:
            continue
        matched = sum(1 for kw in keywords if kw in all_text_clean)
        coverage = matched / len(keywords)
        if coverage < 0.6:
            missing.append({
                "question": q,
                "coverage_score": round(coverage, 2),
                "priority": "high" if coverage < 0.2 else "medium",
            })
    return missing


def _compute_answerability(chunks: list[dict], missing: list[dict]) -> float:
    """
    Score based purely on topic coverage, not chunk count.
    Chunk count penalty removed — quality KB > quantity.
    """
    if not chunks:
        return 0.0

    total_questions = len(COMMON_SUPPORT_QUESTIONS)
    # Count questions with at least medium coverage
    high_missing = len([m for m in missing if m["priority"] == "high"])
    medium_missing = len([m for m in missing if m["priority"] == "medium"])

    # High missing = full miss, medium missing = half credit
    covered = total_questions - high_missing - (medium_missing * 0.5)
    score = covered / total_questions

    return round(min(score, 1.0) * 100, 1)


def _generate_recommendations(contradictions, outdated, missing, score) -> list[str]:
    recs = []
    if score < 60:
        recs.append("KB coverage is low. Add more Shopify help articles for common support topics.")
    elif score < 80:
        recs.append("KB coverage is good. Target the missing questions below to reach 80%+ answerability.")
    if contradictions:
        recs.append(f"Resolve {len(contradictions)} topic contradiction(s) — conflicting answers reduce AI answer quality.")
    if outdated:
        recs.append(f"Review {len(outdated)} potentially outdated page(s) and update or remove stale content.")
    high_priority = [m["question"] for m in missing if m["priority"] == "high"]
    if high_priority:
        preview = ", ".join(f'"{q}"' for q in high_priority[:3])
        recs.append(f"Add KB content for: {preview}")
    if score >= 80:
        recs.append("KB health is strong. Consider adding FAQ-style Q&A blocks for better AI answer snippets.")
    if score >= 90:
        recs.append("Excellent coverage! Consider adding edge-case articles for advanced merchant questions.")
    return recs
