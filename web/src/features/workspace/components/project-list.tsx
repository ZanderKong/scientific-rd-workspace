'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api-client';
import type { Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge } from './shared';
import { ProjectForm } from './project-form';
import { useTranslations } from 'next-intl';

export function ProjectList() {
  const t = useTranslations('Projects');
  const statusT = useTranslations('Status');
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
        title={t('title')}
        description={t('description')}
        action={
          <Button onClick={() => setShowForm((value) => !value)}>
            {showForm ? t('close') : t('newProject')}
          </Button>
        }
      />
      {showForm && (
        <Card className='mb-6'>
          <CardHeader>
            <CardTitle>{t('newProject')}</CardTitle>
            <CardDescription>{t('createDescription')}</CardDescription>
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
          placeholder={t('searchPlaceholder')}
          aria-label={t('searchAria')}
        />
        <select
          className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label={t('filterStatus')}
        >
          <option value='all'>{t('allStatuses')}</option>
          <option value='active'>{statusT('active')}</option>
          <option value='paused'>{statusT('paused')}</option>
          <option value='completed'>{statusT('completed')}</option>
          <option value='archived'>{statusT('archived')}</option>
        </select>
      </div>
      {loading || error ? (
        <PageState loading={loading} error={error} />
      ) : filtered.length === 0 ? (
        <PageState
          empty={projects.length === 0 ? t('noProjects') : t('noMatch')}
          action={
            projects.length === 0 ? (
              <Button onClick={() => setShowForm(true)}>{t('createFirst')}</Button>
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
                  {project.description || t('descriptionPlaceholder')}
                </p>
                <div className='mt-4 flex items-center justify-between text-xs text-muted-foreground'>
                  <span>{t('experimentsCount', { count: project.experiment_count })}</span>
                  <ButtonLink
                    href={`/dashboard/projects/${project.id}`}
                    variant='outline'
                    size='sm'
                  >
                    {t('open')}
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
