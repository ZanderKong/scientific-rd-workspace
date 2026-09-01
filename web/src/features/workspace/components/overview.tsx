'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { Experiment, Project } from '@/lib/domain';
import { ExperimentTable } from './experiment-table';
import { ButtonLink, PageHeader, PageState } from './shared';

export function Overview() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([api.listProjects(), api.listExperiments()])
      .then(([p, e]) => {
        setProjects(p);
        setExperiments(e);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);
  const active = useMemo(() => projects.filter((p) => p.status === 'active').length, [projects]);
  return (
    <div className='flex flex-1 flex-col px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title='Workspace overview'
        description='A durable home for your projects, experiments, and evidence.'
        action={<ButtonLink href='/dashboard/projects'>New project</ButtonLink>}
      />
      {loading || error ? (
        <PageState loading={loading} error={error} />
      ) : (
        <>
          <div className='mb-6 grid gap-4 sm:grid-cols-3'>
            <Card>
              <CardHeader>
                <CardTitle className='text-sm text-muted-foreground'>Active projects</CardTitle>
              </CardHeader>
              <CardContent className='text-3xl font-semibold'>{active}</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className='text-sm text-muted-foreground'>Experiments</CardTitle>
              </CardHeader>
              <CardContent className='text-3xl font-semibold'>{experiments.length}</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className='text-sm text-muted-foreground'>Completed</CardTitle>
              </CardHeader>
              <CardContent className='text-3xl font-semibold'>
                {experiments.filter((e) => e.status === 'completed').length}
              </CardContent>
            </Card>
          </div>
          <div className='mb-6 rounded-xl border border-dashed border-primary/40 bg-primary/5 px-4 py-3 text-sm text-muted-foreground'>
            Synthetic seed data is enabled for this Phase 1 demo. Every edit, upload, clone, and
            revision is persisted through the API.
          </div>
          <div className='mb-3 flex items-center justify-between'>
            <h2 className='text-lg font-semibold'>Recent experiments</h2>
            <ButtonLink href='/dashboard/experiments' variant='ghost' size='sm'>
              View all →
            </ButtonLink>
          </div>
          <ExperimentTable
            experiments={experiments
              .toSorted((a, b) => b.updated_at.localeCompare(a.updated_at))
              .slice(0, 8)}
          />
        </>
      )}
    </div>
  );
}
