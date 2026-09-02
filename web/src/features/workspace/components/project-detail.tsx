'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { Experiment, Project } from '@/lib/domain';
import { ExperimentTable } from './experiment-table';
import { BackLink, ButtonLink, PageHeader, PageState, StatusBadge } from './shared';
import { ProjectForm } from './project-form';
import { useTranslations } from 'next-intl';

export function ProjectDetail({ projectId }: { projectId: string }) {
  const t = useTranslations('Projects');
  const [project, setProject] = useState<Project | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [p, e] = await Promise.all([
        api.getProject(projectId),
        api.listProjectExperiments(projectId)
      ]);
      setProject(p);
      setExperiments(e);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('notFound'));
    } finally {
      setLoading(false);
    }
  }, [projectId, t]);
  useEffect(() => {
    void load();
  }, [load]);
  if (loading || error || !project)
    return (
      <div className='flex flex-1 flex-col px-4 pt-4 md:px-6'>
        <PageState loading={loading} error={error || (!project ? t('notFound') : '')} />
      </div>
    );
  return (
    <div className='flex flex-1 flex-col px-4 pt-3 pb-8 md:px-6'>
      <BackLink href='/dashboard/projects' children={t('title')} />
      <PageHeader
        title={project.title}
        description={`${project.code} · ${project.description || t('descriptionPlaceholder')}`}
        action={
          <div className='flex gap-2'>
            <Button variant='outline' onClick={() => setEditing((v) => !v)}>
              {editing ? t('closeEdit') : t('edit')}
            </Button>
            <ButtonLink href={`/dashboard/projects/${project.id}/experiments/new`}>
              {t('newExperiment')}
            </ButtonLink>
          </div>
        }
      />
      <div className='mb-6 flex items-center gap-2'>
        <StatusBadge status={project.status} />
        <span className='text-sm text-muted-foreground'>
          {t('experimentsCount', { count: experiments.length })}
        </span>
      </div>
      {editing && (
        <Card className='mb-6'>
          <CardHeader>
            <CardTitle>{t('edit')}</CardTitle>
          </CardHeader>
          <CardContent>
            <ProjectForm
              project={project}
              onSaved={(saved) => {
                setProject(saved);
                setEditing(false);
              }}
              onCancel={() => setEditing(false)}
            />
          </CardContent>
        </Card>
      )}
      <div className='mb-3 flex items-center justify-between'>
        <h2 className='text-lg font-semibold'>{t('experimentsHeading')}</h2>
        <span className='text-sm text-muted-foreground'>{t('revisionsDescription')}</span>
      </div>
      <ExperimentTable experiments={experiments} />
    </div>
  );
}
