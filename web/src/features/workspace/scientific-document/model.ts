import type {
  JsonObject,
  SampleRecord,
  ScientificDocumentV1,
  ScientificOccurrenceDraft
} from '@/lib/domain';

export const SCIENTIFIC_DOCUMENT_VERSION = 1 as const;

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

export function enrichDocument(record: SampleRecord): ScientificEditorDraft {
  const blocks = enrichScientificDocument(record.document, record.occurrences);
  return {
    document: { schema_version: SCIENTIFIC_DOCUMENT_VERSION, blocks },
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
  const ids = occurrences.map((item) => item.occurrence_id);
  if (new Set(ids).size !== ids.length)
    throw new Error('Copied Refs must receive new occurrence IDs');
  return {
    document: { schema_version: SCIENTIFIC_DOCUMENT_VERSION, blocks: canonicalBlocks },
    occurrences
  };
}

export function cloneDocumentForNewRecord(blocks: JsonObject[]): JsonObject[] {
  const copy = structuredClone(blocks);
  const occurrenceMap = new Map<string, string>();
  visit(copy, (node) => {
    if (node.type !== 'processRef' && node.type !== 'objectRef') return;
    const props = node.props as RefProps | undefined;
    const occurrence = parseOccurrencePayload(props?.payload);
    if (!props || !occurrence) return;
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
    if (node.type !== 'objectRef') return;
    const props = node.props as RefProps | undefined;
    const occurrence = parseOccurrencePayload(props?.payload);
    if (!props || !occurrence?.binding) return;
    occurrence.binding.process_occurrence_id =
      occurrenceMap.get(occurrence.binding.process_occurrence_id) ??
      occurrence.binding.process_occurrence_id;
    props.payload = JSON.stringify(occurrence);
  });
  return copy;
}
