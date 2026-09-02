'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { EvaluationCase, EvaluationRun, Project } from '@/lib/domain';
import { ButtonLink, PageHeader, PageState, StatusBadge, formatDate } from './shared';
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';

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
      <div className='flex flex-wrap gap-2'>
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
          <Card>
            <CardHeader>
              <CardTitle>
                {t('cases')} ({cases.length})
              </CardTitle>
            </CardHeader>
            <CardContent className='grid gap-2'>
              {cases.length ? (
                cases.map((item) => (
                  <div
                    key={item.id}
                    className='flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm'
                  >
                    <span>
                      <span className='mr-2 rounded bg-muted px-2 py-1 text-xs'>
                        <StatusBadge status={item.case_type} />
                      </span>
                      {item.case_tags_json.join(', ') || t('untagged')}
                    </span>
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
                  </div>
                ))
              ) : (
                <p className='text-sm text-muted-foreground'>{t('noCases')}</p>
              )}
            </CardContent>
          </Card>
          <div className='grid gap-3'>
            {runs.map((run) => (
              <Card key={run.id}>
                <CardContent className='flex flex-wrap items-center justify-between gap-2 py-4 text-sm'>
                  <span>
                    {formatDate(run.created_at, locale)} · {run.completed_cases}/{run.total_cases}{' '}
                    {t('cases').toLowerCase()} · {run.model_profile_key}
                  </span>
                  <div className='flex items-center gap-2'>
                    <StatusBadge status={run.status} />
                    <ButtonLink
                      href={`/dashboard/evaluations/${run.id}`}
                      variant='outline'
                      size='sm'
                    >
                      {t('inspectRun')}
                    </ButtonLink>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
