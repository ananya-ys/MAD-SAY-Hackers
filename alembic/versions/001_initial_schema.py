"""initial_schema

Revision ID: 001_initial
Revises:
Create Date: 2026-04-09

GAP 2 FIX: First migration. Replaces create_all() which cannot handle
incremental schema changes in production. All future schema changes must
be a new Alembic revision — never modify this file.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), primary_key=True),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="ENGINEER"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("refresh_jti", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # ── repair_sessions ────────────────────────────────────────────────────
    op.create_table(
        "repair_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), primary_key=True),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("source_layer", sa.String(32), nullable=True),
        sa.Column("rule_id", sa.String(64), nullable=True),
        sa.Column("stack_trace", sa.Text, nullable=False),
        sa.Column("repo_path", sa.String(1024), nullable=False),
        sa.Column("error_signature", sa.JSON, nullable=True),
        sa.Column("validation_level", sa.String(16), nullable=False, server_default="BASIC"),
        sa.Column("max_iterations", sa.SmallInteger, nullable=False, server_default="5"),
        sa.Column("total_iterations", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("final_patch", sa.Text, nullable=True),
        sa.Column("llm_cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("total_elapsed_ms", sa.Integer, nullable=True),
        sa.Column("explainability", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_repair_sessions_org_id", "repair_sessions", ["org_id"])
    op.create_index("ix_repair_sessions_user_id", "repair_sessions", ["user_id"])

    # ── memory_entries ─────────────────────────────────────────────────────
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("structural_hash", sa.String(16), nullable=False, unique=True),
        sa.Column("signature_json", sa.JSON, nullable=False),
        sa.Column("error_type", sa.String(128), nullable=False),
        sa.Column("cached_fix", sa.Text, nullable=False),
        sa.Column("fix_source", sa.String(32), nullable=False, server_default="llm"),
        sa.Column("validation_level", sa.String(16), nullable=False),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.70"),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memory_entries_structural_hash", "memory_entries", ["structural_hash"], unique=True)
    op.create_index("ix_memory_entries_error_type", "memory_entries", ["error_type"])

    # ── rules ──────────────────────────────────────────────────────────────
    op.create_table(
        "rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), primary_key=True),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("condition_yaml", sa.Text, nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("action_params", sa.JSON, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("hit_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("source", sa.String(32), nullable=False, server_default="builtin"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rules_org_id", "rules", ["org_id"])

    # ── audit_log ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), primary_key=True),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=True),
        sa.Column("api_key_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.dialects.postgresql.UUID(as_uuid=True) if _is_pg() else sa.String(36), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_log_org_id", "audit_log", ["org_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("rules")
    op.drop_table("memory_entries")
    op.drop_table("repair_sessions")
    op.drop_table("users")


def _is_pg() -> bool:
    """Detect PostgreSQL vs SQLite at migration time."""
    try:
        bind = op.get_bind()
        return bind.dialect.name == "postgresql"
    except Exception:
        return False
