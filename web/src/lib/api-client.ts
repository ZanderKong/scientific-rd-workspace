import type {
  Attachment,
  DataImport,
  DataPayload,
  DataPoint,
  ExperimentContext,
  ImportPreview,
  JsonObject,
  ObjectRelation,
  ObjectRevision,
  ObjectType,
  ProcessComposition,
  ProcessCompositionItem,
  ChangeSet,
  DataRecord,
  ExperimentComparison,
  ExperimentRecord,
  ExecutionRead,
  ProjectContext,
  ProjectRecord,
  ProjectSearch,
  ProjectSummary,
  ResearchObject,
  ResearchObjectKind,
  SampleContext,
  SampleRecord,
  SampleRecordCreatePayload,
  SampleRecordPutPayload,
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
  if (typeof detail === 'string') {
    try {
      const parsed = JSON.parse(detail) as {
        errors?: Array<{ path?: string; message?: string }>;
        code?: string;
      };
      if (parsed.errors?.length)
        return parsed.errors.map((item) => `${item.path ?? '$'}: ${item.message ?? ''}`).join('; ');
      if (parsed.code) return parsed.code;
    } catch {
      return detail;
    }
    return detail;
  }
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
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request timed out. Try again.', 408);
    }
    throw new ApiError('Backend unreachable. Start the API and try again.', 0, error);
  } finally {
    globalThis.clearTimeout(timer);
  }
  const text = await response.text();
  let data: unknown;
  try {
    data = text ? (JSON.parse(text) as unknown) : undefined;
  } catch {
    data = text;
  }
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

export const api = {
  getCapabilities: () => request<Record<string, unknown>>('/capabilities'),
  listTypes: () => request<ObjectType[]>('/object-types'),
  getType: (id: string) => request<ObjectType>(`/object-types/${id}`),
  listObjects: (
    params: {
      kind?: ResearchObjectKind;
      kinds?: ResearchObjectKind[];
      project_scope_id?: string;
      type_key?: string;
      type_id?: string;
      q?: string;
      status?: string;
      include_global?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined) return;
      if (key === 'kinds' && Array.isArray(value)) {
        value.forEach((kind) => query.append(key, String(kind)));
      } else {
        query.set(key, String(value));
      }
    });
    return request<ResearchObject[]>(`/objects${query.size ? `?${query.toString()}` : ''}`);
  },
  getObject: (id: string) => request<ResearchObject>(`/objects/${id}`),
  createObject: (payload: {
    kind: ResearchObjectKind;
    title: string;
    project_scope_id?: string | null;
    status?: string;
    properties_jsonb?: JsonObject;
    usage_schema_jsonb?: JsonObject;
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
        | 'properties_jsonb'
        | 'usage_schema_jsonb'
        | 'content_document'
      >
    >
  ) => request<ResearchObject>(`/objects/${id}`, { ...json(payload), method: 'PATCH' }),
  listRelations: (id: string) => request<ObjectRelation[]>(`/objects/${id}/relations`),
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
    params: { q?: string; kinds?: string[]; status?: string; limit?: number; offset?: number } = {}
  ) => {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    params.kinds?.forEach((kind) => query.append('kinds', kind));
    if (params.status) query.set('status', params.status);
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    if (params.offset !== undefined) query.set('offset', String(params.offset));
    return request<ProjectSearch>(`/projects/${id}/search${query.size ? `?${query}` : ''}`);
  },
  getWorkspaceSummary: () => request<WorkspaceSummary>('/workspace/summary'),
  getComposition: (id: string) => request<ProcessComposition>(`/processes/${id}/composition`),
  putComposition: (id: string, items: ProcessCompositionItem[]) =>
    request<ProcessComposition>(`/processes/${id}/composition`, {
      ...json({ items }),
      method: 'PUT'
    }),
  getSampleRecord: (id: string) => request<SampleRecord>(`/samples/${id}/record`),
  createSampleRecord: (payload: SampleRecordCreatePayload, idempotencyKey?: string) =>
    request<SampleRecord>(
      '/sample-records',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
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
  getExperimentComparison: (id: string, differencesOnly = false) =>
    request<ExperimentComparison>(
      `/experiments/${id}/comparison?differences_only=${differencesOnly}`
    ),
  createDataRecord: (payload: unknown, idempotencyKey?: string) =>
    request<DataRecord>(
      '/data-records',
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  getDataRecord: (id: string) => request<DataRecord>(`/data/${id}/record`),
  createScalarPayload: (id: string, payload: unknown, idempotencyKey?: string) =>
    request<DataPayload>(
      `/data/${id}/payloads/scalar`,
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  createTablePayload: (id: string, payload: unknown, idempotencyKey?: string) =>
    request<DataPayload>(
      `/data/${id}/payloads/table`,
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  createFilePayload: (id: string, payload: unknown, idempotencyKey?: string) =>
    request<DataPayload>(
      `/data/${id}/payloads/file`,
      json(payload, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  startExecution: (id: string, idempotencyKey?: string) =>
    request<ExecutionRead>(
      `/samples/${id}/execution/start`,
      json({}, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  getExecution: (id: string) => request<ExecutionRead>(`/samples/${id}/execution`),
  updateExecution: (id: string, payload: unknown, etag?: string) =>
    request<ExecutionRead>(`/samples/${id}/execution`, {
      ...json(payload, etag ? { 'If-Match': etag } : {}),
      method: 'PUT'
    }),
  completeExecution: (id: string, idempotencyKey?: string) =>
    request<ExecutionRead>(
      `/samples/${id}/execution/complete`,
      json({}, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
  cancelExecution: (id: string, idempotencyKey?: string) =>
    request<ExecutionRead>(
      `/samples/${id}/execution/cancel`,
      json({}, idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    ),
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
  createRelation: (payload: {
    source_object_id: string;
    target_object_id: string;
    relation_type: ObjectRelation['relation_type'];
    role?: string | null;
    properties_jsonb?: JsonObject;
  }) => request<ObjectRelation>('/relations', json(payload)),
  updateRelation: (id: string, payload: { role?: string | null; properties_jsonb?: JsonObject }) =>
    request<ObjectRelation>(`/relations/${id}`, { ...json(payload), method: 'PATCH' }),
  deleteRelation: (id: string) => request<void>(`/relations/${id}`, { method: 'DELETE' }),
  listRevisions: (id: string) => request<ObjectRevision[]>(`/objects/${id}/revisions`),
  createRevision: (id: string, change_note?: string) =>
    request<ObjectRevision>(`/objects/${id}/revisions`, json({ change_note: change_note || null })),
  getRevision: (id: string, number: number) =>
    request<ObjectRevision>(`/objects/${id}/revisions/${number}`),
  listAttachments: (id: string) => request<Attachment[]>(`/objects/${id}/attachments`),
  uploadAttachment: (id: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Attachment>(`/objects/${id}/attachments`, { method: 'POST', body }, 60000);
  },
  deleteAttachment: (id: string) => request<void>(`/attachments/${id}`, { method: 'DELETE' }),
  downloadUrl: (id: string) => `${API_BASE}/attachments/${id}/download`,
  sampleContext: (id: string, depth = 3) =>
    request<SampleContext>(`/samples/${id}/context?depth=${depth}`),
  experimentContext: (id: string) => request<ExperimentContext>(`/experiments/${id}/context`),
  listPayloads: (id: string) => request<DataPayload[]>(`/data/${id}/payloads`),
  getPayload: (id: string) => request<DataPayload>(`/data-payloads/${id}`),
  listPoints: (id: string) => request<DataPoint[]>(`/data-payloads/${id}/points`),
  listImports: (id: string) => request<DataImport[]>(`/data/${id}/imports`),
  previewImport: (id: string, source_attachment_id: string, sheet_name?: string | null) =>
    request<ImportPreview>(
      `/data/${id}/imports/preview`,
      json({ source_attachment_id, sheet_name: sheet_name || null })
    ),
  commitImport: (dataId: string, importId: string, payload: unknown) =>
    request<DataPayload>(
      `/data/${dataId}/imports/${importId}/commit`,
      { ...json(payload), method: 'POST' },
      60000
    )
};
