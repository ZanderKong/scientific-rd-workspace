'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { EvaluationRun } from '@/lib/domain';
import { BackLink, ButtonLink, PageHeader, PageState, StatusBadge } from './shared';
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';
import {
  CaseTypeBadge,
  MetadataList,
  MetricStrip,
  ScoreSummary,
  SectionHeader,
  TechnicalDetails
} from './scientific-ui';
import { formatStructuredValue } from '../presentation';

const terminal = new Set([
  'completed',
  'completed_with_errors',
  'failed',
  'interrupted',
  'cancelled'
]);

export function EvaluationDetail({ evaluationRunId }: { evaluationRunId: string }) {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Evaluation');
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      setRun(await api.getEvaluationRun(evaluationRunId));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorLoad'));
    }
  }, [evaluationRunId, t]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!run || terminal.has(run.status)) return;
    const timer = window.setInterval(() => void load(), 1500);
    return () => window.clearInterval(timer);
  }, [run, load]);
  if (!run || error)
    return (
      <div className='flex flex-1 flex-col px-4 pt-4 md:px-6'>
        <PageState loading={!error} error={error} />
      </div>
    );
  async function cancel() {
    try {
      setRun(await api.cancelEvaluationRun(run!.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorCancel'));
    }
  }
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-3 pb-8 md:px-6'>
      <BackLink href='/dashboard/evaluations'>{t('title')}</BackLink>
      <PageHeader
        title={t('runTitle')}
        description={t('dataset', { version: run.dataset_version })}
        action={<StatusBadge status={run.status} />}
      />
      <MetricStrip
        items={[
          { label: t('progress'), value: `${run.completed_cases}/${run.total_cases}` },
          { label: t('passed'), value: run.passed_cases, tone: 'primary' },
          {
            label: t('failed'),
            value: run.failed_cases,
            tone: run.failed_cases > 0 ? 'warning' : 'default'
          },
          { label: t('errors'), value: run.error_cases }
        ]}
      />
      <Card>
        <CardHeader>
          <SectionHeader title={t('configuration')} description={t('configurationHint')} />
        </CardHeader>
        <CardContent className='grid gap-4 text-sm'>
          <MetadataList
            items={[
              { label: t('model'), value: `${run.model_profile_key} · ${run.requested_model}` },
              {
                label: t('outputMode'),
                value: `${run.structured_output_mode} · prompt v${run.prompt_version}`
              },
              {
                label: t('created'),
                value: new Intl.DateTimeFormat(locale, {
                  dateStyle: 'medium',
                  timeStyle: 'short'
                }).format(new Date(run.created_at))
              },
              { label: t('dataset', { version: run.dataset_version }), value: run.dataset_version }
            ]}
          />
          <p>
            <strong>{t('judge')}:</strong>{' '}
            {run.judge_enabled
              ? `${run.judge_model_profile_key} (${t('optional')})`
              : t('disabled')}
          </p>
          {!terminal.has(run.status) && (
            <Button variant='destructive' onClick={() => void cancel()}>
              {t('cancel')}
            </Button>
          )}
        </CardContent>
      </Card>
      <div className='grid gap-3'>
        {run.results.map((result) => (
          <Card key={result.id}>
            <CardContent className='grid gap-4 py-4 text-sm'>
              <div className='flex flex-wrap items-center justify-between gap-2'>
                <span>
                  {result.evaluation_case?.case_type ? (
                    <CaseTypeBadge caseType={result.evaluation_case.case_type} />
                  ) : null}{' '}
                  <strong>{t('case', { number: result.ordinal + 1 })}</strong>
                </span>
                <StatusBadge status={result.status} />
              </div>
              <ScoreSummary scores={result.deterministic_scores_json} title={t('deterministic')} />
              {result.judge_scores_json ? (
                <div className='rounded-lg border border-dashed p-3'>
                  <ScoreSummary scores={result.judge_scores_json} title={t('modelJudge')} />
                  <p className='mt-2 text-xs text-muted-foreground'>{t('judgeSecondary')}</p>
                </div>
              ) : null}
              {result.failure_tags_json.length ? (
                <div>
                  <p className='mb-1 text-xs font-medium text-muted-foreground'>
                    {t('failureTags')}
                  </p>
                  <div className='flex flex-wrap gap-1'>
                    {result.failure_tags_json.map((tag) => (
                      <span
                        key={tag}
                        className='rounded bg-muted px-2 py-1 font-mono text-[0.68rem]'
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {result.evaluation_case ? (
                <TechnicalDetails title={t('caseContext')}>
                  <MetadataList
                    items={[
                      {
                        label: t('expectedBehavior'),
                        value: formatStructuredValue(result.evaluation_case.expected_behavior_json)
                      },
                      {
                        label: t('caseTags'),
                        value: result.evaluation_case.case_tags_json.join(', ') || '—'
                      },
                      { label: t('caseId'), value: result.evaluation_case.id, mono: true }
                    ]}
                    columns={1}
                  />
                </TechnicalDetails>
              ) : null}
              {result.error_message && (
                <p className='text-destructive'>
                  {result.error_code}: {result.error_message}
                </p>
              )}
              <div className='flex flex-wrap gap-2 border-t pt-3'>
                {result.evaluation_case && (
                  <ButtonLink
                    href={
                      typeof result.evaluation_case.finding_snapshot_json.analysis_run_id ===
                      'string'
                        ? `/dashboard/analysis/${result.evaluation_case.finding_snapshot_json.analysis_run_id}`
                        : '/dashboard/analysis'
                    }
                    variant='ghost'
                    size='sm'
                  >
                    {t('sourceFinding')}
                  </ButtonLink>
                )}
                {result.replay_analysis_run_id && (
                  <ButtonLink
                    href={`/dashboard/analysis/${result.replay_analysis_run_id}`}
                    variant='outline'
                    size='sm'
                  >
                    {t('replayAnalysis')}
                  </ButtonLink>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
