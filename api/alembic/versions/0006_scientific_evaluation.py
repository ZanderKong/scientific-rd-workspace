"""Add immutable evaluation cases, runs, results, and draft provenance links.

Revision ID: 0006_scientific_evaluation
Revises: 0005_scientific_analysis
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_scientific_evaluation"
down_revision = "0005_scientific_analysis"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
uuid_type = sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "evaluation_cases",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("case_type", sa.String(24), nullable=False),
        sa.Column("source_finding_id", uuid_type, nullable=False),
        sa.Column("source_review_decision_id", uuid_type, nullable=False),
        sa.Column("context_schema_version", sa.Integer(), nullable=False),
        sa.Column("context_snapshot_json", json_type, nullable=False),
        sa.Column("model_output_snapshot_json", json_type, nullable=False),
        sa.Column("finding_snapshot_json", json_type, nullable=False),
        sa.Column("gate_snapshot_json", json_type, nullable=False),
        sa.Column("review_snapshot_json", json_type, nullable=False),
        sa.Column("expected_behavior_json", json_type, nullable=False),
        sa.Column("case_tags_json", json_type, nullable=False),
        sa.Column("source_model_config_json", json_type, nullable=False),
        sa.Column("source_prompt_snapshot_json", json_type, nullable=False),
        sa.Column("case_hash", sa.String(64), nullable=False),
        sa.Column("langfuse_dataset_item_id", sa.String(255), nullable=True),
        sa.Column("langfuse_sync_status", sa.String(32), nullable=False),
        sa.Column("langfuse_error", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("case_type in ('bad_case', 'reference_case')", name="ck_evaluation_cases_case_type"),
        sa.CheckConstraint("context_schema_version > 0", name="ck_evaluation_cases_context_version"),
        sa.CheckConstraint("langfuse_sync_status in ('disabled', 'pending', 'synced', 'failed')", name="ck_evaluation_cases_langfuse_status"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_finding_id"], ["findings.id"]),
        sa.ForeignKeyConstraint(["source_review_decision_id"], ["review_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_review_decision_id"),
    )
    op.create_index("ix_evaluation_cases_project_id", "evaluation_cases", ["project_id"])
    op.create_index("ix_evaluation_cases_source_finding_id", "evaluation_cases", ["source_finding_id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column("model_profile_key", sa.String(120), nullable=False),
        sa.Column("structured_output_mode", sa.String(32), nullable=False),
        sa.Column("requested_model", sa.String(255), nullable=False),
        sa.Column("prompt_key", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("prompt_sha256", sa.String(64), nullable=False),
        sa.Column("prompt_snapshot_json", json_type, nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("output_schema_version", sa.Integer(), nullable=False),
        sa.Column("generation_parameters_json", json_type, nullable=False),
        sa.Column("judge_enabled", sa.Boolean(), nullable=False),
        sa.Column("judge_model_profile_key", sa.String(120), nullable=True),
        sa.Column("judge_structured_output_mode", sa.String(32), nullable=True),
        sa.Column("judge_prompt_version", sa.Integer(), nullable=True),
        sa.Column("baseline_run_id", uuid_type, nullable=True),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("completed_cases", sa.Integer(), nullable=False),
        sa.Column("passed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("error_cases", sa.Integer(), nullable=False),
        sa.Column("aggregate_scores_json", json_type, nullable=False),
        sa.Column("regression_summary_json", json_type, nullable=False),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("langfuse_experiment_name", sa.String(255), nullable=True),
        sa.Column("langfuse_sync_status", sa.String(32), nullable=False),
        sa.Column("langfuse_error", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('queued', 'running', 'completed', 'completed_with_errors', 'failed', 'interrupted', 'cancel_requested', 'cancelled')", name="ck_evaluation_runs_status"),
        sa.CheckConstraint("structured_output_mode in ('native_schema', 'json_object')", name="ck_evaluation_runs_output_mode"),
        sa.CheckConstraint("total_cases >= 0", name="ck_evaluation_runs_total_cases"),
        sa.CheckConstraint("completed_cases >= 0", name="ck_evaluation_runs_completed_cases"),
        sa.CheckConstraint("passed_cases >= 0", name="ck_evaluation_runs_passed_cases"),
        sa.CheckConstraint("failed_cases >= 0", name="ck_evaluation_runs_failed_cases"),
        sa.CheckConstraint("error_cases >= 0", name="ck_evaluation_runs_error_cases"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["evaluation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_project_id", "evaluation_runs", ["project_id"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("evaluation_run_id", uuid_type, nullable=False),
        sa.Column("evaluation_case_id", uuid_type, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("replay_analysis_run_id", uuid_type, nullable=True),
        sa.Column("deterministic_scores_json", json_type, nullable=False),
        sa.Column("judge_scores_json", json_type, nullable=True),
        sa.Column("judge_metadata_json", json_type, nullable=True),
        sa.Column("failure_tags_json", json_type, nullable=False),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("langfuse_trace_id", sa.String(255), nullable=True),
        sa.Column("langfuse_sync_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'running', 'passed', 'failed', 'error', 'cancelled')", name="ck_evaluation_results_status"),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"]),
        sa.ForeignKeyConstraint(["evaluation_case_id"], ["evaluation_cases.id"]),
        sa.ForeignKeyConstraint(["replay_analysis_run_id"], ["scientific_analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_run_id", "evaluation_case_id"),
        sa.UniqueConstraint("evaluation_run_id", "ordinal"),
    )
    op.create_index("ix_evaluation_results_evaluation_run_id", "evaluation_results", ["evaluation_run_id"])
    op.create_index("ix_evaluation_results_evaluation_case_id", "evaluation_results", ["evaluation_case_id"])

    op.create_table(
        "experiment_provenance_links",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("experiment_id", uuid_type, nullable=False),
        sa.Column("finding_id", uuid_type, nullable=False),
        sa.Column("analysis_run_id", uuid_type, nullable=False),
        sa.Column("enabling_review_decision_id", uuid_type, nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("suggestion_snapshot_json", json_type, nullable=False),
        sa.Column("submitted_values_snapshot_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("relation_type = 'suggested_from_finding'", name="ck_experiment_provenance_relation"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"]),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["scientific_analysis_runs.id"]),
        sa.ForeignKeyConstraint(["enabling_review_decision_id"], ["review_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id"),
    )
    op.create_index("ix_experiment_provenance_links_finding_id", "experiment_provenance_links", ["finding_id"])
    op.create_index("ix_experiment_provenance_links_analysis_run_id", "experiment_provenance_links", ["analysis_run_id"])
    op.create_index("ix_experiment_provenance_links_enabling_review_decision_id", "experiment_provenance_links", ["enabling_review_decision_id"])


def downgrade() -> None:
    op.drop_index("ix_experiment_provenance_links_enabling_review_decision_id", table_name="experiment_provenance_links")
    op.drop_index("ix_experiment_provenance_links_analysis_run_id", table_name="experiment_provenance_links")
    op.drop_index("ix_experiment_provenance_links_finding_id", table_name="experiment_provenance_links")
    op.drop_table("experiment_provenance_links")
    op.drop_index("ix_evaluation_results_evaluation_case_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_evaluation_run_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_index("ix_evaluation_runs_project_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_evaluation_cases_source_finding_id", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_project_id", table_name="evaluation_cases")
    op.drop_table("evaluation_cases")
