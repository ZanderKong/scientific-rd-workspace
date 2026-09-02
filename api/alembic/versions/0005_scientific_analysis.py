"""Add frozen scientific analysis, findings, and review records.

Revision ID: 0005_scientific_analysis
Revises: 0004_literature_evidence
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_scientific_analysis"
down_revision = "0004_literature_evidence"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
uuid_type = sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "scientific_analysis_runs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_key", sa.String(length=32), nullable=False),
        sa.Column("model_profile_key", sa.String(length=120), nullable=False),
        sa.Column("structured_output_mode", sa.String(length=32), nullable=False),
        sa.Column("requested_model", sa.String(length=255), nullable=False),
        sa.Column("resolved_model", sa.String(length=255), nullable=True),
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
        sa.Column("provider_model_version", sa.String(length=255), nullable=True),
        sa.Column("prompt_key", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=64), nullable=False),
        sa.Column("prompt_snapshot_json", json_type, nullable=False),
        sa.Column("output_schema_version", sa.Integer(), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("generation_parameters_json", json_type, nullable=False),
        sa.Column("model_metadata_json", json_type, nullable=False),
        sa.Column("raw_output_text", sa.Text(), nullable=True),
        sa.Column("validated_output_json", json_type, nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("langfuse_trace_id", sa.String(length=255), nullable=True),
        sa.Column("langfuse_sync_status", sa.String(length=32), nullable=False),
        sa.Column("langfuse_error", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "purpose in ('interactive', 'evaluation_replay')",
            name="ck_scientific_analysis_runs_purpose",
        ),
        sa.CheckConstraint(
            "status in ('building_context', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_scientific_analysis_runs_status",
        ),
        sa.CheckConstraint(
            "provider_key in ('litellm', 'fixture')", name="ck_scientific_analysis_runs_provider"
        ),
        sa.CheckConstraint(
            "structured_output_mode in ('native_schema', 'json_object')",
            name="ck_scientific_analysis_runs_output_mode",
        ),
        sa.CheckConstraint("prompt_version > 0", name="ck_scientific_analysis_runs_prompt_version"),
        sa.CheckConstraint(
            "output_schema_version > 0", name="ck_scientific_analysis_runs_schema_version"
        ),
        sa.CheckConstraint(
            "workflow_version > 0", name="ck_scientific_analysis_runs_workflow_version"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scientific_analysis_runs_project_id", "scientific_analysis_runs", ["project_id"]
    )

    op.create_table(
        "analysis_context_snapshots",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("analysis_run_id", uuid_type, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", json_type, nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["scientific_analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id"),
    )
    op.create_index(
        "ix_analysis_context_snapshots_analysis_run_id",
        "analysis_context_snapshots",
        ["analysis_run_id"],
    )

    op.create_table(
        "findings",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("analysis_run_id", uuid_type, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=48), nullable=False),
        sa.Column("confidence_label", sa.String(length=16), nullable=False),
        sa.Column("confidence_rationale", sa.Text(), nullable=False),
        sa.Column("applicability_scope", sa.Text(), nullable=False),
        sa.Column("limitations_json", json_type, nullable=False),
        sa.Column("risks_json", json_type, nullable=False),
        sa.Column("missing_evidence_json", json_type, nullable=False),
        sa.Column("comparison_assertions_json", json_type, nullable=False),
        sa.Column("structured_support_json", json_type, nullable=False),
        sa.Column("causal_target_json", json_type, nullable=True),
        sa.Column("suggested_next_experiment_json", json_type, nullable=True),
        sa.Column("model_proposed_gate_status", sa.String(length=32), nullable=False),
        sa.Column("model_proposed_gate_rationale", sa.Text(), nullable=False),
        sa.Column("evidence_gate_status", sa.String(length=32), nullable=False),
        sa.Column("evidence_gate_rationale_json", json_type, nullable=False),
        sa.Column("gate_policy_version", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["scientific_analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id", "ordinal"),
        sa.CheckConstraint(
            "claim_type in ('scientific_observation', 'hypothesis', 'comparative_finding', 'causal_claim', 'recommendation')",
            name="ck_findings_claim_type",
        ),
        sa.CheckConstraint(
            "confidence_label in ('low', 'medium', 'high')", name="ck_findings_confidence_label"
        ),
        sa.CheckConstraint(
            "model_proposed_gate_status in ('supported', 'partially_supported', 'insufficient_evidence', 'contradicted')",
            name="ck_findings_model_gate_status",
        ),
        sa.CheckConstraint(
            "evidence_gate_status in ('supported', 'partially_supported', 'insufficient_evidence', 'contradicted')",
            name="ck_findings_evidence_gate_status",
        ),
        sa.CheckConstraint(
            "review_status in ('pending_review', 'accepted', 'rejected', 'needs_evidence')",
            name="ck_findings_review_status",
        ),
        sa.CheckConstraint("gate_policy_version > 0", name="ck_findings_gate_policy_version"),
    )
    op.create_index("ix_findings_project_id", "findings", ["project_id"])
    op.create_index("ix_findings_analysis_run_id", "findings", ["analysis_run_id"])

    op.create_table(
        "finding_evidence_links",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("finding_id", uuid_type, nullable=False),
        sa.Column("evidence_record_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_snapshot_json", json_type, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role in ('supporting', 'contradicting', 'contextual')",
            name="ck_finding_evidence_links_role",
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"]),
        sa.ForeignKeyConstraint(["evidence_record_id"], ["evidence_records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", "evidence_record_id"),
    )
    op.create_index(
        "ix_finding_evidence_links_finding_id", "finding_evidence_links", ["finding_id"]
    )
    op.create_index(
        "ix_finding_evidence_links_evidence_record_id",
        "finding_evidence_links",
        ["evidence_record_id"],
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("finding_id", uuid_type, nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reviewer_name", sa.String(length=240), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("supersedes_review_id", uuid_type, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision in ('accept', 'reject', 'needs_evidence')",
            name="ck_review_decisions_decision",
        ),
        sa.CheckConstraint("sequence_number > 0", name="ck_review_decisions_sequence"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"]),
        sa.ForeignKeyConstraint(["supersedes_review_id"], ["review_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", "sequence_number"),
    )
    op.create_index("ix_review_decisions_finding_id", "review_decisions", ["finding_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_finding_id", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_index(
        "ix_finding_evidence_links_evidence_record_id", table_name="finding_evidence_links"
    )
    op.drop_index("ix_finding_evidence_links_finding_id", table_name="finding_evidence_links")
    op.drop_table("finding_evidence_links")
    op.drop_index("ix_findings_analysis_run_id", table_name="findings")
    op.drop_index("ix_findings_project_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index(
        "ix_analysis_context_snapshots_analysis_run_id", table_name="analysis_context_snapshots"
    )
    op.drop_table("analysis_context_snapshots")
    op.drop_index("ix_scientific_analysis_runs_project_id", table_name="scientific_analysis_runs")
    op.drop_table("scientific_analysis_runs")
