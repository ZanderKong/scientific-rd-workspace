import type {
  ExperimentStatus,
  JsonObject,
  RevisionAttachmentSnapshot,
  RevisionSnapshot
} from './domain';

const EXPERIMENT_STATUSES = new Set<ExperimentStatus>([
  'draft',
  'planned',
  'running',
  'completed',
  'cancelled'
]);

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isAttachment(value: unknown): value is RevisionAttachmentSnapshot {
  if (!isObject(value)) return false;
  return (
    typeof value.id === 'string' &&
    typeof value.original_filename === 'string' &&
    (typeof value.content_type === 'string' || value.content_type === null) &&
    typeof value.size_bytes === 'number' &&
    typeof value.sha256 === 'string'
  );
}

export function parseRevisionSnapshot(value: unknown): RevisionSnapshot | null {
  if (!isObject(value) || !isObject(value.experiment) || !Array.isArray(value.attachments)) {
    return null;
  }
  const experiment = value.experiment;
  if (
    typeof experiment.title !== 'string' ||
    typeof experiment.status !== 'string' ||
    !EXPERIMENT_STATUSES.has(experiment.status as ExperimentStatus) ||
    (typeof experiment.objective !== 'string' && experiment.objective !== null) ||
    typeof experiment.template_id !== 'string' ||
    typeof experiment.template_version !== 'number' ||
    !isObject(experiment.structured_data) ||
    !Array.isArray(experiment.note_document) ||
    !experiment.note_document.every(isObject) ||
    !value.attachments.every(isAttachment)
  ) {
    return null;
  }
  return {
    snapshot_schema_version:
      typeof value.snapshot_schema_version === 'number' ? value.snapshot_schema_version : 1,
    experiment: {
      title: experiment.title,
      status: experiment.status as ExperimentStatus,
      objective: experiment.objective,
      template_id: experiment.template_id,
      template_version: experiment.template_version,
      structured_data: experiment.structured_data,
      note_document: experiment.note_document
    },
    attachments: value.attachments,
    measurements: Array.isArray(value.measurements)
      ? value.measurements
          .filter(isObject)
          .map((item) => item as NonNullable<RevisionSnapshot['measurements']>[number])
      : undefined,
    literature_links: Array.isArray(value.literature_links)
      ? value.literature_links
          .filter(isObject)
          .map((item) => item as NonNullable<RevisionSnapshot['literature_links']>[number])
      : undefined,
    evidence: Array.isArray(value.evidence)
      ? value.evidence
          .filter(isObject)
          .map((item) => item as NonNullable<RevisionSnapshot['evidence']>[number])
      : undefined
  };
}
