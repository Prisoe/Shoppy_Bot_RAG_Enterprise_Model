"""
GEO report generator — produces structured report dict.
"""
from datetime import datetime
from src.services.geo.analyzer import analyze_kb
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_geo_report(db: AsyncSession, org_id: str) -> dict:
    analysis = await analyze_kb(db, org_id)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "org_id": org_id,
        "summary": {
            "total_chunks": analysis.get("total_chunks", 0),
            "avg_answerability_score": analysis.get("avg_answerability_score", 0),
            "contradiction_count": len(analysis.get("contradictions", [])),
        },
        "contradictions": analysis.get("contradictions", []),
        "recommendations": analysis.get("recommendations", []),
    }
