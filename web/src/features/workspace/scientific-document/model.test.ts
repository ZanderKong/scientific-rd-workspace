import { describe, expect, it, vi } from 'vitest';
import type { JsonObject, ScientificOccurrenceDraft } from '@/lib/domain';
import {
  canonicalizeDocument,
  cloneDocumentForNewRecord,
  occurrenceRef,
  parsePropertyText,
  parseOccurrencePayload
} from './model';

function paragraph(...content: JsonObject[]): JsonObject[] {
  return [{ type: 'paragraph', content }];
}

describe('scientific document codec', () => {
  it('parses full-width property syntax and projects a child row onto its parent occurrence', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'parent-occurrence',
      kind: 'object',
      target_id: 'water',
      field_definitions: {},
      values: {},
      status: 'recorded'
    };
    const blocks: JsonObject[] = [
      {
        type: 'bulletListItem',
        content: [occurrenceRef(occurrence, '水')],
        children: [
          {
            type: 'bulletListItem',
            content: [
              {
                type: 'propertyRef',
                props: { occurrenceId: occurrence.occurrence_id, lineId: 'line-1', label: '水' }
              },
              { type: 'text', text: '｜温度：60 ℃｜添加量: 0' }
            ]
          }
        ]
      }
    ];
    const parsed = parsePropertyText('｜温度：60 ℃｜添加量: 0');
    expect(parsed.map((item) => item.rawValue)).toEqual(['60 ℃', '0']);
    const result = canonicalizeDocument(blocks);
    expect(result.document.schema_version).toBe(2);
    expect(result.occurrences[0].values).toMatchObject({
      'property_line-1_0': { value: '60 ℃', raw_value: '60 ℃' },
      'property_line-1_1': { value: '0', raw_value: '0' }
    });
  });

  it('preserves punctuation inside the raw property value', () => {
    expect(parsePropertyText('比例：1：10｜备注: A:B').map((item) => item.rawValue)).toEqual([
      '1：10',
      'A:B'
    ]);
  });

  it('rejects a property row that does not belong to its parent bullet', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'parent-occurrence',
      kind: 'object',
      target_id: 'water',
      field_definitions: {},
      values: {}
    };
    expect(() =>
      canonicalizeDocument([
        {
          type: 'bulletListItem',
          content: [occurrenceRef(occurrence, '水')],
          children: [
            {
              type: 'bulletListItem',
              content: [
                {
                  type: 'propertyRef',
                  props: { occurrenceId: 'other', lineId: 'line', label: '水' }
                },
                { type: 'text', text: '｜温度: 60 ℃' }
              ]
            }
          ]
        }
      ])
    ).toThrow('parent bullet');
  });

  it('reports an incomplete property pair instead of silently dropping it', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'parent-occurrence',
      kind: 'object',
      target_id: 'water',
      field_definitions: {},
      values: {}
    };
    expect(() =>
      canonicalizeDocument([
        {
          type: 'bulletListItem',
          content: [occurrenceRef(occurrence, '水')],
          children: [
            {
              type: 'bulletListItem',
              content: [
                {
                  type: 'propertyRef',
                  props: { occurrenceId: 'parent-occurrence', lineId: 'line', label: '水' }
                },
                { type: 'text', text: '｜温度' }
              ]
            }
          ]
        }
      ])
    ).toThrow('incomplete property');
  });

  it('removes projected property values when the child row is deleted', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'parent-occurrence',
      kind: 'object',
      target_id: 'water',
      field_definitions: {
        fields: [
          {
            key: 'property_old_line_0',
            field_id: 'property_old_line_0',
            source: 'local',
            label: '温度',
            value_type: 'text'
          },
          { key: 'template_note', label: '备注', source: 'template', value_type: 'text' }
        ]
      },
      values: {
        property_old_line_0: { value: '60 ℃', raw_value: '60 ℃' },
        template_note: { value: 'keep' }
      }
    };
    const result = canonicalizeDocument([
      { type: 'bulletListItem', content: [occurrenceRef(occurrence, '水')], children: [] }
    ]);
    expect(result.occurrences[0].values).toEqual({ template_note: { value: 'keep' } });
    expect(result.occurrences[0].field_definitions.fields).toEqual([
      { key: 'template_note', label: '备注', source: 'template', value_type: 'text' }
    ]);
  });

  it('rejects duplicate property line identities instead of merging them', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'parent-occurrence',
      kind: 'object',
      target_id: 'water',
      field_definitions: {},
      values: {}
    };
    const child = {
      type: 'bulletListItem',
      content: [
        {
          type: 'propertyRef',
          props: { occurrenceId: occurrence.occurrence_id, lineId: 'same-line', label: '水' }
        },
        { type: 'text', text: '｜温度: 60 ℃' }
      ]
    };
    expect(() =>
      canonicalizeDocument([
        {
          type: 'bulletListItem',
          content: [occurrenceRef(occurrence, '水')],
          children: [child, structuredClone(child)]
        }
      ])
    ).toThrow('unique stable line IDs');
  });

  it('remaps property line identities when copying a record', () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn().mockReturnValueOnce('line-new').mockReturnValueOnce('occurrence-new')
    });
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'occurrence-old',
      kind: 'object',
      target_id: 'water',
      field_definitions: {
        fields: [
          {
            key: 'property_line-old_0',
            field_id: 'property_line-old_0',
            source: 'local',
            label: '温度',
            value_type: 'text'
          }
        ]
      },
      values: { 'property_line-old_0': { value: '60 ℃', raw_value: '60 ℃' } }
    };
    const copied = cloneDocumentForNewRecord([
      {
        type: 'bulletListItem',
        content: [occurrenceRef(occurrence, '水')],
        children: [
          {
            type: 'bulletListItem',
            content: [
              {
                type: 'propertyRef',
                props: { occurrenceId: 'occurrence-old', lineId: 'line-old', label: '水' }
              },
              { type: 'text', text: '｜温度: 60 ℃' }
            ]
          }
        ]
      }
    ]);
    const ref = (copied[0].content as JsonObject[])[0];
    const cloned = parseOccurrencePayload((ref.props as JsonObject).payload);
    expect(cloned?.field_definitions.fields).toEqual([
      expect.objectContaining({ key: 'property_line-new_0' })
    ]);
    expect(cloned?.values).toMatchObject({ 'property_line-new_0': { value: '60 ℃' } });
    const property = ((copied[0].children as JsonObject[])[0].content as JsonObject[])[0];
    expect((property.props as JsonObject).occurrenceId).toBe('occurrence-new');
    vi.unstubAllGlobals();
  });

  it('keeps values in the occurrence write set and strips them from canonical nodes', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: '11111111-1111-4111-8111-111111111111',
      kind: 'process',
      target_id: '22222222-2222-4222-8222-222222222222',
      process_definition_version_id: '33333333-3333-4333-8333-333333333333',
      label_snapshot: '搅拌',
      field_definitions: { temperature: { label: '温度', value_type: 'number' } },
      values: { temperature: '60' },
      status: 'recorded'
    };
    const result = canonicalizeDocument(paragraph(occurrenceRef(occurrence, '搅拌')));
    expect(result.occurrences).toEqual([occurrence]);
    expect((result.document.blocks[0].content as JsonObject[])[0]).toMatchObject({
      props: { occurrenceId: occurrence.occurrence_id, targetId: occurrence.target_id, payload: '' }
    });
  });

  it('remaps copied process, object, binding and execution identities', () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn().mockReturnValueOnce('process-new').mockReturnValueOnce('object-new')
    });
    const process: ScientificOccurrenceDraft = {
      occurrence_id: 'process-old',
      kind: 'process',
      target_id: 'definition',
      execution_id: 'execution-old',
      field_definitions: {},
      values: {},
      status: 'completed'
    };
    const object: ScientificOccurrenceDraft = {
      occurrence_id: 'object-old',
      kind: 'object',
      target_id: 'object',
      field_definitions: {},
      values: {},
      binding: {
        process_occurrence_id: 'process-old',
        binding_id: 'binding-old',
        direction: 'input'
      }
    };
    const cloned = cloneDocumentForNewRecord(
      paragraph(occurrenceRef(process, 'Process'), occurrenceRef(object, 'Object'))
    );
    const refs = cloned[0].content as JsonObject[];
    const clonedProcess = parseOccurrencePayload((refs[0].props as JsonObject).payload);
    const clonedObject = parseOccurrencePayload((refs[1].props as JsonObject).payload);
    expect(clonedProcess).toMatchObject({
      occurrence_id: 'process-new',
      execution_id: null,
      status: 'recorded'
    });
    expect(clonedObject?.binding).toMatchObject({
      process_occurrence_id: 'process-new',
      binding_id: null
    });
    vi.unstubAllGlobals();
  });

  it('rejects duplicate occurrence identities', () => {
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'same',
      kind: 'object',
      target_id: 'object',
      field_definitions: {},
      values: {}
    };
    expect(() =>
      canonicalizeDocument(
        paragraph(occurrenceRef(occurrence, 'A'), occurrenceRef(occurrence, 'B'))
      )
    ).toThrow('Copied Refs');
  });

  it('drops output bindings when creating a fresh record copy', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'object-new' });
    const output: ScientificOccurrenceDraft = {
      occurrence_id: 'object-old',
      kind: 'object',
      target_id: 'object',
      field_definitions: {},
      values: {},
      binding: {
        process_occurrence_id: 'process-old',
        binding_id: 'binding-old',
        direction: 'output'
      }
    };
    const cloned = cloneDocumentForNewRecord(paragraph(occurrenceRef(output, 'Output')));
    const ref = (cloned[0].content as JsonObject[])[0];
    expect(parseOccurrencePayload((ref.props as JsonObject).payload)?.binding).toBeNull();
    vi.unstubAllGlobals();
  });

  it('allocates fresh local field identities and preserves their values in a copy', () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn().mockReturnValueOnce('field-new').mockReturnValueOnce('occurrence-new')
    });
    const occurrence: ScientificOccurrenceDraft = {
      occurrence_id: 'occurrence-old',
      kind: 'object',
      target_id: 'object',
      field_definitions: {
        fields: [
          {
            key: 'local_field-old',
            field_id: 'field-old',
            source: 'local',
            label: 'Local',
            value_type: 'text'
          }
        ]
      },
      values: { 'local_field-old': { value: 'kept' } }
    };
    const cloned = cloneDocumentForNewRecord(paragraph(occurrenceRef(occurrence, 'Object')));
    const copied = parseOccurrencePayload(
      ((cloned[0].content as JsonObject[])[0].props as JsonObject).payload
    );
    expect(copied).toMatchObject({
      occurrence_id: 'occurrence-new',
      field_definitions: {
        fields: [{ key: 'local_field-new', field_id: 'field-new', source: 'local' }]
      },
      values: { 'local_field-new': { value: 'kept' } }
    });
    vi.unstubAllGlobals();
  });
});
