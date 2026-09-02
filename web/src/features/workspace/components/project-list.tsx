'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { api } from '@/lib/api-client';
import type { Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge } from './shared';
import { ProjectForm } from './project-form';
import { useTranslations } from 'next-intl';
import { formatDate } from './shared';
import { parseLocale } from '@/i18n/config';
import { useLocale } from 'next-intl';

export function ProjectList() {
  const locale = parseLocale(useLocale());
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
      <div className='mb-4 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 p-3'>
        <Input
          className='h-9 max-w-sm bg-background'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('searchPlaceholder')}
          aria-label={t('searchAria')}
        />
        <select
          className='h-9 rounded-lg border border-input bg-background px-3 text-sm'
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
        <Card>
          <CardHeader className='border-b'>
            <CardTitle className='text-base'>{t('researchProgram')}</CardTitle>
            <CardDescription>{t('researchProgramHint')}</CardDescription>
          </CardHeader>
          <CardContent className='p-0'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('tableProject')}</TableHead>
                  <TableHead>{t('statusLabel')}</TableHead>
                  <TableHead>{t('tableExperiments')}</TableHead>
                  <TableHead>{t('tableUpdated')}</TableHead>
                  <TableHead className='text-right'>{t('open')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((project) => (
                  <TableRow key={project.id}>
                    <TableCell className='min-w-64'>
                      <div className='flex items-start gap-3'>
                        <span
                          className='mt-1 size-2 shrink-0 rounded-full bg-primary'
                          aria-hidden='true'
                        />
                        <div className='min-w-0'>
                          <div className='truncate font-medium'>{project.title}</div>
                          <div className='font-mono text-xs text-muted-foreground'>
                            {project.code}
                          </div>
                          <div className='mt-1 line-clamp-1 text-xs text-muted-foreground'>
                            {project.description || t('descriptionPlaceholder')}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={project.status} />
                    </TableCell>
                    <TableCell className='tabular-nums'>{project.experiment_count}</TableCell>
                    <TableCell className='whitespace-nowrap text-xs text-muted-foreground'>
                      {formatDate(project.updated_at, locale)}
                    </TableCell>
                    <TableCell className='text-right'>
                      <ButtonLink
                        href={`/dashboard/projects/${project.id}`}
                        variant='outline'
                        size='sm'
                      >
                        {t('open')}
                      </ButtonLink>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
