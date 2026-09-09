import type {
  JsonObject,
  SampleRecord,
  ScientificDocumentV1,
  ScientificSemanticEntry,
  ScientificOccurrenceDraft
} from '@/lib/domain';

export const SCIENTIFIC_DOCUMENT_VERSION = 2 as const;

export type ScientificEditorDraft = {
  document: ScientificDocumentV1;
  baseRecordSha256: string | null;
  generation: number;
};

type RefProps = {
  occurrenceId: string;
  targetId: string;
  label: string;
  payload: string;
};

type PropertyRefProps = {
  occurrenceId: string;
  lineId: string;
};

function visit(value: unknown, callback: (node: JsonObject) => void) {
  if (Array.isArray(value)) {
    value.forEach((item) => visit(item, callback));
    return;
  }
  if (!value || typeof value !== 'object') return;
  const node = value as JsonObject;
  callback(node);
  Object.values(node).forEach((item) => visit(item, callback));
}

function inlineText(content: unknown[]): string {
  return content
    .map((item) => {
      if (typeof item === 'string') return item;
      if (!item || typeof item !== 'object') return '';
      const node = item as JsonObject;
      if (node.type === 'text') return String(node.text ?? '');
      if (node.type === 'processRef' || node.type === 'objectRef' || node.type === 'propertyRef') {
        return `@${String((node.props as JsonObject | undefined)?.label ?? '')}`;
      }
      return '';
    })
    .join('');
}

function contentAfter(content: unknown[], type: string): string {
  let found = false;
  return content
    .flatMap((item) => {
      if (!found && item && typeof item === 'object' && (item as JsonObject).type === type) {
        found = true;
        return [];
      }
      if (!found) return [];
      if (typeof item === 'string') return [item];
      if (item && typeof item === 'object' && (item as JsonObject).type === 'text') {
        return [String((item as JsonObject).text ?? '')];
      }
      return [];
    })
    .join('');
}

export type ParsedProperty = { key: string; rawValue: string; ordinal: number };

export function parsePropertyText(value: string): ParsedProperty[] {
  return value
    .split(/[|｜]/u)
    .map((part) => part.trim())
    .filter(Boolean)
    .flatMap((part, ordinal) => {
      const match = part.match(/[:：]/u);
      const split = match?.index ?? -1;
      if (split <= 0) return [];
      const key = part.slice(0, split).trim();
      const rawValue = part.slice(split + 1).trim();
      return key && rawValue !== '' ? [{ key, rawValue, ordinal }] : [];
    });
}

function fieldId(lineId: string, property: ParsedProperty) {
  return `property_${lineId}_${property.ordinal}`;
}

function collectSemanticEntries(blocks: JsonObject[]): ScientificSemanticEntry[] {
  const entries: ScientificSemanticEntry[] = [];
  visit(blocks, (node) => {
    if (node.type !== 'bulletListItem' && node.type !== 'paragraph') return;
    const value = inlineText(Array.isArray(node.content) ? node.content : []);
    const match = value.match(/^@(data|claim)\s+(.+)$/i);
    if (!match) return;
    entries.push({
      id: typeof node.id === 'string' ? node.id : `semantic_${entries.length + 1}`,
      kind: match[1].toLowerCase() as 'data' | 'claim',
      text: match[2].trim(),
      block_id: typeof node.id === 'string' ? node.id : null
    });
  });
  return entries;
}

function collectNestedProperties(
  blocks: JsonObject[],
  occurrences: Map<string, ScientificOccurrenceDraft>
) {
  const propertyLineIds = new Set<string>();
  occurrences.forEach((occurrence) => {
    const hadFields = Array.isArray(occurrence.field_definitions.fields);
    const existingFields = hadFields ? (occurrence.field_definitions.fields as unknown[]) : [];
    const fields = hadFields
      ? existingFields.filter(
          (field) =>
            !(
              field &&
              typeof field === 'object' &&
              (field as JsonObject).source === 'local' &&
              String((field as JsonObject).key ?? '').startsWith('property_')
            )
        )
      : [];
    if (hadFields) occurrence.field_definitions = { ...occurrence.field_definitions, fields };
    occurrence.values = Object.fromEntries(
      Object.entries(occurrence.values).filter(([key]) => !key.startsWith('property_'))
    );
  });
  const walk = (items: JsonObject[], parentOccurrenceIds: Set<string>, depth: number) => {
    if (depth > 1 && items.length)
      throw new Error('Scientific documents support only two bullet levels');
    items.forEach((block) => {
      const content = Array.isArray(block.content) ? block.content : [];
      const property = content.find(
        (item) => item && typeof item === 'object' && (item as JsonObject).type === 'propertyRef'
      ) as JsonObject | undefined;
      if (property) {
        const props = property.props as PropertyRefProps | undefined;
        if (!props?.occurrenceId || !parentOccurrenceIds.has(props.occurrenceId)) {
          throw new Error(
            'Property row must reference an occurrence declared by its parent bullet'
          );
        }
        const occurrence = occurrences.get(props.occurrenceId);
        if (!occurrence) throw new Error('Property row references a missing occurrence');
        const rawPropertyText = contentAfter(content, 'propertyRef');
        const propertyParts = rawPropertyText
          .split(/[|｜]/u)
          .map((part) => part.trim())
          .filter(Boolean);
        const parsed = parsePropertyText(rawPropertyText);
        if (
          propertyParts.some((part) => {
            const match = part.match(/[:：]/u);
            const separator = match?.index ?? -1;
            return separator <= 0 || part.slice(separator + 1).trim() === '';
          })
        ) {
          throw new Error('Property row contains an incomplete property: value pair');
        }
        if (propertyLineIds.has(props.lineId)) {
          throw new Error('Property rows must have unique stable line IDs');
        }
        propertyLineIds.add(props.lineId);
        const fields = Array.isArray(occurrence.field_definitions.fields)
          ? [...occurrence.field_definitions.fields]
          : [];
        const values = { ...occurrence.values };
        parsed.forEach((item) => {
          const key = fieldId(props.lineId, item);
          if (
            !fields.some(
              (field) => field && typeof field === 'object' && (field as JsonObject).key === key
            )
          ) {
            fields.push({
              key,
              field_id: key,
              source: 'local',
              label: item.key,
              value_type: 'text',
              order: fields.length
            });
          }
          values[key] = { value: item.rawValue, raw_value: item.rawValue };
        });
        occurrence.field_definitions = { ...occurrence.field_definitions, fields };
        occurrence.values = values;
      }
      const childItems = Array.isArray(block.children) ? (block.children as JsonObject[]) : [];
      const declaredIds = new Set(
        content
          .filter(
            (item) =>
              item &&
              typeof item === 'object' &&
              ['processRef', 'objectRef'].includes(String((item as JsonObject).type))
          )
          .map((item) =>
            String(((item as JsonObject).props as JsonObject | undefined)?.occurrenceId ?? '')
          )
          .filter(Boolean)
      );
      if (depth > 0 && declaredIds.size > 0) {
        throw new Error('Child bullets may only reference a parent occurrence');
      }
      if (childItems.length) walk(childItems, declaredIds, depth + 1);
    });
  };
  walk(blocks, new Set(), 0);
}

export function parseOccurrencePayload(value: unknown): ScientificOccurrenceDraft | null {
  if (typeof value !== 'string' || !value) return null;
  try {
    const parsed = JSON.parse(value) as ScientificOccurrenceDraft;
    if (
      parsed &&
      typeof parsed === 'object' &&
      typeof parsed.occurrence_id === 'string' &&
      (parsed.kind === 'process' || parsed.kind === 'object')
    ) {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

export function occurrenceRef(occurrence: ScientificOccurrenceDraft, label: string): JsonObject {
  return {
    type: occurrence.kind === 'process' ? 'processRef' : 'objectRef',
    props: {
      occurrenceId: occurrence.occurrence_id,
      targetId: occurrence.target_id,
      label,
      payload: JSON.stringify(occurrence)
    }
  };
}

export function remapLocalFieldIdentities(
  occurrence: ScientificOccurrenceDraft
): ScientificOccurrenceDraft {
  const next = structuredClone(occurrence);
  const nested = next.field_definitions.fields;
  if (!Array.isArray(nested)) return next;
  const remappedValues: JsonObject = { ...next.values };
  next.field_definitions = {
    ...next.field_definitions,
    fields: nested.map((value) => {
      if (!value || typeof value !== 'object') return value;
      const field = value as JsonObject;
      if (field.source !== 'local') return field;
      const oldKey = String(field.key ?? '');
      const fieldId = crypto.randomUUID();
      const key = `local_${fieldId}`;
      if (oldKey in remappedValues) {
        remappedValues[key] = remappedValues[oldKey];
        delete remappedValues[oldKey];
      }
      return { ...field, key, field_id: fieldId, owner_id: null };
    })
  };
  next.values = remappedValues;
  return next;
}

export function enrichDocument(record: SampleRecord): ScientificEditorDraft {
  const blocks = enrichScientificDocument(record.document, record.occurrences);
  return {
    document: {
      schema_version: SCIENTIFIC_DOCUMENT_VERSION,
      blocks,
      semantic_entries: record.document.semantic_entries ?? []
    },
    baseRecordSha256: record.record_sha256,
    generation: 0
  };
}

export function enrichScientificDocument(
  document: ScientificDocumentV1,
  occurrences: ScientificOccurrenceDraft[]
): JsonObject[] {
  const occurrenceById = new Map(occurrences.map((item) => [item.occurrence_id, item]));
  const blocks = structuredClone(document.blocks);
  let semanticIndex = 0;
  visit(blocks, (node) => {
    if (node.type !== 'bulletListItem' && node.type !== 'paragraph') return;
    const value = inlineText(Array.isArray(node.content) ? node.content : []);
    if (!/^@(data|claim)\s+/i.test(value)) return;
    const entry = document.semantic_entries?.[semanticIndex++];
    if (entry && typeof node.id !== 'string') node.id = entry.id;
  });
  visit(blocks, (node) => {
    if (node.type !== 'processRef' && node.type !== 'objectRef') return;
    const props = node.props as RefProps | undefined;
    const occurrence = props && occurrenceById.get(props.occurrenceId);
    if (!props || !occurrence) return;
    props.targetId = occurrence.target_id;
    props.label = occurrence.label_snapshot ?? props.label;
    props.payload = JSON.stringify({
      occurrence_id: occurrence.occurrence_id,
      kind: occurrence.kind,
      target_id: occurrence.target_id,
      target_revision_id: occurrence.target_revision_id,
      execution_id: occurrence.execution_id,
      process_definition_version_id: occurrence.process_definition_version_id,
      label_snapshot: occurrence.label_snapshot,
      field_definitions: occurrence.field_definitions,
      values: occurrence.values,
      status: occurrence.status,
      binding: occurrence.binding
    } satisfies ScientificOccurrenceDraft);
  });
  return blocks;
}

export function canonicalizeDocument(blocks: JsonObject[]): {
  document: ScientificDocumentV1;
  occurrences: ScientificOccurrenceDraft[];
} {
  const canonicalBlocks = structuredClone(blocks);
  const occurrences: ScientificOccurrenceDraft[] = [];
  visit(canonicalBlocks, (node) => {
    if (node.type !== 'processRef' && node.type !== 'objectRef') return;
    const props = node.props as RefProps | undefined;
    const occurrence = parseOccurrencePayload(props?.payload);
    if (!props || !occurrence) throw new Error('Ref is missing a valid scientific occurrence');
    if (
      occurrence.occurrence_id !== props.occurrenceId ||
      occurrence.target_id !== props.targetId
    ) {
      throw new Error('Ref identity and payload do not match');
    }
    occurrences.push(occurrence);
    props.payload = '';
  });
  const occurrenceById = new Map(occurrences.map((item) => [item.occurrence_id, item]));
  collectNestedProperties(canonicalBlocks, occurrenceById);
  const ids = occurrences.map((item) => item.occurrence_id);
  if (new Set(ids).size !== ids.length)
    throw new Error('Copied Refs must receive new occurrence IDs');
  return {
    document: {
      schema_version: SCIENTIFIC_DOCUMENT_VERSION,
      blocks: canonicalBlocks,
      semantic_entries: collectSemanticEntries(canonicalBlocks)
    },
    occurrences
  };
}

export function cloneDocumentForNewRecord(blocks: JsonObject[]): JsonObject[] {
  const copy = structuredClone(blocks);
  const occurrenceMap = new Map<string, string>();
  const propertyLineMap = new Map<string, string>();
  visit(copy, (node) => {
    if (node.type !== 'propertyRef') return;
    const props = node.props as PropertyRefProps | undefined;
    if (!props?.lineId) return;
    const nextLineId = crypto.randomUUID();
    propertyLineMap.set(props.lineId, nextLineId);
    props.lineId = nextLineId;
  });
  visit(copy, (node) => {
    if (node.type !== 'processRef' && node.type !== 'objectRef') return;
    const props = node.props as RefProps | undefined;
    let occurrence = parseOccurrencePayload(props?.payload);
    if (!props || !occurrence) return;
    const remapped = structuredClone(occurrence);
    const remappedValues: JsonObject = { ...remapped.values };
    const fields = Array.isArray(remapped.field_definitions.fields)
      ? remapped.field_definitions.fields
      : [];
    remapped.field_definitions = {
      ...remapped.field_definitions,
      fields: fields.map((field) => {
        if (!field || typeof field !== 'object' || field.source !== 'local') return field;
        const oldKey = String(field.key ?? '');
        const propertyMatch = oldKey.match(/^property_(.+)_(\d+)$/);
        const oldLineId = propertyMatch?.[1];
        const nextFieldId =
          oldLineId && propertyLineMap.has(oldLineId)
            ? `property_${propertyLineMap.get(oldLineId)}_${propertyMatch?.[2]}`
            : crypto.randomUUID();
        const nextKey =
          oldLineId && propertyLineMap.has(oldLineId) ? nextFieldId : `local_${nextFieldId}`;
        if (oldKey in remappedValues) {
          remappedValues[nextKey] = remappedValues[oldKey];
          delete remappedValues[oldKey];
        }
        return { ...field, key: nextKey, field_id: nextFieldId, owner_id: null };
      })
    };
    remapped.values = remappedValues;
    occurrence = remapped;
    const nextId = crypto.randomUUID();
    occurrenceMap.set(occurrence.occurrence_id, nextId);
    occurrence.occurrence_id = nextId;
    occurrence.execution_id = null;
    occurrence.status = 'recorded';
    if (occurrence.binding?.direction === 'output') occurrence.binding = null;
    else if (occurrence.binding) occurrence.binding.binding_id = null;
    props.occurrenceId = nextId;
    props.payload = JSON.stringify(occurrence);
  });
  visit(copy, (node) => {
    if (node.type !== 'propertyRef') return;
    const props = node.props as PropertyRefProps | undefined;
    if (!props) return;
    const nextOccurrenceId = occurrenceMap.get(props.occurrenceId);
    if (nextOccurrenceId) props.occurrenceId = nextOccurrenceId;
  });
  visit(copy, (node) => {
    if (node.type !== 'objectRef') return;
    const props = node.props as RefProps | undefined;
    const occurrence = parseOccurrencePayload(props?.payload);
    if (!props || !occurrence?.binding) return;
    const processOccurrenceId = occurrenceMap.get(occurrence.binding.process_occurrence_id);
    if (!processOccurrenceId) occurrence.binding = null;
    else occurrence.binding.process_occurrence_id = processOccurrenceId;
    props.payload = JSON.stringify(occurrence);
  });
  visit(copy, (node) => {
    if (node.type === 'propertyRef') return;
    if (node.type !== 'bulletListItem' && node.type !== 'paragraph') return;
    const content = Array.isArray(node.content) ? node.content : [];
    const textValue = inlineText(content);
    if (/^@(data|claim)\s+/i.test(textValue) && typeof node.id === 'string') {
      node.id = crypto.randomUUID();
    }
  });
  return copy;
}
