import type {
  Attachment,
  Experiment,
  ExperimentTemplate,
  JsonObject,
  Project,
  Revision
} from './domain';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1').replace(
  /\/$/,
  ''
);

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, cache: 'no-store' });
  } catch {
    throw new ApiError('Backend unreachable. Start the API and try again.', 0);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof body.detail === 'string') message = body.detail;
      if (Array.isArray(body.detail))
        message = body.detail
          .map((item) => item.msg)
          .filter(Boolean)
          .join('; ');
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listProjects: () => request<Project[]>('/projects'),
  createProject: (payload: Pick<Project, 'title' | 'description' | 'status'>) =>
    request<Project>('/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  updateProject: (
    id: string,
    payload: Partial<Pick<Project, 'title' | 'description' | 'status'>>
  ) =>
    request<Project>(`/projects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  listProjectExperiments: (projectId: string) =>
    request<Experiment[]>(`/projects/${projectId}/experiments`),
  listExperiments: () => request<Experiment[]>('/experiments'),
  createExperiment: (
    projectId: string,
    payload: {
      title: string;
      template_id: string;
      status?: string;
      objective?: string;
      structured_data?: JsonObject;
      note_document?: Array<JsonObject>;
    }
  ) =>
    request<Experiment>(`/projects/${projectId}/experiments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  getExperiment: (id: string) => request<Experiment>(`/experiments/${id}`),
  updateExperiment: (
    id: string,
    payload: Partial<
      Pick<Experiment, 'title' | 'status' | 'objective' | 'structured_data' | 'note_document'>
    >
  ) =>
    request<Experiment>(`/experiments/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  cloneExperiment: (id: string, new_title: string) =>
    request<Experiment>(`/experiments/${id}/clone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_title, copy_note: true, copy_structured_data: true })
    }),
  listTemplates: () => request<ExperimentTemplate[]>('/experiment-templates'),
  getTemplate: (id: string) => request<ExperimentTemplate>(`/experiment-templates/${id}`),
  listAttachments: (id: string) => request<Attachment[]>(`/experiments/${id}/attachments`),
  uploadAttachment: (id: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Attachment>(`/experiments/${id}/attachments`, { method: 'POST', body });
  },
  deleteAttachment: (id: string) => request<void>(`/attachments/${id}`, { method: 'DELETE' }),
  listRevisions: (id: string) => request<Revision[]>(`/experiments/${id}/revisions`),
  createRevision: (id: string, change_note?: string) =>
    request<Revision>(`/experiments/${id}/revisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ change_note: change_note || null })
    }),
  downloadUrl: (id: string) => `${API_BASE}/attachments/${id}/download`
};
