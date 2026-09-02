'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { AnalysisRun, Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge, formatDate } from './shared';

export function AnalysisList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    api
      .listProjects()
      .then((items) => {
        setProjects(items);
        setProjectId(items[0]?.id ?? '');
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (projectId)
      void api
        .listAnalysisRuns(projectId)
        .then(setRuns)
        .catch((e) => setError(e.message));
  }, [projectId]);
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title='Scientific analysis'
        description='Structured Findings and human review over frozen scientific context.'
      />
      {loading || error ? (
        <PageState loading={loading} error={error} />
      ) : (
        <>
          <select
            className='h-8 max-w-md rounded-lg border bg-background px-2 text-sm'
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value=''>Choose a project</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.title}
              </option>
            ))}
          </select>
          {runs.length === 0 ? (
            <PageState
              empty='No analysis runs yet. Start one from Compare.'
              action={<ButtonLink href='/dashboard/compare'>Open Compare</ButtonLink>}
            />
          ) : (
            <div className='grid gap-4'>
              {runs.map((run) => (
                <Card key={run.id}>
                  <CardHeader>
                    <div className='flex flex-wrap items-center justify-between gap-2'>
                      <CardTitle className='text-base'>
                        {run.provider_key} · {run.model_profile_key}
                      </CardTitle>
                      <StatusBadge status={run.status} />
                    </div>
                  </CardHeader>
                  <CardContent className='flex flex-wrap items-center justify-between gap-3 text-sm'>
                    <span>
                      {formatDate(run.created_at)} · {run.findings.length} Findings ·{' '}
                      {run.structured_output_mode}
                    </span>
                    <ButtonLink href={`/dashboard/analysis/${run.id}`} variant='outline' size='sm'>
                      Inspect run
                    </ButtonLink>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
