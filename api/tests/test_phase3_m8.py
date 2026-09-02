from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import (
    Experiment,
    ExperimentProvenanceLink,
    ExperimentTemplate,
    Finding,
    Project,
    ReviewDecision,
    ScientificAnalysisRun,
)
from app.services import canonical_json_hash


def _fixture(db):
    project = Project(code="PRJ-M8", title="M8 demo", status="active")
    template = ExperimentTemplate(
        key="m8-template",
        name="M8 template",
        version=1,
        is_active=True,
        json_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"temperature": {"type": "number"}},
        },
    )
    db.add_all([project, template])
    db.flush()
    parent = Experiment(
        code="EXP-M8-BASE",
        project_id=project.id,
        template_id=template.id,
        template_version=1,
        title="Base",
        status="completed",
        objective="Base objective",
        structured_data={"temperature": 60},
        note_document=[],
    )
    db.add(parent)
    db.flush()
    run = ScientificAnalysisRun(
        project_id=project.id,
        purpose="interactive",
        status="completed",
        provider_key="fixture",
        model_profile_key="analysis-default",
        structured_output_mode="native_schema",
        requested_model="fixture-model",
        prompt_key="scientific_analysis",
        prompt_version=1,
        prompt_sha256="a" * 64,
        output_schema_version=1,
        workflow_version=1,
        generation_parameters_json={},
        model_metadata_json={},
    )
    db.add(run)
    db.flush()
    prefill = {
        "title": "Test follow-up",
        "objective": "Test the changed temperature",
        "template_id": str(template.id),
        "template_version": 1,
        "parent_experiment_id": str(parent.id),
        "structured_data": {"temperature": 80},
        "control_strategy": "Hold the base formulation constant.",
        "addresses_missing_evidence_codes": [],
        "change_operations": [
            {"op": "set", "path": "/temperature", "value": 80, "rationale": "Test effect."}
        ],
    }
    finding = Finding(
        project_id=project.id,
        analysis_run_id=run.id,
        ordinal=0,
        claim="Temperature comparison",
        claim_type="comparative_finding",
        confidence_label="high",
        confidence_rationale="Frozen comparison",
        applicability_scope="Demo",
        limitations_json=[],
        risks_json=[],
        missing_evidence_json=[],
        comparison_assertions_json=[],
        structured_support_json=[],
        suggested_next_experiment_json={
            "validation_status": "valid",
            "prefill": prefill,
            "suggestion_hash": canonical_json_hash(prefill),
        },
        model_proposed_gate_status="supported",
        model_proposed_gate_rationale="Verified",
        evidence_gate_status="supported",
        evidence_gate_rationale_json={},
        gate_policy_version=1,
        review_status="accepted",
    )
    db.add(finding)
    db.flush()
    review = ReviewDecision(
        finding_id=finding.id,
        sequence_number=1,
        decision="accept",
        reviewer_name="Scientist",
        comment="Accepted for follow-up.",
    )
    db.add(review)
    db.commit()
    return project, template, parent, finding, review


def test_prefill_requires_review_and_submit_creates_atomic_provenance(db):
    project, template, parent, finding, review = _fixture(db)
    client = TestClient(app)
    response = client.get(f"/api/v1/findings/{finding.id}/suggested-experiment-prefill")
    assert response.status_code == 200
    prefill = response.json()
    assert prefill["parent_experiment_id"] == str(parent.id)
    assert prefill["template_version"] == 1

    created = client.post(
        f"/api/v1/projects/{project.id}/experiments",
        json={
            "title": "Edited follow-up",
            "objective": "Edited objective",
            "template_id": str(template.id),
            "status": "draft",
            "structured_data": {"temperature": 85},
            "suggestion_origin": {
                "finding_id": str(finding.id),
                "analysis_run_id": str(finding.analysis_run_id),
                "enabling_review_decision_id": str(review.id),
                "suggestion_hash": prefill["suggestion_hash"],
                "template_id": prefill["template_id"],
                "template_version": prefill["template_version"],
                "parent_experiment_id": prefill["parent_experiment_id"],
            },
        },
    )
    assert created.status_code == 201, created.text
    experiment_id = uuid.UUID(created.json()["id"])
    experiment = db.get(Experiment, experiment_id)
    link = db.scalar(
        select(ExperimentProvenanceLink).where(
            ExperimentProvenanceLink.experiment_id == experiment_id
        )
    )
    assert experiment is not None and experiment.status == "draft"
    assert experiment.parent_experiment_id == parent.id
    assert link is not None and link.finding_id == finding.id
    assert link.submitted_values_snapshot_json["structured_data"] == {"temperature": 85}
    assert client.get(f"/api/v1/experiments/{experiment_id}/provenance").status_code == 200


def test_prefill_submission_rejects_stale_review_without_creating_experiment(db):
    project, template, _parent, finding, review = _fixture(db)
    client = TestClient(app)
    prefill = client.get(f"/api/v1/findings/{finding.id}/suggested-experiment-prefill").json()
    newer = client.post(
        f"/api/v1/findings/{finding.id}/reviews",
        json={
            "decision": "needs_evidence",
            "reviewer_name": "Second scientist",
            "comment": "Please add an isolating control.",
            "supersedes_review_id": str(review.id),
        },
    )
    assert newer.status_code == 201
    response = client.post(
        f"/api/v1/projects/{project.id}/experiments",
        json={
            "title": prefill["title"],
            "objective": prefill["objective"],
            "template_id": str(template.id),
            "status": "draft",
            "structured_data": prefill["structured_data"],
            "suggestion_origin": {
                "finding_id": str(finding.id),
                "analysis_run_id": str(finding.analysis_run_id),
                "enabling_review_decision_id": str(review.id),
                "suggestion_hash": prefill["suggestion_hash"],
                "template_id": prefill["template_id"],
                "template_version": prefill["template_version"],
                "parent_experiment_id": prefill["parent_experiment_id"],
            },
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "suggestion_review_changed"
    assert len(db.scalars(select(Experiment).where(Experiment.project_id == project.id)).all()) == 1
