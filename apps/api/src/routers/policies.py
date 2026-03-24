import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Organization, PolicyRule
from src.deps import get_org
from src.schemas.policy import PolicyRuleCreate, PolicyRuleOut, PolicyRuleUpdate
import yaml

router = APIRouter(prefix="/policies", tags=["Policies"])


def _validate_yaml(yaml_str: str):
    try:
        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict) or "rules" not in data:
            raise ValueError("YAML must contain a top-level 'rules' list")
        return data
    except yaml.YAMLError as e:
        raise HTTPException(400, f"Invalid YAML: {e}")


@router.post("/", response_model=PolicyRuleOut)
async def create_policy(
    payload: PolicyRuleCreate,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    _validate_yaml(payload.rule_yaml)
    rule = PolicyRule(
        org_id=org.id,
        name=payload.name,
        description=payload.description,
        rule_yaml=payload.rule_yaml,
        is_enabled=payload.is_enabled,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/", response_model=list[PolicyRuleOut])
async def list_policies(
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PolicyRule).where(PolicyRule.org_id == org.id).order_by(PolicyRule.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{rule_id}", response_model=PolicyRuleOut)
async def get_policy(
    rule_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PolicyRule).where(PolicyRule.id == uuid.UUID(rule_id), PolicyRule.org_id == org.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Policy not found")
    return rule


@router.patch("/{rule_id}", response_model=PolicyRuleOut)
async def update_policy(
    rule_id: str,
    payload: PolicyRuleUpdate,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PolicyRule).where(PolicyRule.id == uuid.UUID(rule_id), PolicyRule.org_id == org.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Policy not found")

    if payload.rule_yaml:
        _validate_yaml(payload.rule_yaml)
        rule.rule_yaml = payload.rule_yaml
    if payload.name is not None:
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.is_enabled is not None:
        rule.is_enabled = payload.is_enabled

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_policy(
    rule_id: str,
    org: Organization = Depends(get_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PolicyRule).where(PolicyRule.id == uuid.UUID(rule_id), PolicyRule.org_id == org.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Policy not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": rule_id}
