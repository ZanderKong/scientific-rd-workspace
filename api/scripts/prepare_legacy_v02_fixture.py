"""Insert a minimal, realistic v0.2 fixture after upgrading a database to revision 0006."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.db import SessionLocal

PROJECT_TYPE = uuid.UUID("00000000-0000-0000-0000-000000000101")
SAMPLE_TYPE = uuid.UUID("00000000-0000-0000-0000-000000000102")
DATA_TYPE = uuid.UUID("00000000-0000-0000-0000-000000000103")
PROJECT_VERSION = uuid.UUID("00000000-0000-0000-0000-000000000201")
SAMPLE_VERSION = uuid.UUID("00000000-0000-0000-0000-000000000202")
DATA_VERSION = uuid.UUID("00000000-0000-0000-0000-000000000203")
PROJECT = uuid.UUID("00000000-0000-0000-0000-000000000301")
SAMPLE = uuid.UUID("00000000-0000-0000-0000-000000000302")
DATA = uuid.UUID("00000000-0000-0000-0000-000000000303")


def main() -> None:
    with SessionLocal.begin() as db:
        for type_id, key, kind, label in (
            (PROJECT_TYPE, "project.legacy", "project", "Legacy project"),
            (SAMPLE_TYPE, "sample.legacy", "sample", "Legacy sample"),
            (DATA_TYPE, "data.legacy", "data", "Legacy data"),
        ):
            db.execute(
                text(
                    "INSERT INTO object_types (id, key, kind, label_zh, label_en, is_default) "
                    "VALUES (:id, :key, :kind, :label, :label, false)"
                ),
                {"id": type_id, "key": key, "kind": kind, "label": label},
            )
        for version_id, type_id in (
            (PROJECT_VERSION, PROJECT_TYPE),
            (SAMPLE_VERSION, SAMPLE_TYPE),
            (DATA_VERSION, DATA_TYPE),
        ):
            db.execute(
                text(
                    "INSERT INTO object_type_versions "
                    "(id, object_type_id, version, json_schema, is_active) "
                    "VALUES (:id, :type_id, 1, '{}'::jsonb, true)"
                ),
                {"id": version_id, "type_id": type_id},
            )
        for object_id, code, kind, title, scope, version_id in (
            (
                PROJECT,
                "PRJ-LEGACY-001",
                "project",
                "Legacy migration project",
                None,
                PROJECT_VERSION,
            ),
            (SAMPLE, "SMP-LEGACY-001", "sample", "Legacy sample", PROJECT, SAMPLE_VERSION),
            (DATA, "DAT-LEGACY-001", "data", "Legacy response", PROJECT, DATA_VERSION),
        ):
            db.execute(
                text(
                    "INSERT INTO research_objects "
                    "(id, code, kind, title, status, project_scope_id, type_version_id, "
                    "properties_jsonb, content_document) "
                    "VALUES (:id, :code, :kind, :title, 'active', :scope, :version_id, "
                    "'{}'::jsonb, '[]'::jsonb)"
                ),
                {
                    "id": object_id,
                    "code": code,
                    "kind": kind,
                    "title": title,
                    "scope": scope,
                    "version_id": version_id,
                },
            )
    print("Legacy v0.2 migration fixture prepared")


if __name__ == "__main__":
    main()
