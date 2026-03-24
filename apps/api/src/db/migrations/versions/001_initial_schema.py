"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_key", sa.String(255), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
    )

    op.create_table(
        "kb_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("metadata", postgresql.JSONB(), default=dict),
        sa.Column("product_area", sa.String(128), nullable=True),
        sa.Column("language", sa.String(16), default="en"),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_table(
        "kb_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), default=dict),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kb_chunks_org_id", "kb_chunks", ["org_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("agent_name", sa.String(128), default="support_ops"),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("output_payload", postgresql.JSONB(), nullable=True),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(), default=list),
        sa.Column("tool_calls", postgresql.JSONB(), default=list),
        sa.Column("model_id", sa.String(256), nullable=True),
        sa.Column("input_tokens", sa.Integer(), default=0),
        sa.Column("output_tokens", sa.Integer(), default=0),
        sa.Column("cost_usd", sa.Float(), default=0.0),
        sa.Column("latency_ms", sa.Integer(), default=0),
        sa.Column("status", sa.String(32), default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_runs_org_id", "agent_runs", ["org_id"])

    op.create_table(
        "policy_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_yaml", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "policy_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_rules.id"), nullable=True),
        sa.Column("rule_name", sa.String(256), nullable=True),
        sa.Column("action_taken", sa.String(32), nullable=False),
        sa.Column("detail", postgresql.JSONB(), default=dict),
        sa.Column("phase", sa.String(16), default="post"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), unique=True, nullable=False),
        sa.Column("reviewer_id", sa.String(256), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "eval_suites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("dataset_path", sa.String(512), nullable=False),
        sa.Column("metrics_config", postgresql.JSONB(), default=dict),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eval_suites.id"), nullable=False),
        sa.Column("kb_version", sa.String(64), nullable=True),
        sa.Column("model_id", sa.String(256), nullable=True),
        sa.Column("scores", postgresql.JSONB(), default=dict),
        sa.Column("failures", postgresql.JSONB(), default=list),
        sa.Column("total_cases", sa.Integer(), default=0),
        sa.Column("passed", sa.Integer(), default=0),
        sa.Column("failed", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "geo_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answerability_score", sa.Float(), nullable=True),
        sa.Column("contradictions", postgresql.JSONB(), default=list),
        sa.Column("missing_questions", postgresql.JSONB(), default=list),
        sa.Column("outdated_pages", postgresql.JSONB(), default=list),
        sa.Column("recommendations", postgresql.JSONB(), default=list),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("geo_reports")
    op.drop_table("eval_runs")
    op.drop_table("eval_suites")
    op.drop_table("approvals")
    op.drop_table("policy_events")
    op.drop_table("policy_rules")
    op.drop_table("agent_runs")
    op.drop_table("kb_chunks")
    op.drop_table("kb_sources")
    op.drop_table("organizations")
