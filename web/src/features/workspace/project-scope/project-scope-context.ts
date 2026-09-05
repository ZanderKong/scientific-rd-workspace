'use client';

import { createContext, useContext } from 'react';
import type { ResearchObject } from '@/lib/domain';

export type ProjectScopeContextValue = {
  projects: ResearchObject[];
  activeProject: ResearchObject | null;
  activeProjectId: string | null;
  loading: boolean;
  error: string | null;
  selectProject: (id: string) => void;
  refreshProjects: () => Promise<void>;
  registerCreatedProject: (project: ResearchObject) => void;
  openCreateProject: () => void;
  getProjectLabel: (id: string) => string | null;
  setProjectLabel: (id: string, label: string | null) => void;
};

export const ProjectScopeContext = createContext<ProjectScopeContextValue | null>(null);

export function useProjectScope() {
  const value = useContext(ProjectScopeContext);
  if (!value) throw new Error('useProjectScope must be used within ProjectScopeProvider');
  return value;
}
