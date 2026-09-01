'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api-client';
import type { Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge } from './shared';
import { ProjectForm } from './project-form';

export function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  const filtered = useMemo(
    () =>
      projects.filter(
        (p) =>
          (status === 'all' || p.status === status) &&
          `${p.code} ${p.title} ${p.description ?? ''}`.toLowerCase().includes(query.toLowerCase())
      ),
    [projects, query, status]
  );
  return (
    <div className='flex flex-1 flex-col px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title='Projects'
        description='Organize experiments into durable research programs.'
        action={
          <Button onClick={() => setShowForm((value) => !value)}>
            {showForm ? 'Close' : 'New project'}
          </Button>
        }
      />
      {showForm && (
        <Card className='mb-6'>
          <CardHeader>
            <CardTitle>New project</CardTitle>
            <CardDescription>Create a durable container for experiments.</CardDescription>
          </CardHeader>
          <CardContent>
            <ProjectForm
              onSaved={(project) => {
                setProjects((items) => [project, ...items]);
                setShowForm(false);
              }}
              onCancel={() => setShowForm(false)}
            />
          </CardContent>
        </Card>
      )}
      <div className='mb-4 flex flex-wrap gap-2'>
        <Input
          className='max-w-sm'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Search projects…'
          aria-label='Search projects'
        />
        <select
          className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label='Filter project status'
        >
          <option value='all'>All statuses</option>
          <option value='active'>Active</option>
          <option value='paused'>Paused</option>
          <option value='completed'>Completed</option>
          <option value='archived'>Archived</option>
        </select>
      </div>
      {loading || error ? (
        <PageState loading={loading} error={error} />
      ) : filtered.length === 0 ? (
        <PageState
          empty={
            projects.length === 0
              ? 'No projects yet. Create the first research project.'
              : 'No projects match these filters.'
          }
          action={
            projects.length === 0 ? (
              <Button onClick={() => setShowForm(true)}>Create project</Button>
            ) : undefined
          }
        />
      ) : (
        <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
          {filtered.map((project) => (
            <Card key={project.id} className='transition-shadow hover:shadow-md'>
              <CardHeader>
                <div className='flex items-start justify-between gap-2'>
                  <div>
                    <CardTitle>{project.title}</CardTitle>
                    <CardDescription>{project.code}</CardDescription>
                  </div>
                  <StatusBadge status={project.status} />
                </div>
              </CardHeader>
              <CardContent>
                <p className='line-clamp-2 min-h-10 text-sm text-muted-foreground'>
                  {project.description || 'No description yet.'}
                </p>
                <div className='mt-4 flex items-center justify-between text-xs text-muted-foreground'>
                  <span>{project.experiment_count} experiments</span>
                  <ButtonLink
                    href={`/dashboard/projects/${project.id}`}
                    variant='outline'
                    size='sm'
                  >
                    Open project
                  </ButtonLink>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
