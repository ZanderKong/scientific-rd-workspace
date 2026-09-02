'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { api } from '@/lib/api-client';
import type { AnalysisRun, Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge, formatDate } from './shared';
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';
import { SectionHeader } from './scientific-ui';

export function AnalysisList() {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Analysis');
  const common = useTranslations('Common');
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
      <PageHeader title={t('title')} description={t('description')} />
      {loading || error ? (
        <PageState loading={loading} error={error} />
      ) : (
        <>
          <select
            className='h-8 max-w-md rounded-lg border bg-background px-2 text-sm'
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value=''>{common('chooseProject')}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.title}
              </option>
            ))}
          </select>
          {runs.length === 0 ? (
            <PageState
              empty={t('noRuns')}
              action={<ButtonLink href='/dashboard/compare'>{t('openCompare')}</ButtonLink>}
            />
          ) : (
            <Card>
              <CardHeader>
                <SectionHeader title={t('runHistory')} description={t('runHistoryHint')} />
              </CardHeader>
              <CardContent className='p-0'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('created')}</TableHead>
                      <TableHead>{t('provider')}</TableHead>
                      <TableHead>{t('model')}</TableHead>
                      <TableHead>{t('findings')}</TableHead>
                      <TableHead>{t('status')}</TableHead>
                      <TableHead className='text-right'>{t('inspectRun')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((run) => (
                      <TableRow key={run.id}>
                        <TableCell className='whitespace-nowrap text-xs text-muted-foreground'>
                          {formatDate(run.created_at, locale)}
                        </TableCell>
                        <TableCell>
                          <div className='font-medium'>{run.provider_key}</div>
                          <div className='text-xs text-muted-foreground'>
                            {run.structured_output_mode}
                          </div>
                        </TableCell>
                        <TableCell className='max-w-56 whitespace-normal text-sm'>
                          {run.model_profile_key}
                          <div className='font-mono text-[0.68rem] text-muted-foreground'>
                            {run.requested_model}
                          </div>
                        </TableCell>
                        <TableCell className='tabular-nums'>{run.findings.length}</TableCell>
                        <TableCell>
                          <StatusBadge status={run.status} />
                        </TableCell>
                        <TableCell className='text-right'>
                          <ButtonLink
                            href={`/dashboard/analysis/${run.id}`}
                            variant='outline'
                            size='sm'
                          >
                            {t('inspectRun')}
                          </ButtonLink>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
