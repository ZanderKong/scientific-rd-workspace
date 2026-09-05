'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { ChevronDown, Plus, RefreshCw, Search, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import type { ResearchObject } from '@/lib/domain';
import { generateProjectAvatar } from './project-avatar';
import { ProjectLabelDialog } from './project-label-dialog';
import { useProjectScope } from './project-scope-context';

function ProjectAvatar({
  project,
  label,
  className
}: {
  project: ResearchObject | null;
  label?: string | null;
  className?: string;
}) {
  const value = project ? label || generateProjectAvatar(project.title, project.code) : '+';
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-xs font-semibold text-primary-foreground',
        className
      )}
    >
      {value}
    </span>
  );
}

export function ProjectSwitcher() {
  const t = useTranslations('ProjectSwitcher');
  const {
    projects,
    activeProject,
    activeProjectId,
    loading,
    error,
    selectProject,
    refreshProjects,
    openCreateProject,
    getProjectLabel
  } = useProjectScope();
  const [open, setOpen] = useState(false);
  const [labelOpen, setLabelOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlighted, setHighlighted] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const filteredProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return projects;
    return projects.filter((project) =>
      `${project.code} ${project.title}`.toLowerCase().includes(normalized)
    );
  }, [projects, query]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setHighlighted(0);
      window.setTimeout(() => searchRef.current?.focus(), 0);
    }
  }, [open]);

  function choose(project: ResearchObject) {
    selectProject(project.id);
    setOpen(false);
  }

  function handleSearchKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlighted((value) => Math.min(value + 1, Math.max(filteredProjects.length - 1, 0)));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlighted((value) => Math.max(value - 1, 0));
    } else if (event.key === 'Enter' && filteredProjects[highlighted]) {
      event.preventDefault();
      choose(filteredProjects[highlighted]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
    }
  }

  return (
    <div className='px-2 py-2'>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={
            <Button
              variant='ghost'
              className='h-auto w-full justify-start gap-2 px-2 py-1.5 text-left hover:bg-sidebar-accent'
              data-testid='project-switcher-trigger'
              aria-label={
                activeProject
                  ? `${t('currentProject')}: ${activeProject.title}`
                  : t('createOrChoose')
              }
            />
          }
        >
          <ProjectAvatar
            project={activeProject}
            label={activeProject ? getProjectLabel(activeProject.id) : null}
          />
          <span className='min-w-0 flex-1 group-data-[collapsible=icon]:hidden'>
            <span className='block truncate text-xs font-semibold'>
              {loading ? t('loading') : activeProject?.title || t('createOrChoose')}
            </span>
            <span className='block truncate font-mono text-[10px] text-sidebar-foreground/55'>
              {activeProject?.code || t('noProjectSelected')}
            </span>
          </span>
          <ChevronDown className='size-4 shrink-0 text-sidebar-foreground/55 group-data-[collapsible=icon]:hidden' />
        </PopoverTrigger>
        <PopoverContent
          align='start'
          side='right'
          className='w-80 p-2'
          data-testid='project-switcher-menu'
        >
          <div className='mb-2 flex items-center justify-between px-1'>
            <div>
              <p className='text-xs font-semibold'>{t('currentProject')}</p>
              <p className='text-[11px] text-muted-foreground'>
                {activeProject?.title || t('noProjectSelected')}
              </p>
            </div>
            {activeProject && (
              <ProjectAvatar
                project={activeProject}
                label={getProjectLabel(activeProject.id)}
                className='size-7 text-[10px]'
              />
            )}
          </div>
          <div className='relative mb-2'>
            <Search className='pointer-events-none absolute top-2 left-2.5 size-3.5 text-muted-foreground' />
            <Input
              ref={searchRef}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setHighlighted(0);
              }}
              onKeyDown={handleSearchKeyDown}
              className='h-8 pl-8 text-xs'
              placeholder={t('search')}
              aria-label={t('search')}
            />
          </div>
          <div
            className='max-h-64 space-y-0.5 overflow-y-auto'
            role='listbox'
            aria-label={t('projects')}
          >
            {loading && (
              <p className='px-2 py-4 text-center text-xs text-muted-foreground'>{t('loading')}</p>
            )}
            {!loading && error && (
              <div className='space-y-2 px-2 py-3 text-xs text-destructive'>
                <p>{t('loadError')}</p>
                <Button variant='outline' size='xs' onClick={() => void refreshProjects()}>
                  <RefreshCw /> {t('retry')}
                </Button>
              </div>
            )}
            {!loading && !error && filteredProjects.length === 0 && (
              <p className='px-2 py-4 text-center text-xs text-muted-foreground'>
                {projects.length ? t('noMatch') : t('empty')}
              </p>
            )}
            {!loading &&
              !error &&
              filteredProjects.map((project, index) => (
                <button
                  type='button'
                  key={project.id}
                  role='option'
                  aria-selected={project.id === activeProjectId}
                  onMouseEnter={() => setHighlighted(index)}
                  onClick={() => choose(project)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs transition hover:bg-accent',
                    index === highlighted && 'bg-accent/70'
                  )}
                >
                  <ProjectAvatar
                    project={project}
                    label={getProjectLabel(project.id)}
                    className='size-7 text-[10px]'
                  />
                  <span className='min-w-0 flex-1'>
                    <span className='block truncate font-medium'>{project.title}</span>
                    <span className='font-mono text-[10px] text-muted-foreground'>
                      {project.code}
                    </span>
                  </span>
                  {project.id === activeProjectId && (
                    <span className='text-[10px] text-primary'>{t('active')}</span>
                  )}
                </button>
              ))}
          </div>
          <div className='mt-2 border-t pt-2'>
            <button
              type='button'
              className='flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs hover:bg-accent'
              data-testid='create-project'
              onClick={() => {
                setOpen(false);
                openCreateProject();
              }}
            >
              <Plus className='size-4' /> {t('create')}
            </button>
            <button
              type='button'
              disabled={!activeProject}
              className='flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs hover:bg-accent disabled:opacity-50'
              onClick={() => {
                setOpen(false);
                setLabelOpen(true);
              }}
            >
              <Settings2 className='size-4' /> {t('editLabel')}
            </button>
          </div>
        </PopoverContent>
      </Popover>
      <ProjectLabelDialog project={activeProject} open={labelOpen} onOpenChange={setLabelOpen} />
    </div>
  );
}
