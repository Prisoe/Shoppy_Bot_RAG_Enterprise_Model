"""API Key management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, APIKey
from src.config import settings
import hashlib, secrets, uuid

router = APIRouter()


@router.post("/orgs")
async def create_org(name: str, slug: str, db: AsyncSession = Depends(get_db)):
    """Create a new organization. In production, add admin auth here."""
    org = Organization(name=name, slug=slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return {"org_id": org.id, "name": org.name}


@router.post("/api-keys")
async def create_api_key(org_id: str, label: str = "default", db: AsyncSession = Depends(get_db)):
    """Generate a new API key for an org."""
    raw_key = f"sk-ao-{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(f"{raw_key}{settings.API_KEY_SALT}".encode()).hexdigest()
    api_key = APIKey(org_id=org_id, key_hash=key_hash, label=label)
    db.add(api_key)
    await db.commit()
    return {"api_key": raw_key, "label": label, "note": "Store this key securely — it won't be shown again."}
