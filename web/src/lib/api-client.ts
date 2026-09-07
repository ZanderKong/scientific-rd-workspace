import type {
  Asset,
  ChangeSet,
  ClaimRecord,
  DataImport,
  DataDraft,
  DataRecord,
  DataRepresentation,
  ExperimentRecord,
  ExperimentReferenceDraft,
  JsonObject,
  ObjectRelation,
  ObjectRevision,
  ObjectType,
  ProcessDefinition,
  ProcessExecution,
  ProcessExecutionDraft,
  ProjectContext,
  ProjectRecord,
  ProjectSearch,
  ProjectSummary,
  RecordTableResult,
  RelationType,
  ResearchObject,
  ResearchObjectKind,
  SampleRecord,
  SampleRecordCreatePayload,
  SampleRecordPutPayload,
  ViewRecord,
  WorkspaceSummary
} from './domain';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1').replace(
  /\/$/,
  ''
);

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
  if (detail && typeof detail === 'object' && 'error' in detail) {
    const error = detail.error;
    if (error && typeof error === 'object' && 'message' in error) return String(error.message);
  }
  return fallback;
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 15000
): Promise<T> {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  if (init.signal) init.signal.addEventListener('abort', () => controller.abort(), { once: true });
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError')
      throw new ApiError('Request timed out. Try again.', 408);
    throw new ApiError('Backend unreachable. Start the API and try again.', 0, error);
  } finally {
    globalThis.clearTimeout(timer);
  }
  const text = await response.text();
  const data: unknown = text ? JSON.parse(text) : undefined;
  if (!response.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? data.detail : data;
    throw new ApiError(
      errorMessage(detail, `Request failed (${response.status})`),
      response.status,
      detail
    );
  }
  return data as T;
}

const json = (body: unknown, headers: Record<string, string> = {}): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json', ...headers },
  body: JSON.stringify(body)
});

function queryString(params: Record<string, string | number | boolean | string[] | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
    else query.set(key, String(value));
  }
  return query.size ? `?${query}` : '';
}

export const api = {
  getCapabilities: () => request<Record<string, unknown>>('/capabilities'),
  listTypes: () => request<ObjectType[]>('/object-types'),
  getType: (id: string) => request<ObjectType>(`/object-types/${id}`),
  listObjects: (
    params: {
      kind?: ResearchObjectKind;
      kinds?: ResearchObjectKind[];
      tag?: string;
      project_scope_id?: string;
      q?: string;
      status?: string;
      include_global?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ) => request<ResearchObject[]>(`/objects${queryString(params)}`),
  getObject: (id: string) => request<ResearchObject>(`/objects/${id}`),
  deleteObject: (id: string) => request<void>(`/objects/${id}`, { method: 'DELETE' }),
  createObject: (payload: {
    kind: ResearchObjectKind;
    title: string;
    code?: string | null;
    project_scope_id?: string | null;
    status?: string;
    tags?: string[];
    properties_jsonb?: JsonObject;
    process_field_definitions?: JsonObject;
    content_document?: JsonObject[];
  }) => request<ResearchObject>('/objects', json(payload)),
  updateObject: (
    id: string,
    payload: Partial<
      Pick<
        ResearchObject,
        | 'title'
        | 'status'
        | 'project_scope_id'
        | 'tags'
        | 'properties_jsonb'
        | 'process_field_definitions'
        | 'content_document'
      >
    >,
    etag: string
  ) =>
    request<ResearchObject>(`/objects/${id}`, {
      ...json(payload, { 'If-Match': etag }),
      method: 'PATCH'
    }),
  listRelations: (id: string) => request<ObjectRelation[]>(`/objects/${id}/relations`),
  createRelation: (payload: {
    source_object_id: string;
    target_object_id: string;
    relation_type: RelationType;
    role?: string | null;
    properties_jsonb?: JsonObject;
  }) => request<ObjectRelation>('/relations', json(payload)),
  updateRelation: (id: string, payload: { role?: string | null; properties_jsonb?: JsonObject }) =>
    request<ObjectRelation>(`/relations/${id}`, { ...json(payload), method: 'PATCH' }),
  deleteRelation: (id: string) => request<void>(`/relations/${id}`, { method: 'DELETE' }),
  listRevisions: (id: string) => request<ObjectRevision[]>(`/objects/${id}/revisions`),
  createRevision: (id: string, change_note?: string) =>
    request<ObjectRevision>(`/objects/${id}/revisions`, json({ change_note: change_note || null })),
  getProjectSummary: (id: string) => request<ProjectSummary>(`/projects/${id}/summary`),
  createProjectRecord: (payload: unknown, idempotencyKey?: string) =>
    request<ProjectRecord>(
      '/project-records',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  getProjectRecord: (id: string) => request<ProjectRecord>(`/projects/${id}/record`),
  updateProjectRecord: (id: string, payload: unknown, etag?: string) =>
    request<ProjectRecord>(`/projects/${id}/record`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),
  getProjectContext: (id: string) => request<ProjectContext>(`/projects/${id}/context`),
  searchProject: (
    id: string,
    params: {
      q?: string;
      kinds?: ResearchObjectKind[];
      status?: string;
      limit?: number;
      offset?: number;
    } = {}
  ) => request<ProjectSearch>(`/projects/${id}/search${queryString(params)}`),
  getWorkspaceSummary: () => request<WorkspaceSummary>('/workspace/summary'),

  listProcessDefinitions: (
    params: { project_scope_id?: string; q?: string; limit?: number; offset?: number } = {}
  ) => request<ProcessDefinition[]>(`/process-definitions${queryString(params)}`),
  getProcessDefinition: (id: string) => request<ProcessDefinition>(`/process-definitions/${id}`),
  createProcessDefinition: (payload: unknown) =>
    request<ProcessDefinition>('/process-definitions', json(payload)),
  createProcessDefinitionVersion: (id: string, payload: unknown) =>
    request<unknown>(`/process-definitions/${id}/versions`, json(payload)),
  createProcessExecution: (payload: ProcessExecutionDraft, idempotencyKey?: string) =>
    request<ProcessExecution>(
      '/process-executions',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  getProcessExecution: (id: string) => request<ProcessExecution>(`/process-executions/${id}`),
  updateProcessExecution: (
    id: string,
    payload: Partial<ProcessExecutionDraft> & { change_note?: string },
    etag?: string
  ) =>
    request<ProcessExecution>(`/process-executions/${id}`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),
  listObjectExecutions: (id: string) =>
    request<ProcessExecution[]>(`/objects/${id}/process-executions`),

  getSampleRecord: (id: string) => request<SampleRecord>(`/samples/${id}/record`),
  getSampleRecordRevision: (id: string, revision: number) =>
    request<SampleRecord>(`/samples/${id}/record/revisions/${revision}`),
  createSampleRecord: (payload: SampleRecordCreatePayload, idempotencyKey?: string) =>
    request<SampleRecord>(
      '/sample-records',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  createSampleBatch: (
    payload: {
      project_scope_id: string;
      rows: Array<{ client_row_id: string; record: SampleRecordCreatePayload }>;
    },
    idempotencyKey: string
  ) =>
    request<{ rows: Array<{ client_row_id: string; record: SampleRecord }> }>(
      '/sample-records/batch',
      json(payload, { 'Idempotency-Key': idempotencyKey })
    ),
  updateSampleRecord: (id: string, payload: SampleRecordPutPayload, etag?: string) =>
    request<SampleRecord>(`/samples/${id}/record`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),

  createExperimentRecord: (payload: unknown, idempotencyKey?: string) =>
    request<ExperimentRecord>(
      '/experiment-records',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  getExperimentRecord: (id: string) => request<ExperimentRecord>(`/experiments/${id}/record`),
  updateExperimentRecord: (id: string, payload: unknown, etag?: string) =>
    request<ExperimentRecord>(`/experiments/${id}/record`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),
  patchExperimentMetadata: (id: string, payload: unknown, etag: string) =>
    request<ExperimentRecord>(`/experiments/${id}/metadata`, {
      ...json(payload, { 'If-Match': etag }),
      method: 'PATCH'
    }),
  addExperimentReference: (id: string, payload: unknown, etag: string) =>
    request<ExperimentRecord>(`/experiments/${id}/references`, {
      ...json(payload, { 'If-Match': etag })
    }),
  removeExperimentReference: (id: string, relationId: string, etag: string) =>
    request<ExperimentRecord>(`/experiments/${id}/references/${relationId}`, {
      method: 'DELETE',
      headers: { 'If-Match': etag }
    }),
  reorderExperimentReferences: (id: string, relationIds: string[], etag: string) =>
    request<ExperimentRecord>(`/experiments/${id}/reference-order`, {
      ...json({ relation_ids: relationIds }, { 'If-Match': etag }),
      method: 'PUT'
    }),
  experimentReferencePayload: (
    target_id: string,
    role?: string,
    note?: string
  ): ExperimentReferenceDraft => ({ target_id, role, note }),

  createDataRecord: (payload: unknown, idempotencyKey?: string) =>
    request<DataRecord>(
      '/data-records',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  getDataRecord: (id: string) => request<DataRecord>(`/data/${id}/record`),
  queryRecordTable: (payload: unknown) =>
    request<RecordTableResult>('/record-tables/query', json(payload)),
  beginDataDraft: (payload: unknown, idempotencyKey: string) =>
    request<DataDraft>('/data-drafts', json(payload, { 'Idempotency-Key': idempotencyKey })),
  getDataDraft: (id: string) => request<DataDraft>(`/data-drafts/${id}`),
  updateDataDraft: (id: string, payload: unknown) =>
    request<DataDraft>(`/data-drafts/${id}`, { ...json(payload), method: 'PUT' }),
  attachDataDraftAsset: (id: string, clientAttachmentId: string, assetId: string) =>
    request<DataDraft>(
      `/data-drafts/${id}/attachments`,
      json({ client_attachment_id: clientAttachmentId, asset_id: assetId })
    ),
  removeDataDraftAsset: (id: string, clientAttachmentId: string) =>
    request<DataDraft>(`/data-drafts/${id}/attachments/${encodeURIComponent(clientAttachmentId)}`, {
      method: 'DELETE'
    }),
  finalizeDataDraft: (id: string, recordSha256: string, idempotencyKey: string) =>
    request<DataRecord>(
      `/data-drafts/${id}/finalize`,
      json({ base_record_sha256: recordSha256 }, { 'Idempotency-Key': idempotencyKey })
    ),
  updateDataRecord: (id: string, payload: unknown, etag?: string) =>
    request<DataRecord>(`/data/${id}/record`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),
  createRepresentation: (id: string, payload: unknown) =>
    request<DataRepresentation>(`/data/${id}/representations`, json(payload)),
  listRepresentations: (id: string) => request<DataRepresentation[]>(`/data/${id}/representations`),
  getRepresentation: (dataId: string, representationId: string) =>
    request<DataRepresentation>(`/data/${dataId}/representations/${representationId}`),
  setDataRelations: (id: string, subjects: string[], derived_from: string[]) =>
    request<void>(`/data/${id}/relations${queryString({ subjects, derived_from })}`, {
      method: 'PUT'
    }),
  listImports: (id: string) => request<DataImport[]>(`/data/${id}/imports`),
  previewImport: (id: string, source_asset_id: string, sheet_name?: string | null) =>
    request<DataImport>(
      `/data/${id}/imports/preview`,
      json({ source_asset_id, sheet_name: sheet_name || null })
    ),
  commitImport: (dataId: string, importId: string, payload: unknown) =>
    request<DataRepresentation>(
      `/data/${dataId}/imports/${importId}/commit`,
      { ...json(payload), method: 'POST' },
      60000
    ),

  createView: (payload: unknown) => request<ViewRecord>('/views', json(payload)),
  getView: (id: string) => request<ViewRecord>(`/views/${id}`),
  updateView: (id: string, payload: unknown, etag?: string) =>
    request<ViewRecord>(`/views/${id}`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),
  listViewRevisions: (id: string) => request<unknown[]>(`/views/${id}/revisions`),
  createClaim: (payload: unknown) => request<ClaimRecord>('/claims', json(payload)),
  listClaimsByReference: (id: string) => request<ClaimRecord[]>(`/claims/by-reference/${id}`),
  getClaim: (id: string) => request<ClaimRecord>(`/claims/${id}`),
  updateClaim: (id: string, payload: unknown, etag?: string) =>
    request<ClaimRecord>(`/claims/${id}`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),

  listAssets: (id: string) => request<Asset[]>(`/objects/${id}/assets`),
  uploadAsset: (id: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Asset>(`/objects/${id}/assets`, { method: 'POST', body }, 60000);
  },
  deleteAsset: (id: string) => request<void>(`/assets/${id}`, { method: 'DELETE' }),
  downloadUrl: (id: string) => `${API_BASE}/assets/${id}/download`,

  listChangeSets: (projectId?: string) =>
    request<ChangeSet[]>(`/change-sets${projectId ? `?project_scope_id=${projectId}` : ''}`),
  getChangeSet: (id: string) => request<ChangeSet>(`/change-sets/${id}`),
  proposeChangeSet: (payload: unknown, idempotencyKey?: string) =>
    request<ChangeSet>(
      '/change-sets/propose',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  reviewChangeSet: (id: string, payload: unknown) =>
    request<ChangeSet>(`/change-sets/${id}/review`, json(payload)),
  applyChangeSet: (id: string) => request<ChangeSet>(`/change-sets/${id}/apply`, { method: 'POST' })
};
