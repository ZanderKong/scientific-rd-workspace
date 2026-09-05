'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '@/lib/api-client';
import type { ResearchObject } from '@/lib/domain';
import { ProjectCreateDialog } from './project-create-dialog';
import { ProjectScopeContext } from './project-scope-context';
import {
  isProjectScopedRoute,
  readActiveProjectId,
  readProjectLabels,
  resolveActiveProjectId,
  withProjectQuery,
  writeActiveProjectId,
  writeProjectLabels
} from './project-scope-storage';

export function ProjectScopeProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<ResearchObject[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    try {
      const nextProjects = await api.listObjects({ kind: 'project', limit: 100 });
      setProjects(nextProjects);
      setError(null);
    } catch (cause) {
      setProjects([]);
      setError(cause instanceof Error ? cause.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshProjects();
    setLabels(readProjectLabels());
  }, [refreshProjects]);

  useEffect(() => {
    if (loading) return;
    const savedProjectId = readActiveProjectId();
    const valid = new Set(projects.map((project) => project.id));
    const next = resolveActiveProjectId(projects, pathname, searchParams, savedProjectId);
    if (savedProjectId && !valid.has(savedProjectId)) writeActiveProjectId(null);
    if (next !== activeProjectId) {
      setActiveProjectId(next);
      writeActiveProjectId(next);
    }
    if (isProjectScopedRoute(pathname) && next && searchParams.get('project') !== next) {
      router.replace(withProjectQuery(pathname, searchParams, next));
    }
  }, [activeProjectId, loading, pathname, projects, router, searchParams]);

  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;

  const selectProject = useCallback(
    (id: string) => {
      if (!projects.some((project) => project.id === id)) return;
      setActiveProjectId(id);
      writeActiveProjectId(id);
      if (pathname.match(/^\/dashboard\/projects\/[^/]+$/)) {
        router.push(`/dashboard/projects/${id}`);
      } else if (isProjectScopedRoute(pathname)) {
        router.replace(withProjectQuery(pathname, searchParams, id));
      }
    },
    [pathname, projects, router, searchParams]
  );

  const registerCreatedProject = useCallback((project: ResearchObject) => {
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
    setActiveProjectId(project.id);
    writeActiveProjectId(project.id);
  }, []);

  const getProjectLabel = useCallback((id: string) => labels[id] ?? null, [labels]);
  const setProjectLabel = useCallback((id: string, label: string | null) => {
    setLabels((current) => {
      const next = { ...current };
      if (label) next[id] = label;
      else delete next[id];
      writeProjectLabels(next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({
      projects,
      activeProject,
      activeProjectId,
      loading,
      error,
      selectProject,
      refreshProjects,
      registerCreatedProject,
      openCreateProject: () => setCreateOpen(true),
      getProjectLabel,
      setProjectLabel
    }),
    [
      activeProject,
      activeProjectId,
      error,
      getProjectLabel,
      loading,
      projects,
      refreshProjects,
      registerCreatedProject,
      selectProject,
      setProjectLabel
    ]
  );

  return (
    <ProjectScopeContext.Provider value={value}>
      {children}
      <ProjectCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </ProjectScopeContext.Provider>
  );
}
