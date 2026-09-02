from __future__ import annotations

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.context_builder import ContextValidationError, build_scientific_context
from app.core.config import Settings, get_settings
from app.main import app
from app.models import (
    Attachment,
    EvidenceRecord,
    Experiment,
    ExperimentRevision,
    ExperimentTemplate,
    Finding,
    Measurement,
    MeasurementImport,
    MeasurementPoint,
    Project,
)
from app.schemas import AnalysisRunCreate
from app.scientific_ai_service import AnalysisFailure, create_analysis_run
from app.services import _snapshot

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "additives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
                    "unit": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "drying_temperature": {"type": "number"},
    },
}


def _make_fixture(db, count: int = 3):
    project = Project(
        code=f"PRJ-{uuid.uuid4().hex[:8]}", title="Phase 3 test project", status="active"
    )
    template = ExperimentTemplate(
        key=f"phase3-template-{uuid.uuid4().hex[:8]}",
        name="Phase 3 test template",
        version=1,
        json_schema=SCHEMA,
        is_active=True,
    )
    db.add_all([project, template])
    db.flush()
    experiments = []
    measurements = []
    for index in range(count):
        additives = []
        if index >= 1:
            additives.append({"name": "KI", "amount": 1, "unit": "g"})
        if index >= 2:
            additives.append({"name": "starch", "amount": 1, "unit": "wt%"})
        experiment = Experiment(
            code=f"EXP-{uuid.uuid4().hex[:8]}-{index}",
            project_id=project.id,
            template_id=template.id,
            template_version=1,
            title=f"Formulation {index}",
            status="completed",
            objective="Compare formulations",
            structured_data={"additives": additives, "drying_temperature": 60},
            note_document=[],
        )
        db.add(experiment)
        db.flush()
        attachment = Attachment(
            experiment_id=experiment.id,
            original_filename=f"measurement-{index}.csv",
            storage_key=f"phase3/{experiment.id}/{index}.csv",
            content_type="text/csv",
            size_bytes=16,
            sha256=hashlib.sha256(f"measurement-{index}".encode()).hexdigest(),
        )
        db.add(attachment)
        db.flush()
        import_record = MeasurementImport(
            experiment_id=experiment.id,
            source_attachment_id=attachment.id,
            status="completed",
            source_format="csv",
            parser_key="tabular-xy",
            parser_version=1,
            source_sha256=attachment.sha256,
            header_json=["x", "y"],
            source_metadata_json={},
            mapping_json={},
            warnings_json=[],
            errors_json=[],
            row_count=2,
        )
        db.add(import_record)
        db.flush()
        measurement = Measurement(
            experiment_id=experiment.id,
            import_id=import_record.id,
            name=f"Response {index}",
            measurement_type="other_xy",
            schema_key="xy-series",
            schema_version=1,
            default_chart_type="line",
            x_label="x",
            x_unit="nm",
            y_label="y",
            y_unit="AU",
            row_count=2,
            summary_json={
                "x_min": 0,
                "x_max": 1,
                "y_min": 1 + index,
                "y_max": 2 + index,
                "y_mean": 1.5 + index,
            },
            points_sha256=hashlib.sha256(f"points-{index}".encode()).hexdigest(),
        )
        db.add(measurement)
        db.flush()
        db.add_all(
            [
                MeasurementPoint(
                    measurement_id=measurement.id,
                    ordinal=0,
                    source_row_number=2,
                    x_value=0,
                    y_value=1 + index,
                ),
                MeasurementPoint(
                    measurement_id=measurement.id,
                    ordinal=1,
                    source_row_number=3,
                    x_value=1,
                    y_value=2 + index,
                ),
            ]
        )
        experiments.append(experiment)
        measurements.append(measurement)
    db.flush()
    for experiment in experiments:
        db.refresh(experiment)
        db.add(
            ExperimentRevision(
                experiment_id=experiment.id,
                revision_number=1,
                snapshot_json=_snapshot(experiment),
                change_note="test snapshot",
            )
        )
    db.commit()
    return project, template, experiments, measurements


def _payload(experiments, measurements, profile="analysis-default"):
    return {
        "experiment_selections": [
            {"experiment_id": str(item.id), "revision_number": 1} for item in experiments
        ],
        "measurement_ids": [str(item.id) for item in measurements],
        "literature_ids": [],
        "evidence_ids": [],
        "model_profile_key": profile,
        "prompt_version": 1,
    }


def test_context_is_frozen_and_factor_diff_is_name_addressable(db):
    project, _, experiments, measurements = _make_fixture(db, 3)
    payload = AnalysisRunCreate.model_validate(_payload(experiments, measurements))
    context, digest, size = build_scientific_context(db, project.id, payload, Settings())
    from app.context_builder import canonical_bytes

    assert digest == hashlib.sha256(canonical_bytes(context)).hexdigest()
    assert size > 0
    paths = {item["path"] for item in context["factor_differences"] if item["differs"]}
    assert "/additives/@KI" in paths
    assert "/additives/@starch" in paths
    assert context["measurements"][0]["import"]["source_sha256"]
    experiments[0].title = "mutated after revision"
    db.commit()
    with pytest.raises(ContextValidationError, match="changed since revision"):
        build_scientific_context(db, project.id, payload, Settings())


def test_fixture_analysis_supports_comparison_without_evidence_and_caps_causality(db, monkeypatch):
    project, _, experiments, measurements = _make_fixture(db, 3)
    monkeypatch.setenv("AI_PROVIDER", "fixture")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post(
        f"/api/v1/projects/{project.id}/analysis-runs", json=_payload(experiments, measurements)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["langfuse_sync_status"] == "disabled"
    assert body["langfuse_trace_id"] is None
    assert len(body["findings"]) == 2
    assert body["findings"][0]["evidence_gate_status"] == "supported"
    assert body["findings"][0]["structured_support_json"][0]["verified"] is True
    assert body["findings"][1]["evidence_gate_status"] == "insufficient_evidence"
    assert (
        "confounded_variables"
        in body["findings"][1]["evidence_gate_rationale_json"]["reason_codes"]
    )
    get_settings.cache_clear()


def test_json_object_profile_is_exposed_and_runs(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    client = TestClient(app)
    profiles = client.get("/api/v1/ai/model-profiles")
    assert profiles.status_code == 200
    profile = next(item for item in profiles.json() if item["key"] == "analysis-json")
    assert profile["structured_output_mode"] == "json_object"
    response = client.post(
        f"/api/v1/projects/{project.id}/analysis-runs",
        json=_payload(experiments, measurements, "analysis-json"),
    )
    assert response.status_code == 201, response.text
    assert response.json()["structured_output_mode"] == "json_object"


def test_invalid_direct_support_fails_without_partial_findings(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    invalid = {
        "analysis_summary": "invalid",
        "findings": [
            {
                "claim": "The comparison is invalid",
                "claim_type": "comparative_finding",
                "confidence_label": "high",
                "confidence_rationale": "test",
                "applicability_scope": "test",
                "evidence_links": [],
                "structured_support_assertions": [
                    {
                        "kind": "measurement_comparison",
                        "left_measurement_id": str(measurements[0].id),
                        "right_measurement_id": str(measurements[1].id),
                        "metric": "y_mean",
                        "relation": "less_than",
                        "rationale": "wrong direction",
                    }
                ],
                "limitations": [],
                "risks": [],
                "missing_evidence": [],
                "comparison_assertions": [],
                "causal_target": None,
                "suggested_next_experiment": None,
                "proposed_gate": {"status": "supported", "rationale": "test"},
            }
        ],
    }
    payload = AnalysisRunCreate.model_validate(_payload(experiments, measurements))
    with pytest.raises(AnalysisFailure):
        create_analysis_run(db, project.id, payload, Settings(), fixture_response=invalid)
    assert db.scalar(select(func.count()).select_from(Finding)) == 0


def test_review_decisions_are_append_only_and_supersede_latest(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    client = TestClient(app)
    created = client.post(
        f"/api/v1/projects/{project.id}/analysis-runs", json=_payload(experiments, measurements)
    )
    assert created.status_code == 201, created.text
    finding = created.json()["findings"][0]
    first = client.post(
        f"/api/v1/findings/{finding['id']}/reviews",
        json={"decision": "accept", "reviewer_name": "Scientist"},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v1/findings/{finding['id']}/reviews",
        json={
            "decision": "needs_evidence",
            "reviewer_name": "Scientist",
            "comment": "Add control",
            "supersedes_review_id": first.json()["id"],
        },
    )
    assert second.status_code == 201, second.text
    stale = client.post(
        f"/api/v1/findings/{finding['id']}/reviews",
        json={
            "decision": "reject",
            "reviewer_name": "Scientist",
            "reason_code": "wrong",
            "comment": "stale",
            "supersedes_review_id": first.json()["id"],
        },
    )
    assert stale.status_code == 409
    finding_row = db.get(Finding, uuid.UUID(finding["id"]))
    assert finding_row is not None
    finding_row.claim = "attempted mutation"
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()


def test_gate_covers_partial_and_contradicted_states(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    contradiction = EvidenceRecord(
        project_id=project.id,
        context_experiment_id=experiments[1].id,
        claim_text="The selected response does not improve.",
        stance="contradicts",
        source_type="measurement",
        measurement_id=measurements[1].id,
        source_snapshot_json={"measurement_id": str(measurements[1].id)},
        status="active",
    )
    db.add(contradiction)
    db.commit()
    payload = AnalysisRunCreate.model_validate(
        _payload(experiments, measurements) | {"evidence_ids": [str(contradiction.id)]}
    )
    partial = {
        "analysis_summary": "partial",
        "findings": [
            {
                "claim": "The response is higher.",
                "claim_type": "comparative_finding",
                "confidence_label": "high",
                "confidence_rationale": "test",
                "applicability_scope": "test",
                "evidence_links": [],
                "structured_support_assertions": [
                    {
                        "kind": "measurement_comparison",
                        "left_measurement_id": str(measurements[0].id),
                        "right_measurement_id": str(measurements[1].id),
                        "metric": "y_mean",
                        "relation": "greater_than",
                        "rationale": "frozen summaries",
                    }
                ],
                "limitations": [{"code": "small_sample", "description": "demo"}],
                "risks": [],
                "missing_evidence": [],
                "comparison_assertions": [],
                "causal_target": None,
                "suggested_next_experiment": None,
                "proposed_gate": {"status": "supported", "rationale": "model"},
            }
        ],
    }
    run = create_analysis_run(db, project.id, payload, Settings(), fixture_response=partial)
    assert run.findings[0].evidence_gate_status == "partially_supported"

    contradicted = {
        "analysis_summary": "contradicted",
        "findings": [
            {
                "claim": "The response is higher.",
                "claim_type": "scientific_observation",
                "confidence_label": "medium",
                "confidence_rationale": "test",
                "applicability_scope": "test",
                "evidence_links": [
                    {
                        "evidence_id": str(contradiction.id),
                        "role": "contradicting",
                        "rationale": "counter observation",
                    }
                ],
                "structured_support_assertions": [],
                "limitations": [],
                "risks": [],
                "missing_evidence": [],
                "comparison_assertions": [],
                "causal_target": None,
                "suggested_next_experiment": None,
                "proposed_gate": {"status": "supported", "rationale": "model"},
            }
        ],
    }
    payload2 = AnalysisRunCreate.model_validate(
        _payload(experiments, measurements) | {"evidence_ids": [str(contradiction.id)]}
    )
    run2 = create_analysis_run(db, project.id, payload2, Settings(), fixture_response=contradicted)
    assert run2.findings[0].evidence_gate_status == "contradicted"
