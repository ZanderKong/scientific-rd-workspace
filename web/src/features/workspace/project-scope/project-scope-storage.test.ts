import { describe, expect, it } from 'vitest';
import {
  isProjectScopedRoute,
  resolveActiveProjectId,
  withProjectQuery,
  writeActiveProjectId
} from './project-scope-storage';

const projects = [{ id: 'project-a' }, { id: 'project-b' }];

describe('project scope contract', () => {
  it('uses path, query, storage, then first project priority', () => {
    expect(resolveActiveProjectId(projects, '/dashboard/projects/project-b', '', 'project-a')).toBe(
      'project-b'
    );
    expect(
      resolveActiveProjectId(projects, '/dashboard/samples', '?project=project-b', 'project-a')
    ).toBe('project-b');
    expect(resolveActiveProjectId(projects, '/dashboard/samples', '', 'project-a')).toBe(
      'project-a'
    );
    expect(resolveActiveProjectId(projects, '/dashboard/samples', '', 'stale')).toBe('project-a');
    expect(resolveActiveProjectId([], '/dashboard/samples', '', 'stale')).toBeNull();
  });

  it('updates only the project query and leaves other parameters intact', () => {
    expect(withProjectQuery('/dashboard/samples', 'q=abc&project=old', 'project-b')).toBe(
      '/dashboard/samples?q=abc&project=project-b'
    );
    expect(withProjectQuery('/dashboard/settings', '', 'project-b')).toBe(
      '/dashboard/settings?project=project-b'
    );
    expect(isProjectScopedRoute('/dashboard/data')).toBe(true);
    expect(isProjectScopedRoute('/dashboard/settings')).toBe(false);
  });

  it('writes and clears the active project without coupling to scientific objects', () => {
    const values = new Map<string, string>();
    const storage = {
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key)
    };
    writeActiveProjectId('project-a', storage);
    expect(values.get('scientific_workspace_project')).toBe('project-a');
    writeActiveProjectId(null, storage);
    expect(values.has('scientific_workspace_project')).toBe(false);
  });
});
