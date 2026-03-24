from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class EvalSuiteCreate(BaseModel):
    name: str
    dataset_path: str
    metrics_config: Optional[dict] = {}


class EvalSuiteOut(BaseModel):
    id: UUID
    name: str
    dataset_path: str
    metrics_config: dict
    created_at: datetime

    class Config:
        from_attributes = True


class EvalRunOut(BaseModel):
    id: UUID
    suite_id: UUID
    model_id: Optional[str]
    scores: dict
    failures: list
    total_cases: int
    passed: int
    failed: int
    created_at: datetime

    class Config:
        from_attributes = True
