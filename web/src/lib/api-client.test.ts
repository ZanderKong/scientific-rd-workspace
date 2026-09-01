import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api-client';

afterEach(() => vi.restoreAllMocks());

describe('api client', () => {
  it('parses structured API errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: [{ msg: 'title is required' }] }), { status: 422 })
        )
    );
    await expect(api.listProjects()).rejects.toEqual(
      expect.objectContaining({
        message: 'title is required',
        status: 422
      } satisfies Partial<ApiError>)
    );
  });

  it('creates a project with the API base path', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ id: '1', code: 'PRJ-001' }), { status: 201 })
      );
    vi.stubGlobal('fetch', fetchMock);
    await api.createProject({ title: 'New project', description: '', status: 'active' });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/projects',
      expect.objectContaining({ method: 'POST' })
    );
  });
});
