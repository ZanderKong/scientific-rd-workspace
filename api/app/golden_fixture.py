"""Named, repeat-safe synthetic fixture used by release verification.

The fixture deliberately models a small Cl₂ sensor workflow without retaining any
v0.2 compatibility payloads.  It is a test fixture, not application bootstrap data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.models import (
    ClaimEvidence,
    DataRecord,
    DataRepresentation,
    ProcessExecution,
    ProcessExecutionDataBinding,
    ProcessExecutionObjectBinding,
    ResearchObject,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class GoldenCl2Workflow:
    """Stable identifiers for the synthetic chlorine-sensor acceptance fixture."""

    project_code: str = "PRJ-001"
    sample_code: str = "ROO-007"
    response_data_code: str = "DAT-001"
    growth_rate_data_code: str = "DAT-002"
    source_data_code: str = "DAT-003"
    view_code: str = "VEW-001"
    claim_code: str = "CLM-001"


class GoldenCl2WorkflowFactory:
    """Creates and verifies the v0.3 golden scientific workflow."""

    fixture = GoldenCl2Workflow()

    def create(self) -> GoldenCl2Workflow:
        """Create the fixture through the canonical seed entrypoint, safely more than once."""
        from app.seed import seed

        seed()
        return self.fixture

    def verify(self, db: Session) -> GoldenCl2Workflow:
        fixture = self.fixture
        project = db.scalar(
            select(ResearchObject).where(
                ResearchObject.code == fixture.project_code,
                ResearchObject.kind == "project",
            )
        )
        if project is None:
            raise AssertionError("golden fixture project is missing")

        records = {
            item.code: item
            for item in db.scalars(
                select(ResearchObject).where(
                    ResearchObject.code.in_(
                        [
                            fixture.sample_code,
                            fixture.response_data_code,
                            fixture.growth_rate_data_code,
                            fixture.source_data_code,
                            fixture.view_code,
                            fixture.claim_code,
                        ]
                    )
                )
            )
        }
        expected_kinds = {
            fixture.sample_code: "research_object",
            fixture.response_data_code: "data",
            fixture.growth_rate_data_code: "data",
            fixture.source_data_code: "data",
            fixture.view_code: "view",
            fixture.claim_code: "claim",
        }
        if {code: item.kind for code, item in records.items()} != expected_kinds:
            raise AssertionError("golden fixture uses missing or non-canonical object kinds")
        if records[fixture.sample_code].project_scope_id != project.id:
            raise AssertionError("golden sample is outside the golden project scope")

        representation_count = db.scalar(
            select(func.count())
            .select_from(DataRepresentation)
            .where(
                DataRepresentation.data_object_id.in_(
                    [
                        records[fixture.response_data_code].id,
                        records[fixture.growth_rate_data_code].id,
                        records[fixture.source_data_code].id,
                    ]
                )
            )
        )
        if representation_count != 3:
            raise AssertionError("golden data records do not have their expected representations")
        if (
            db.scalar(
                select(func.count())
                .select_from(DataRecord)
                .where(DataRecord.data_object_id.in_([item.id for item in records.values()]))
            )
            < 3
        ):
            raise AssertionError("golden data records are incomplete")

        producer_rows = db.scalars(
            select(ProcessExecutionDataBinding).where(
                ProcessExecutionDataBinding.data_id.in_(
                    [
                        records[fixture.response_data_code].id,
                        records[fixture.growth_rate_data_code].id,
                    ]
                ),
                ProcessExecutionDataBinding.direction == "output",
            )
        ).all()
        if len(producer_rows) != 2:
            raise AssertionError("golden response and derived data require one producer each")
        sample_bindings = db.scalar(
            select(func.count())
            .select_from(ProcessExecutionObjectBinding)
            .where(
                ProcessExecutionObjectBinding.research_object_id == records[fixture.sample_code].id,
                ProcessExecutionObjectBinding.role == "product",
            )
        )
        if sample_bindings != 1:
            raise AssertionError("golden sample must be produced exactly once")
        if db.scalar(select(func.count()).select_from(ProcessExecution)) != 4:
            raise AssertionError("golden workflow must contain four process executions")
        if (
            db.scalar(
                select(func.count())
                .select_from(ClaimEvidence)
                .where(ClaimEvidence.claim_id == records[fixture.claim_code].id)
            )
            != 2
        ):
            raise AssertionError("golden claim must retain both data and view evidence")
        return fixture
