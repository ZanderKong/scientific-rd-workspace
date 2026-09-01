from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectStatus = Literal["active", "paused", "completed", "archived"]
ExperimentStatus = Literal["draft", "planned", "running", "completed", "cancelled"]


def non_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    status: ProjectStatus = "active"

    _title = field_validator("title")(non_blank)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    status: ProjectStatus | None = None

    _title = field_validator("title")(non_blank)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    description: str | None
    status: ProjectStatus
    experiment_count: int = 0
    created_at: datetime
    updated_at: datetime


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    version: int
    json_schema: dict[str, Any]
    ui_schema: dict[str, Any] | None
    is_active: bool
    created_at: datetime


class ExperimentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    template_id: uuid.UUID
    status: ExperimentStatus = "draft"
    objective: str | None = Field(default=None, max_length=10000)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    note_document: list[dict[str, Any]] = Field(default_factory=list)

    _title = field_validator("title")(non_blank)


class ExperimentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: ExperimentStatus | None = None
    objective: str | None = Field(default=None, max_length=10000)
    structured_data: dict[str, Any] | None = None
    note_document: list[dict[str, Any]] | None = None

    _title = field_validator("title")(non_blank)


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    project_id: uuid.UUID
    template_id: uuid.UUID
    template_version: int
    parent_experiment_id: uuid.UUID | None
    title: str
    status: ExperimentStatus
    objective: str | None
    structured_data: dict[str, Any]
    note_document: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class CloneRequest(BaseModel):
    new_title: str = Field(min_length=1, max_length=240)
    copy_note: bool = True
    copy_structured_data: bool = True

    _title = field_validator("new_title")(non_blank)


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    original_filename: str
    content_type: str | None
    size_bytes: int
    sha256: str
    created_at: datetime


class RevisionCreate(BaseModel):
    change_note: str | None = Field(default=None, max_length=500)


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    revision_number: int
    snapshot_json: dict[str, Any]
    change_note: str | None
    created_at: datetime
