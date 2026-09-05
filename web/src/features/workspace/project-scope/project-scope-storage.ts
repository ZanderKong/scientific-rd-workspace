import type { ReadonlyURLSearchParams } from 'next/navigation';
import type { ResearchObject } from '@/lib/domain';

export const ACTIVE_PROJECT_STORAGE_KEY = 'scientific_workspace_project';
export const PROJECT_LABELS_STORAGE_KEY = 'scientific_workspace_project_labels_v1';

export function readActiveProjectId(storage: Pick<Storage, 'getItem'> = window.localStorage) {
  return storage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
}

export function writeActiveProjectId(
  id: string | null,
  storage: Pick<Storage, 'setItem' | 'removeItem'> = window.localStorage
) {
  if (id) storage.setItem(ACTIVE_PROJECT_STORAGE_KEY, id);
  else storage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
}

export function readProjectLabels(
  storage: Pick<Storage, 'getItem'> = window.localStorage
): Record<string, string> {
  try {
    const raw = storage.getItem(PROJECT_LABELS_STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([, value]) => typeof value === 'string' && value.trim())
    );
  } catch {
    return {};
  }
}

export function writeProjectLabels(
  labels: Record<string, string>,
  storage: Pick<Storage, 'setItem'> = window.localStorage
) {
  storage.setItem(PROJECT_LABELS_STORAGE_KEY, JSON.stringify(labels));
}

export function projectIdFromPathname(pathname: string) {
  return pathname.match(/^\/dashboard\/projects\/([^/]+)/)?.[1] ?? null;
}

export function resolveActiveProjectId(
  projects: Pick<ResearchObject, 'id'>[],
  pathname: string,
  searchParams: ReadonlyURLSearchParams | URLSearchParams | string,
  savedProjectId: string | null
) {
  const valid = new Set(projects.map((project) => project.id));
  const query = new URLSearchParams(
    typeof searchParams === 'string' ? searchParams : searchParams.toString()
  ).get('project');
  return (
    [projectIdFromPathname(pathname), query, savedProjectId].find((id): id is string =>
      Boolean(id && valid.has(id))
    ) ??
    projects[0]?.id ??
    null
  );
}

export function isProjectScopedRoute(pathname: string) {
  return [
    '/dashboard/samples',
    '/dashboard/experiments',
    '/dashboard/data',
    '/dashboard/changes'
  ].some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export function withProjectQuery(
  pathname: string,
  searchParams: ReadonlyURLSearchParams | URLSearchParams | string,
  projectId: string | null
) {
  const params = new URLSearchParams(
    typeof searchParams === 'string' ? searchParams : searchParams.toString()
  );
  if (projectId) params.set('project', projectId);
  else params.delete('project');
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}
