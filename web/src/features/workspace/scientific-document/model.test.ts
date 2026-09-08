import { describe, expect, it, vi } from 'vitest';
import type { JsonObject, ScientificOccurrenceDraft } from '@/lib/domain';
import {
  canonicalizeDocument,
  cloneDocumentForNewRecord,
  occurrenceRef,
  parseOccurrencePayload
} from './model';

function paragraph(...content: JsonObject[]): JsonObject[] {
  return [{ type: 'paragraph', content }];
}

describe('scientific document codec', () => {
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
