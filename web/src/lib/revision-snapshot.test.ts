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
});
