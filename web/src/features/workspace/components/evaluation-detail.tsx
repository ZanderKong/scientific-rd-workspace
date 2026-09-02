'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { EvaluationRun } from '@/lib/domain';
import { BackLink, ButtonLink, PageHeader, PageState, StatusBadge } from './shared';
import { useTranslations } from 'next-intl';

const terminal = new Set([
  'completed',
  'completed_with_errors',
  'failed',
  'interrupted',
  'cancelled'
]);

export function EvaluationDetail({ evaluationRunId }: { evaluationRunId: string }) {
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
      <Card>
        <CardHeader>
          <CardTitle>{t('configuration')}</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-2 text-sm'>
          <p>
            <strong>{t('progress')}:</strong> {run.completed_cases}/{run.total_cases} ·{' '}
            {t('passed')} {run.passed_cases} · {t('failed')} {run.failed_cases} · {t('errors')}{' '}
            {run.error_cases}
          </p>
          <p>
            <strong>{t('model')}:</strong> {run.model_profile_key} · {run.structured_output_mode} ·
            prompt v{run.prompt_version}
          </p>
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
            <CardContent className='grid gap-2 py-4 text-sm'>
              <div className='flex flex-wrap items-center justify-between gap-2'>
                <span>
                  {result.evaluation_case?.case_type ? (
                    <StatusBadge status={result.evaluation_case.case_type} />
                  ) : null}{' '}
                  <strong>{t('case', { number: result.ordinal + 1 })}</strong>
                </span>
                <StatusBadge status={result.status} />
              </div>
              <p>
                <strong>{t('deterministic')}:</strong>{' '}
                {JSON.stringify(result.deterministic_scores_json)}
              </p>
              {result.judge_scores_json && (
                <p>
                  <strong>{t('modelJudge')}:</strong> {JSON.stringify(result.judge_scores_json)}
                </p>
              )}
              {result.error_message && (
                <p className='text-destructive'>
                  {result.error_code}: {result.error_message}
                </p>
              )}
              <div className='flex flex-wrap gap-2'>
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
