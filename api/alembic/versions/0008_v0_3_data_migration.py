"""Copy v0.2 records into the v0.3 canonical model."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_v0_3_data_migration"
down_revision: str | Sequence[str] | None = "0007_v0_3_canonical_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        UPDATE research_objects SET tags_jsonb = CASE kind
          WHEN 'material' THEN CASE WHEN tags_jsonb @> '[\"原料\"]'::jsonb THEN tags_jsonb ELSE tags_jsonb || '[\"原料\"]'::jsonb END
          WHEN 'equipment' THEN CASE WHEN tags_jsonb @> '[\"设备\"]'::jsonb THEN tags_jsonb ELSE tags_jsonb || '[\"设备\"]'::jsonb END
          WHEN 'sample' THEN CASE WHEN tags_jsonb @> '[\"样品\"]'::jsonb THEN tags_jsonb ELSE tags_jsonb || '[\"样品\"]'::jsonb END
          ELSE tags_jsonb END
        WHERE kind IN ('material','equipment','sample')
        """
    )
    op.execute(
        """
        UPDATE object_types SET is_default = false
        WHERE kind IN ('material','sample','equipment','process')
        """
    )
    op.execute(
        """
        UPDATE object_types SET kind = CASE kind
          WHEN 'material' THEN 'research_object'
          WHEN 'sample' THEN 'research_object'
          WHEN 'equipment' THEN 'research_object'
          WHEN 'process' THEN 'process_definition'
          ELSE kind END
        WHERE kind IN ('material','sample','equipment','process')
        """
    )
    op.execute(
        """
        UPDATE research_objects SET kind = CASE kind
          WHEN 'material' THEN 'research_object'
          WHEN 'sample' THEN 'research_object'
          WHEN 'equipment' THEN 'research_object'
          WHEN 'process' THEN 'process_definition'
          ELSE kind END,
          process_field_definitions_jsonb = COALESCE(usage_schema_jsonb, '{}'::jsonb)
        """
    )
    op.execute("UPDATE object_types SET is_default = true WHERE key = 'material.generic'")
    op.execute(
        "UPDATE object_types SET key = 'research_object.material' WHERE key = 'material.generic'"
    )
    op.execute(
        "UPDATE object_types SET key = 'research_object.sample' WHERE key = 'sample.generic'"
    )
    op.execute(
        "UPDATE object_types SET key = 'research_object.equipment' WHERE key = 'equipment.generic'"
    )
    op.execute(
        "UPDATE object_types SET key = 'process_definition.generic' WHERE key = 'process.generic'"
    )

    op.execute(
        """
        INSERT INTO assets (id, storage_backend, bucket, object_key, original_filename,
                            mime_type, size_bytes, sha256, created_at)
        SELECT id, 'local', NULL, storage_key, original_filename, content_type,
               size_bytes, sha256, created_at
        FROM legacy_attachments
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO object_asset_links (object_id, asset_id, role, order_index, created_at)
        SELECT object_id, id, 'attachment', 0, created_at
        FROM legacy_attachments
        ON CONFLICT (object_id, asset_id, role) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO data_records (data_object_id, scientific_type, description)
        SELECT id,
               CASE properties_jsonb ->> 'measurement_kind'
                 WHEN 'spectral_response' THEN 'xy_series'
                 ELSE NULL END,
               NULL
        FROM research_objects
        WHERE kind = 'data'
        ON CONFLICT (data_object_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO data_representations
          (id, data_object_id, kind, name, format, schema_jsonb, metadata_jsonb,
           summary_jsonb, inline_payload_jsonb, asset_id, source_representation_id,
           provenance_jsonb, representation_sha256, created_at)
        SELECT p.id, p.data_object_id,
               CASE p.payload_kind WHEN 'scalar' THEN 'structured'
                                   WHEN 'file' THEN 'raw_file'
                                   ELSE 'table' END,
               p.name, p.schema_key, '{}'::jsonb, p.metadata_jsonb, p.summary_jsonb,
               NULL, a.id, NULL, jsonb_build_object('migrated_from', 'data_payloads'),
               p.payload_sha256, p.created_at
        FROM legacy_data_payloads p
        LEFT JOIN legacy_attachments old_a ON old_a.id = p.source_attachment_id
        LEFT JOIN assets a ON a.id = old_a.id
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO data_scalars (representation_id, value, unit)
        SELECT payload_id, value, unit FROM legacy_data_scalars
        ON CONFLICT (representation_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO data_points (representation_id, ordinal, source_row_number, x_value, y_value)
        SELECT payload_id, ordinal, source_row_number, x_value, y_value
        FROM legacy_data_points
        ON CONFLICT (representation_id, ordinal) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO data_table_rows (representation_id, ordinal, source_row_number, values_jsonb)
        SELECT payload_id, ordinal, source_row_number, values_jsonb
        FROM legacy_data_table_rows
        ON CONFLICT (representation_id, ordinal) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE data_records r SET origin_representation_id = x.id
        FROM (SELECT DISTINCT ON (data_object_id) id, data_object_id
              FROM data_representations ORDER BY data_object_id, created_at, id) x
        WHERE r.data_object_id = x.data_object_id AND r.origin_representation_id IS NULL
        """
    )
    op.execute(
        """
        INSERT INTO data_imports
          (id, data_object_id, source_asset_id, representation_id, status, source_format,
           parser_key, parser_version, sheet_name, source_sha256, header_json,
           metadata_jsonb, mapping_json, warnings_json, errors_json, row_count,
           created_at, completed_at)
        SELECT i.id, i.data_object_id, a.id, i.payload_id,
               CASE WHEN i.status IN ('preview_ready','completed','failed') THEN i.status ELSE 'failed' END,
               CASE WHEN i.source_format IN ('csv','xlsx') THEN i.source_format ELSE 'csv' END,
               i.parser_key, i.parser_version, i.sheet_name, i.source_sha256, i.header_json,
               i.metadata_jsonb, i.mapping_json, i.warnings_json, i.errors_json, i.row_count,
               i.created_at, i.completed_at
        FROM legacy_data_imports i
        JOIN assets a ON a.id = i.source_attachment_id
        ON CONFLICT (id) DO NOTHING
        """
    )

    # Every former process row becomes a definition plus one execution identity.
    op.execute(
        """
        INSERT INTO process_definition_versions
          (id, process_definition_id, version, description,
           execution_field_definitions_jsonb, ui_schema_jsonb, created_at)
        SELECT gen_random_uuid(), id, 1, properties_jsonb ->> 'description',
               COALESCE(usage_schema_jsonb, '{}'::jsonb), NULL, created_at
        FROM research_objects
        WHERE kind = 'process_definition'
        ON CONFLICT (process_definition_id, version) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO process_definition_state (process_definition_id, current_version_id)
        SELECT v.process_definition_id, v.id
        FROM process_definition_versions v
        ON CONFLICT (process_definition_id) DO NOTHING
        """
    )
    op.execute(
        "CREATE TEMP TABLE legacy_sample_execution_map (sample_execution_id uuid primary key, execution_id uuid not null) ON COMMIT DROP"
    )
    op.execute(
        "INSERT INTO legacy_sample_execution_map SELECT id, gen_random_uuid() FROM legacy_sample_executions"
    )
    op.execute(
        "CREATE TEMP TABLE legacy_process_execution_map (process_id uuid primary key, execution_id uuid not null) ON COMMIT DROP"
    )
    op.execute(
        "INSERT INTO legacy_process_execution_map SELECT id, gen_random_uuid() FROM research_objects WHERE kind = 'process_definition'"
    )
    op.execute(
        """
        INSERT INTO process_executions
          (id, project_scope_id, process_definition_id, process_definition_version_id,
           title_snapshot, status, execution_field_definition_snapshot_jsonb,
           values_jsonb, note, occurred_at, started_at, completed_at, created_at, updated_at)
        SELECT m.execution_id, p.project_scope_id, p.id, s.current_version_id, p.title, 'completed',
               v.execution_field_definitions_jsonb,
               COALESCE(
                 (
                   SELECT jsonb_object_agg(parameter.key, parameter.value)
                   FROM jsonb_each(COALESCE(p.properties_jsonb -> 'parameters', '{}'::jsonb)) AS parameter
                   WHERE NOT (
                     jsonb_typeof(parameter.value) = 'object'
                     AND parameter.value ? 'value_type'
                   )
                 ),
                 p.properties_jsonb -> 'values',
                 '{}'::jsonb
               ),
               NULL, NULL, p.created_at,
               p.updated_at, p.created_at, p.updated_at
        FROM research_objects p
        JOIN legacy_process_execution_map m ON m.process_id = p.id
        JOIN process_definition_state s ON s.process_definition_id = p.id
        JOIN process_definition_versions v ON v.id = s.current_version_id
        WHERE p.kind = 'process_definition'
        ON CONFLICT (id) DO NOTHING
        """
    )

    # Convert old graph edges into either execution bindings or references.
    op.execute(
        """
        INSERT INTO process_execution_object_bindings
          (id, execution_id, research_object_id, direction, role,
           field_definition_snapshot_jsonb, values_jsonb, order_index, created_at)
        SELECT gen_random_uuid(), m.execution_id, r.target_object_id,
               CASE WHEN r.relation_type = 'produces' THEN 'output' ELSE 'input' END,
               r.role, COALESCE(o.process_field_definitions_jsonb, '{}'::jsonb),
               (COALESCE(r.properties_jsonb, '{}'::jsonb) - 'usage_values') || COALESCE(r.properties_jsonb -> 'usage_values', '{}'::jsonb), 0, r.created_at
        FROM object_relations r
        JOIN research_objects source ON source.id = r.source_object_id
        JOIN research_objects o ON o.id = r.target_object_id
        JOIN legacy_process_execution_map m ON m.process_id = r.source_object_id
        WHERE source.kind = 'process_definition'
          AND o.kind <> 'data'
          AND r.relation_type IN ('uses','produces')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO process_execution_data_bindings
          (id, execution_id, data_id, direction, role, values_jsonb, order_index, created_at)
        SELECT gen_random_uuid(), m.execution_id, r.target_object_id,
               CASE WHEN r.relation_type = 'produces' THEN 'output' ELSE 'input' END,
               r.role, (COALESCE(r.properties_jsonb, '{}'::jsonb) - 'usage_values') || COALESCE(r.properties_jsonb -> 'usage_values', '{}'::jsonb), 0, r.created_at
        FROM object_relations r
        JOIN research_objects source ON source.id = r.source_object_id
        JOIN research_objects target ON target.id = r.target_object_id
        JOIN legacy_process_execution_map m ON m.process_id = r.source_object_id
        WHERE source.kind = 'process_definition'
          AND target.kind = 'data'
          AND r.relation_type IN ('uses','produces')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO process_execution_relations
          (id, source_execution_id, target_execution_id, relation_type, created_at)
        SELECT gen_random_uuid(), source_map.execution_id, target_map.execution_id, 'precedes', r.created_at
        FROM object_relations r
        JOIN research_objects source ON source.id = r.source_object_id
        JOIN research_objects target ON target.id = r.target_object_id
        JOIN legacy_process_execution_map source_map ON source_map.process_id = r.source_object_id
        JOIN legacy_process_execution_map target_map ON target_map.process_id = r.target_object_id
        WHERE source.kind = 'process_definition' AND target.kind = 'process_definition'
          AND r.relation_type = 'precedes'
        ON CONFLICT (source_execution_id, target_execution_id, relation_type) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE object_relations r
        SET relation_type = CASE
          WHEN source.kind = 'experiment' THEN 'references'
          ELSE 'related_to'
        END
        FROM research_objects source
        WHERE source.id = r.source_object_id
          AND r.relation_type IN ('contains','includes')
        """
    )
    op.execute("DELETE FROM object_relations WHERE relation_type IN ('uses','produces','precedes')")
    op.execute(
        """
        INSERT INTO object_relations
          (id, source_object_id, target_object_id, relation_type, role,
           properties_jsonb, created_at, updated_at)
        SELECT gen_random_uuid(), b.data_id, o.research_object_id, 'subject', NULL,
               '{"system_managed": true}'::jsonb, b.created_at, b.created_at
        FROM process_execution_data_bindings b
        JOIN process_execution_object_bindings o ON o.execution_id = b.execution_id
        WHERE b.direction = 'output' AND o.direction = 'input' AND o.role = 'subject'
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO object_relations
          (id, source_object_id, target_object_id, relation_type, role,
           properties_jsonb, created_at, updated_at)
        SELECT gen_random_uuid(), out_b.data_id, in_b.data_id, 'derived_from', NULL,
               '{"system_managed": true}'::jsonb, out_b.created_at, out_b.created_at
        FROM process_execution_data_bindings out_b
        JOIN process_execution_data_bindings in_b ON in_b.execution_id = out_b.execution_id
        WHERE out_b.direction = 'output' AND in_b.direction = 'input'
        ON CONFLICT DO NOTHING
        """
    )

    # Old SampleExecution rows without a resolvable process are pinned to one
    # explicit, clearly-labelled definition instead of guessing a real one.
    op.execute(
        """
        INSERT INTO research_objects
          (id, code, kind, title, status, project_scope_id, type_version_id,
           properties_jsonb, tags_jsonb, process_field_definitions_jsonb,
           content_document, created_at, updated_at)
        SELECT gen_random_uuid(), 'PFD-LEGACY-SAMPLE', 'process_definition',
               'Legacy Sample Execution', 'active', NULL, NULL, '{}'::jsonb,
               '[\"legacy\",\"migration\"]'::jsonb, '{}'::jsonb, '[]'::jsonb,
               now(), now()
        WHERE EXISTS (SELECT 1 FROM legacy_sample_executions)
          AND NOT EXISTS (
            SELECT 1 FROM research_objects WHERE code = 'PFD-LEGACY-SAMPLE'
          )
        """
    )
    op.execute(
        """
        INSERT INTO process_definition_versions
          (id, process_definition_id, version, description,
           execution_field_definitions_jsonb, ui_schema_jsonb, created_at)
        SELECT gen_random_uuid(), id, 1, 'Unresolved legacy SampleExecution', '{}', NULL, now()
        FROM research_objects
        WHERE code = 'PFD-LEGACY-SAMPLE'
          AND NOT EXISTS (
            SELECT 1 FROM process_definition_versions v
            WHERE v.process_definition_id = research_objects.id
          )
        """
    )
    op.execute(
        """
        INSERT INTO process_definition_state (process_definition_id, current_version_id)
        SELECT v.process_definition_id, v.id
        FROM process_definition_versions v
        JOIN research_objects d ON d.id = v.process_definition_id
        WHERE d.code = 'PFD-LEGACY-SAMPLE'
        ON CONFLICT (process_definition_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO process_executions
          (id, project_scope_id, process_definition_id, process_definition_version_id,
           title_snapshot, status, execution_field_definition_snapshot_jsonb,
           values_jsonb, note, occurred_at, started_at, completed_at, created_at, updated_at)
        SELECT m.execution_id, sample.project_scope_id, definition.id, state.current_version_id,
               'Migrated Sample Execution', e.status,
               version.execution_field_definitions_jsonb, e.plan_snapshot_jsonb,
               'migrate v0.2 SampleExecution', NULL, e.started_at, e.completed_at,
               e.created_at, e.updated_at
        FROM legacy_sample_executions e
        JOIN legacy_sample_execution_map m ON m.sample_execution_id = e.id
        JOIN research_objects sample ON sample.id = e.sample_id
        CROSS JOIN LATERAL (
          SELECT id FROM research_objects WHERE code = 'PFD-LEGACY-SAMPLE'
        ) definition
        JOIN process_definition_state state ON state.process_definition_id = definition.id
        JOIN process_definition_versions version ON version.id = state.current_version_id
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO process_execution_object_bindings
          (id, execution_id, research_object_id, direction, role,
           field_definition_snapshot_jsonb, values_jsonb, order_index, created_at)
        SELECT gen_random_uuid(), m.execution_id, e.sample_id, 'context', 'sample_record',
               '{}', '{}', 0, e.created_at
        FROM legacy_sample_executions e
        JOIN legacy_sample_execution_map m ON m.sample_execution_id = e.id
        JOIN process_executions execution ON execution.id = m.execution_id
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO process_execution_revisions
          (id, execution_id, revision_number, snapshot_jsonb, snapshot_sha256, change_note, created_at)
        SELECT gen_random_uuid(), m.execution_id, 1,
               jsonb_build_object('migrated_from', 'sample_executions', 'sample_id', e.sample_id,
                                  'semantic_resolution', 'unresolved'),
               encode(digest(jsonb_build_object('migrated_from', 'sample_executions', 'sample_id', e.sample_id,
                                                'semantic_resolution', 'unresolved')::text, 'sha256'), 'hex'),
               'migrate v0.2 SampleExecution', e.created_at
        FROM legacy_sample_executions e
        JOIN legacy_sample_execution_map m ON m.sample_execution_id = e.id
        ON CONFLICT (execution_id, revision_number) DO NOTHING
        """
    )
    for kind in (
        "research_object",
        "process_definition",
        "data",
        "experiment",
        "project",
        "view",
        "claim",
    ):
        op.get_bind().execute(
            sa.text(
                "INSERT INTO object_code_counters (kind, next_value) "
                "VALUES (:kind, 1) ON CONFLICT (kind) DO NOTHING"
            ),
            {"kind": kind},
        )


def downgrade() -> None:
    # 0009 owns removal of the copied legacy structures; reversing this data
    # migration would be lossy, so leave the canonical records in place.
    pass
