import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, API_REQUEST_TIMEOUT_MS, ApiError, request } from './api-client';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

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

  it('retains structured import diagnostics on ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              code: 'non_numeric_value',
              message: '1 invalid cell',
              errors: [{ row: 3, column: 'y', message: 'Expected a finite number.' }]
            }
          }),
          { status: 422 }
        )
      )
    );
    await expect(api.listProjects()).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        details: expect.objectContaining({ code: 'non_numeric_value' })
      })
    );
  });

  it('reports network failures without retrying writes', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('connection refused'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      api.createProject({ title: 'New project', description: '', status: 'active' })
    ).rejects.toEqual(
      expect.objectContaining({
        message: 'Backend unreachable. Start the API and try again.',
        status: 0
      })
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('times out a hanging request and preserves caller cancellation', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation((_url: string, options: RequestInit) => {
      return new Promise((_resolve, reject) => {
        options.signal?.addEventListener('abort', () => {
          reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
        });
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const pending = api.listProjects();
    const timedOut = expect(pending).rejects.toEqual(
      expect.objectContaining({
        message: 'Request timed out. Try again.',
        status: 408
      })
    );
    await vi.advanceTimersByTimeAsync(API_REQUEST_TIMEOUT_MS);
    await timedOut;

    const callerController = new AbortController();
    const cancelled = request<unknown>('/projects', { signal: callerController.signal });
    callerController.abort();
    await expect(cancelled).rejects.toEqual(
      expect.objectContaining({
        message: 'Request cancelled. Try again.',
        status: 0
      })
    );
    vi.useRealTimers();
  });
});
