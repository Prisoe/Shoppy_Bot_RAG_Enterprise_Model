import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Float, Integer,
    DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
import enum


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    success = "success"
    blocked = "blocked"
    needs_approval = "needs_approval"
    approved = "approved"
    rejected = "rejected"
    error = "error"


class PolicyAction(str, enum.Enum):
    allow = "allow"
    block = "block"
    require_approval = "require_approval"
    redact = "redact"
    require_citations = "require_citations"


class KBSourceType(str, enum.Enum):
    url = "url"
    file = "file"
    shopify_help = "shopify_help"


class KBSourceStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


# ─────────────────────────────────────────────
# Organizations & Auth
# ─────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    kb_sources = relationship("KBSource", back_populates="org")
    agent_runs = relationship("AgentRun", back_populates="org")
    policy_rules = relationship("PolicyRule", back_populates="org")
    eval_suites = relationship("EvalSuite", back_populates="org")


# ─────────────────────────────────────────────
# Knowledge Base
# ─────────────────────────────────────────────

class KBSource(Base):
    __tablename__ = "kb_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    title = Column(String(512), nullable=False)
    source_type = Column(SAEnum(KBSourceType), nullable=False)
    url = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)
    status = Column(SAEnum(KBSourceStatus), default=KBSourceStatus.pending)
    metadata_ = Column("metadata", JSONB, default=dict)
    product_area = Column(String(128), nullable=True)
    language = Column(String(16), default="en")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    org = relationship("Organization", back_populates="kb_sources")
    chunks = relationship("KBChunk", back_populates="source", cascade="all, delete-orphan")


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("kb_sources.id", ondelete="CASCADE"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("KBSource", back_populates="chunks")


# ─────────────────────────────────────────────
# Agent Runs
# ─────────────────────────────────────────────

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    agent_name = Column(String(128), default="support_ops")
    input_payload = Column(JSONB, nullable=False)
    output_payload = Column(JSONB, nullable=True)
    retrieved_chunk_ids = Column(JSONB, default=list)
    tool_calls = Column(JSONB, default=list)
    model_id = Column(String(256), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    status = Column(SAEnum(RunStatus), default=RunStatus.success)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Organization", back_populates="agent_runs")
    policy_events = relationship("PolicyEvent", back_populates="run")
    approval = relationship("Approval", back_populates="run", uselist=False)


# ─────────────────────────────────────────────
# Policy
# ─────────────────────────────────────────────

class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    rule_yaml = Column(Text, nullable=False)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Organization", back_populates="policy_rules")
    events = relationship("PolicyEvent", back_populates="rule")


class PolicyEvent(Base):
    __tablename__ = "policy_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("policy_rules.id"), nullable=True)
    rule_name = Column(String(256), nullable=True)
    action_taken = Column(SAEnum(PolicyAction), nullable=False)
    detail = Column(JSONB, default=dict)
    phase = Column(String(16), default="post")  # pre or post
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AgentRun", back_populates="policy_events")
    rule = relationship("PolicyRule", back_populates="events")


# ─────────────────────────────────────────────
# Approvals
# ─────────────────────────────────────────────

class Approval(Base):
    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), unique=True, nullable=False)
    reviewer_id = Column(String(256), nullable=True)
    decision = Column(String(16), nullable=True)  # approved / rejected
    notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AgentRun", back_populates="approval")


# ─────────────────────────────────────────────
# Evals
# ─────────────────────────────────────────────

class EvalSuite(Base):
    __tablename__ = "eval_suites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(256), nullable=False)
    dataset_path = Column(String(512), nullable=False)
    metrics_config = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Organization", back_populates="eval_suites")
    runs = relationship("EvalRun", back_populates="suite")


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id = Column(UUID(as_uuid=True), ForeignKey("eval_suites.id"), nullable=False)
    kb_version = Column(String(64), nullable=True)
    model_id = Column(String(256), nullable=True)
    scores = Column(JSONB, default=dict)
    failures = Column(JSONB, default=list)
    total_cases = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    suite = relationship("EvalSuite", back_populates="runs")


# ─────────────────────────────────────────────
# GEO Reports
# ─────────────────────────────────────────────

class GEOReport(Base):
    __tablename__ = "geo_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    answerability_score = Column(Float, nullable=True)
    contradictions = Column(JSONB, default=list)
    missing_questions = Column(JSONB, default=list)
    outdated_pages = Column(JSONB, default=list)
    recommendations = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
