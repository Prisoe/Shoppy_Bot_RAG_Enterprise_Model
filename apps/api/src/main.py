"""
Enterprise RAG Assistant — FastAPI entrypoint.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_engine, AsyncSessionLocal
from src.db.models import Base, Organization
from src.config import get_settings
from src.routers import agents, kb, policies, approvals, evals, geo

settings = get_settings()


async def _ensure_default_org():
    """Create a default org for dev if none exists."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func
        count = await db.scalar(select(func.count(Organization.id)))
        if count == 0:
            org = Organization(
                name="Default Organization",
                api_key=settings.default_org_api_key,
            )
            db.add(org)
            await db.commit()
            print(f"[startup] Created default org with API key: {settings.default_org_api_key}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    async with async_engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_default_org()
    print("[startup] Database ready.")
    yield
    # ── Shutdown ─────────────────────────────────────────────
    await async_engine.dispose()


app = FastAPI(
    title="Enterprise RAG Assistant",
    description="Production-grade RAG system with guardrails, evals, and GEO — powered by AWS Bedrock",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
app.include_router(agents.router)
app.include_router(kb.router)
app.include_router(policies.router)
app.include_router(approvals.router)
app.include_router(evals.router)
app.include_router(geo.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0", "model": settings.bedrock_llm_model_id}


@app.get("/", tags=["Health"])
async def root():
    return {"message": "Enterprise RAG Assistant API", "docs": "/docs"}
