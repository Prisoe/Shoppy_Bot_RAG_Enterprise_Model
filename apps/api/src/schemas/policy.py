from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class PolicyRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_yaml: str
    is_enabled: Optional[bool] = True


class PolicyRuleOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    rule_yaml: str
    is_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PolicyRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_yaml: Optional[str] = None
    is_enabled: Optional[bool] = None
