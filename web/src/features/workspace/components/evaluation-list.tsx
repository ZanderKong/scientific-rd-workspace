'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
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
import type { EvaluationCase, EvaluationRun, Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge, formatDate } from './shared';
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';
import { CaseTypeBadge, MetricStrip, SectionHeader } from './scientific-ui';

export function EvaluationList() {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Evaluation');
  const common = useTranslations('Common');
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [filter, setFilter] = useState<'all' | 'bad_case' | 'reference_case'>('all');
  const [error, setError] = useState('');
  useEffect(() => {
    api
      .listProjects()
      .then((items) => {
        setProjects(items);
        setProjectId(items[0]?.id ?? '');
      })
      .catch((e) => setError(e instanceof Error ? e.message : t('errorLoad')));
  }, [t]);
  const load = useCallback(async () => {
    if (!projectId) return;
    try {
      const [c, r] = await Promise.all([
        api.listEvaluationCases(projectId, filter === 'all' ? undefined : filter),
        api.listEvaluationRuns(projectId)
      ]);
      setCases(c);
      setRuns(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorLoad'));
    }
  }, [filter, projectId, t]);
  useEffect(() => {
    void load();
  }, [load]);
  async function runCases() {
    if (!cases.length) return;
    try {
      await api.createEvaluationRun(projectId, {
        evaluation_case_ids: cases.map((item) => item.id),
        model_profile_key: 'analysis-default'
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorCreate'));
    }
  }
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-4 pb-8 md:px-6'>
      <PageHeader title={t('title')} description={t('description')} />
      <div className='flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 p-3'>
        <select
          className='h-8 rounded-lg border bg-background px-2 text-sm'
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
        <select
          className='h-8 rounded-lg border bg-background px-2 text-sm'
          value={filter}
          onChange={(e) => setFilter(e.target.value as typeof filter)}
        >
          <option value='all'>{t('allCases')}</option>
          <option value='bad_case'>{t('badCases')}</option>
          <option value='reference_case'>{t('referenceCases')}</option>
        </select>
        <Button onClick={() => void runCases()} disabled={!cases.length}>
          {t('runSelected')}
        </Button>
      </div>
      {error ? (
        <PageState error={error} />
      ) : (
        <>
          <MetricStrip
            items={[
              { label: t('cases'), value: cases.length },
              {
                label: t('referenceCases'),
                value: cases.filter((item) => item.case_type === 'reference_case').length,
                tone: 'primary'
              },
              {
                label: t('badCases'),
                value: cases.filter((item) => item.case_type === 'bad_case').length,
                tone: 'warning'
              },
              { label: t('runs'), value: runs.length }
            ]}
          />
          <Card>
            <CardHeader>
              <SectionHeader
                title={`${t('cases')} (${cases.length})`}
                description={t('casesHint')}
              />
            </CardHeader>
            <CardContent className='p-0'>
              {cases.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('caseType')}</TableHead>
                      <TableHead>{t('tags')}</TableHead>
                      <TableHead>{t('created')}</TableHead>
                      <TableHead className='text-right'>{t('sourceFinding')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cases.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <CaseTypeBadge caseType={item.case_type} />
                        </TableCell>
                        <TableCell className='max-w-72 whitespace-normal text-sm'>
                          {item.case_tags_json.join(', ') || t('untagged')}
                        </TableCell>
                        <TableCell className='whitespace-nowrap text-xs text-muted-foreground'>
                          {formatDate(item.created_at, locale)}
                        </TableCell>
                        <TableCell className='text-right'>
                          <ButtonLink
                            href={
                              typeof item.finding_snapshot_json.analysis_run_id === 'string'
                                ? `/dashboard/analysis/${item.finding_snapshot_json.analysis_run_id}`
                                : '/dashboard/analysis'
                            }
                            variant='ghost'
                            size='sm'
                          >
                            {t('sourceFinding')}
                          </ButtonLink>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className='p-6 text-sm text-muted-foreground'>{t('noCases')}</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <SectionHeader title={t('runs')} description={t('runsHint')} />
            </CardHeader>
            <CardContent className='p-0'>
              {runs.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('created')}</TableHead>
                      <TableHead>{t('model')}</TableHead>
                      <TableHead>{t('coverage')}</TableHead>
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
                        <TableCell className='text-sm'>
                          {run.model_profile_key}
                          <div className='text-xs text-muted-foreground'>{run.requested_model}</div>
                        </TableCell>
                        <TableCell className='tabular-nums'>
                          {run.completed_cases}/{run.total_cases}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={run.status} />
                        </TableCell>
                        <TableCell className='text-right'>
                          <ButtonLink
                            href={`/dashboard/evaluations/${run.id}`}
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
              ) : (
                <p className='p-6 text-sm text-muted-foreground'>{t('noRuns')}</p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
