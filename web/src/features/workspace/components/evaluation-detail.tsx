'use client';

import { useCallback, useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { EvaluationRun } from '@/lib/domain';
import { BackLink, ButtonLink, PageHeader, PageState, StatusBadge } from './shared';

const terminal = new Set([
  'completed',
  'completed_with_errors',
  'failed',
  'interrupted',
  'cancelled'
]);

export function EvaluationDetail({ evaluationRunId }: { evaluationRunId: string }) {
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      setRun(await api.getEvaluationRun(evaluationRunId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load evaluation run.');
    }
  }, [evaluationRunId]);
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
      setError(e instanceof Error ? e.message : 'Unable to cancel evaluation.');
    }
  }
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-3 pb-8 md:px-6'>
      <BackLink href='/dashboard/evaluations'>Evaluations</BackLink>
      <PageHeader
        title='Evaluation run'
        description={`Dataset ${run.dataset_version}`}
        action={<StatusBadge status={run.status} />}
      />
      <Card>
        <CardHeader>
          <CardTitle>Run configuration</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-2 text-sm'>
          <p>
            <strong>Progress:</strong> {run.completed_cases}/{run.total_cases} · passed{' '}
            {run.passed_cases} · failed {run.failed_cases} · errors {run.error_cases}
          </p>
          <p>
            <strong>Model:</strong> {run.model_profile_key} · {run.structured_output_mode} · prompt
            v{run.prompt_version}
          </p>
          <p>
            <strong>Judge:</strong>{' '}
            {run.judge_enabled ? `${run.judge_model_profile_key} (optional)` : 'disabled'}
          </p>
          {!terminal.has(run.status) && (
            <Button variant='destructive' onClick={() => void cancel()}>
              Cancel run
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
                  <Badge variant='outline'>
                    {result.evaluation_case?.case_type?.replace('_', ' ') ?? 'case'}
                  </Badge>{' '}
                  <strong>Case {result.ordinal + 1}</strong>
                </span>
                <StatusBadge status={result.status} />
              </div>
              <p>
                <strong>Deterministic:</strong> {JSON.stringify(result.deterministic_scores_json)}
              </p>
              {result.judge_scores_json && (
                <p>
                  <strong>Model judge:</strong> {JSON.stringify(result.judge_scores_json)}
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
                    Source Finding
                  </ButtonLink>
                )}
                {result.replay_analysis_run_id && (
                  <ButtonLink
                    href={`/dashboard/analysis/${result.replay_analysis_run_id}`}
                    variant='outline'
                    size='sm'
                  >
                    Replay Analysis
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
