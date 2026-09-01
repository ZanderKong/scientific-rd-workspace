import { describe, expect, it } from 'vitest';
import { parseRevisionSnapshot } from './revision-snapshot';
import { buildStructuredUiSchema } from './structured-ui-schema';

describe('revision snapshots', () => {
  it('reads note and structured data from snapshot_json.experiment', () => {
    const snapshot = parseRevisionSnapshot({
      experiment: {
        title: 'EXP-045',
        status: 'completed',
        objective: null,
        template_id: 'template-v1',
        template_version: 1,
        structured_data: { concentration: { value: 5, unit: 'wt%' } },
        note_document: [{ type: 'paragraph', content: [] }]
      },
      attachments: []
    });

    expect(snapshot?.experiment.note_document).toEqual([{ type: 'paragraph', content: [] }]);
    expect(snapshot?.experiment.structured_data).toEqual({
      concentration: { value: 5, unit: 'wt%' }
    });
  });

  it('generates nested controls for quantity objects', () => {
    const uiSchema = buildStructuredUiSchema({
      type: 'object',
      properties: {
        concentration: {
          type: 'object',
          title: 'Concentration',
          properties: { value: { type: 'number' }, unit: { type: 'string' } }
        }
      }
    });

    expect(uiSchema.elements).toEqual([
      {
        type: 'Group',
        label: 'Concentration',
        elements: [
          { type: 'Control', scope: '#/properties/concentration/properties/value' },
          { type: 'Control', scope: '#/properties/concentration/properties/unit' }
        ]
      }
    ]);
  });

  it('preserves v2 read-only references while accepting the Phase 1 shape', () => {
    const snapshot = parseRevisionSnapshot({
      snapshot_schema_version: 2,
      experiment: {
        title: 'v2',
        status: 'completed',
        objective: null,
        template_id: 'template',
        template_version: 1,
        structured_data: {},
        note_document: []
      },
      attachments: [],
      measurements: [
        {
          id: 'measurement',
          name: 'Response',
          measurement_type: 'other_xy',
          x_label: 'X',
          x_unit: '1',
          y_label: 'Y',
          y_unit: 'AU',
          row_count: 1,
          summary_json: {},
          points_sha256: 'digest',
          import_id: 'import',
          source_attachment_id: 'attachment',
          source_sha256: 'source'
        }
      ]
    });
    expect(snapshot?.snapshot_schema_version).toBe(2);
    expect(snapshot?.measurements?.[0].name).toBe('Response');
  });
});
