'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api-client';
import type { AnalysisRun, Finding, JsonObject } from '@/lib/domain';
import { BackLink, PageHeader, PageState, StatusBadge, formatDate } from './shared';
import { parseLocale } from '@/i18n/config';

const reasonCodes = [
  'unsupported_causal_claim',
  'insufficient_evidence',
  'contradicted_by_evidence',
  'incorrect_experiment_comparison',
  'missed_limitation',
  'incorrect_citation',
  'unsafe_recommendation',
  'incorrect_reasoning',
  'other'
];
const safeBadCaseReasonCodes = new Set([
  'unsupported_causal_claim',
  'incorrect_citation',
  'missed_limitation',
  'insufficient_evidence',
  'incorrect_experiment_comparison'
]);

const claimTypeKeys = {
  scientific_observation: 'claimScientificObservation',
  hypothesis: 'claimHypothesis',
  comparative_finding: 'claimComparative',
  causal_claim: 'claimCausal',
  recommendation: 'claimRecommendation'
} as const;

const confidenceKeys = {
  low: 'confidenceLow',
  medium: 'confidenceMedium',
  high: 'confidenceHigh'
} as const;

const reasonKeys = {
  unsupported_causal_claim: 'reasonUnsupportedCausal',
  insufficient_evidence: 'reasonInsufficientEvidence',
  contradicted_by_evidence: 'reasonContradictedEvidence',
  incorrect_experiment_comparison: 'reasonIncorrectComparison',
  missed_limitation: 'reasonMissedLimitation',
  incorrect_citation: 'reasonIncorrectCitation',
  unsafe_recommendation: 'reasonUnsafeRecommendation',
  incorrect_reasoning: 'reasonIncorrectReasoning',
  other: 'reasonOther'
} as const;

function readableValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function objectValue(value: unknown): JsonObject | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonObject) : null;
}

function FindingCard({
  finding,
  projectId,
  onReviewed
}: {
  finding: Finding;
  projectId: string;
  onReviewed: () => void;
}) {
  const router = useRouter();
  const t = useTranslations('Analysis');
  const statusT = useTranslations('Status');
  const [reviewer, setReviewer] = useState('R&D Scientist');
  const [comment, setComment] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [caseBusy, setCaseBusy] = useState(false);
  const [caseMessage, setCaseMessage] = useState('');
  const [caseFormOpen, setCaseFormOpen] = useState(false);
  const [expectedGate, setExpectedGate] = useState('');
  const [requiredLimitationCode, setRequiredLimitationCode] = useState('');
  const [expectedBehaviorNotes, setExpectedBehaviorNotes] = useState('');
  const [requireValidCitations, setRequireValidCitations] = useState(false);
  const [error, setError] = useState('');
  const latestReview = finding.reviews.at(-1);
  const requiresExplicitExpectedBehavior =
    latestReview?.decision === 'reject' &&
    !safeBadCaseReasonCodes.has(latestReview.reason_code ?? '');
  async function review(decision: 'accept' | 'reject' | 'needs_evidence') {
    if (
      !reviewer.trim() ||
      (decision !== 'accept' && !comment.trim()) ||
      (decision === 'reject' && !reason)
    )
      return;
    setBusy(true);
    setError('');
    try {
      await api.createReview(finding.id, {
        decision,
        reviewer_name: reviewer,
        comment: comment || null,
        reason_code: decision === 'reject' ? reason : null,
        supersedes_review_id: finding.reviews.at(-1)?.id ?? null
      });
      onReviewed();
      setComment('');
    } catch (e) {
      setError(e instanceof Error ? e.message : t('reviewFailed'));
    } finally {
      setBusy(false);
    }
  }
  async function createEvaluationCase(caseType: 'bad' | 'reference') {
    setCaseBusy(true);
    setCaseMessage('');
    try {
      const expectedBehavior =
        caseType === 'bad'
          ? {
              ...(expectedGate ? { expected_gate_status: expectedGate } : {}),
              ...(requiredLimitationCode
                ? { required_limitation_codes: [requiredLimitationCode] }
                : {}),
              ...(expectedBehaviorNotes ? { reviewer_notes: expectedBehaviorNotes } : {}),
              ...(requireValidCitations ? { must_have_valid_citations: true } : {}),
              ...(latestReview?.reason_code === 'unsupported_causal_claim'
                ? { must_avoid_unsupported_causal_conclusion: true }
                : {}),
              ...(latestReview?.reason_code === 'incorrect_experiment_comparison'
                ? { direct_structured_support_required: true, comparison_assertions_correct: true }
                : {})
            }
          : undefined;
      const evaluationCase =
        caseType === 'bad'
          ? await api.createBadCase(finding.id, { expected_behavior: expectedBehavior })
          : await api.createReferenceCase(finding.id);
      setCaseMessage(
        t('caseReady', {
          type: caseType === 'bad' ? statusT('badCase') : statusT('referenceCase'),
          id: evaluationCase.id
        })
      );
      setCaseFormOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('reviewFailed'));
    } finally {
      setCaseBusy(false);
    }
  }
  return (
    <Card className='border-l-4 border-l-primary'>
      <CardHeader>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <CardTitle className='text-base'>{finding.claim}</CardTitle>
            <div className='mt-2 flex flex-wrap gap-2'>
              <Badge variant='outline'>{t(claimTypeKeys[finding.claim_type] ?? 'finding')}</Badge>
              <StatusBadge status={finding.review_status} />
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className='grid gap-4 text-sm'>
        <div className='grid gap-3 md:grid-cols-2'>
          <div className='rounded-lg border bg-muted/30 p-3'>
            <div className='mb-2 flex items-center justify-between gap-2'>
              <h3 className='font-medium'>{t('confidence')}</h3>
              <Badge variant='secondary'>
                {t(confidenceKeys[finding.confidence_label] ?? 'confidenceMedium')}
              </Badge>
            </div>
            <p className='text-muted-foreground'>{finding.confidence_rationale}</p>
          </div>
          <div className='rounded-lg border border-primary/30 bg-primary/5 p-3'>
            <div className='mb-2 flex items-center justify-between gap-2'>
              <h3 className='font-medium'>{t('gate')}</h3>
              <StatusBadge status={finding.evidence_gate_status} />
            </div>
            <p className='text-muted-foreground'>
              {Object.entries(finding.evidence_gate_rationale_json)
                .map(([key, value]) => `${key}: ${readableValue(value)}`)
                .join(' · ')}
            </p>
          </div>
        </div>
        <p>
          <strong>{t('applicability')}:</strong> {finding.applicability_scope}
        </p>
        <div className='grid gap-3 md:grid-cols-2'>
          <div className='rounded-lg border border-sky-500/30 bg-sky-500/5 p-3'>
            <h3 className='mb-2 font-medium'>{t('directSupport')}</h3>
            {finding.structured_support_json.length ? (
              finding.structured_support_json.map((item, i) => (
                <dl key={i} className='mb-2 grid gap-1 text-xs'>
                  {Object.entries(item).map(([key, value]) => (
                    <div key={key} className='grid grid-cols-[auto_1fr] gap-2'>
                      <dt className='font-medium text-muted-foreground'>{key}</dt>
                      <dd className='break-words'>{readableValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              ))
            ) : (
              <p className='text-muted-foreground'>{t('noneVerified')}</p>
            )}
          </div>
          <div className='rounded-lg border border-amber-500/30 bg-amber-500/5 p-3'>
            <h3 className='mb-2 font-medium'>{t('curatedEvidence')}</h3>
            {finding.evidence_links.length ? (
              finding.evidence_links.map((item) => (
                <div key={item.id} className='mb-2'>
                  <Badge variant='outline'>
                    {t(
                      item.role === 'supporting'
                        ? 'supporting'
                        : item.role === 'contradicting'
                          ? 'contradicting'
                          : 'contextual'
                    )}
                  </Badge>{' '}
                  <span className='text-muted-foreground'>{item.rationale}</span>
                </div>
              ))
            ) : (
              <p className='text-muted-foreground'>{t('noEvidenceLinks')}</p>
            )}
          </div>
        </div>
        {finding.limitations_json.length > 0 && (
          <div>
            <h3 className='font-medium'>{t('limitations')}</h3>
            <ul className='list-disc pl-5'>
              {finding.limitations_json.map((item) => (
                <li key={item.code}>
                  {item.code}: {item.description}
                </li>
              ))}
            </ul>
          </div>
        )}
        {finding.risks_json.length > 0 && (
          <div>
            <h3 className='font-medium'>{t('risks')}</h3>
            <ul className='list-disc pl-5'>
              {finding.risks_json.map((item) => (
                <li key={item.code}>
                  {item.code}: {item.description}
                </li>
              ))}
            </ul>
          </div>
        )}
        {finding.missing_evidence_json.length > 0 && (
          <div>
            <h3 className='font-medium'>{t('missingEvidence')}</h3>
            <ul className='list-disc pl-5'>
              {finding.missing_evidence_json.map((item) => (
                <li key={item.code}>
                  {item.code}: {item.description}
                </li>
              ))}
            </ul>
          </div>
        )}
        {finding.suggested_next_experiment_json && (
          <div className='rounded-lg border border-dashed p-3'>
            <h3 className='font-medium'>{t('suggestedNext')}</h3>
            {(() => {
              const suggestion = finding.suggested_next_experiment_json;
              const prefill = objectValue(suggestion.prefill);
              const changes = Array.isArray(prefill?.change_operations)
                ? prefill.change_operations.map(objectValue).filter(Boolean)
                : [];
              return (
                <>
                  <dl className='mt-3 grid gap-2 text-sm md:grid-cols-2'>
                    <div>
                      <dt className='text-muted-foreground'>{t('nextTitle')}</dt>
                      <dd className='break-words'>{readableValue(prefill?.title)}</dd>
                    </div>
                    <div>
                      <dt className='text-muted-foreground'>{t('nextObjective')}</dt>
                      <dd className='break-words'>{readableValue(prefill?.objective)}</dd>
                    </div>
                    <div className='md:col-span-2'>
                      <dt className='text-muted-foreground'>{t('nextControlStrategy')}</dt>
                      <dd className='break-words'>{readableValue(prefill?.control_strategy)}</dd>
                    </div>
                  </dl>
                  {changes.length > 0 && (
                    <div className='mt-3'>
                      <h4 className='text-sm font-medium'>{t('nextChanges')}</h4>
                      <ul className='mt-1 grid gap-1 text-sm'>
                        {changes.map((change, index) => (
                          <li key={index} className='break-words'>
                            <code>{readableValue(change?.path)}</code> · {t('nextChangeValue')}:{' '}
                            {readableValue(change?.value)} · {readableValue(change?.rationale)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <details className='mt-3 rounded border p-2'>
                    <summary className='cursor-pointer text-sm font-medium'>
                      {t('rawPayload')}
                    </summary>
                    <pre className='mt-2 max-h-80 overflow-auto text-xs'>
                      {JSON.stringify(suggestion, null, 2)}
                    </pre>
                  </details>
                </>
              );
            })()}
          </div>
        )}
        <div className='grid gap-2 rounded-lg border p-3'>
          <h3 className='font-medium'>{t('humanReview')}</h3>
          <Input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder={t('reviewerPlaceholder')}
          />
          <select
            className='h-8 rounded-lg border bg-background px-2 text-sm'
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            <option value=''>{t('rejectReason')}</option>
            {reasonCodes.map((code) => (
              <option key={code} value={code}>
                {t(reasonKeys[code as keyof typeof reasonKeys] ?? 'reasonOther')}
              </option>
            ))}
          </select>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t('commentPlaceholder')}
          />
          <div className='flex flex-wrap gap-2'>
            <Button size='sm' disabled={busy} onClick={() => void review('accept')}>
              {t('accept')}
            </Button>
            <Button
              size='sm'
              variant='secondary'
              disabled={busy || !comment.trim()}
              onClick={() => void review('needs_evidence')}
            >
              {t('needsEvidence')}
            </Button>
            <Button
              size='sm'
              variant='destructive'
              disabled={busy || !comment.trim() || !reason}
              onClick={() => void review('reject')}
            >
              {t('reject')}
            </Button>
            {finding.review_status === 'rejected' && (
              <Button
                size='sm'
                variant='outline'
                disabled={caseBusy}
                onClick={() => {
                  setCaseFormOpen((value) => !value);
                  setCaseMessage('');
                }}
              >
                {caseFormOpen ? t('closeBadCaseForm') : t('createBadCase')}
              </Button>
            )}
            {finding.suggested_next_experiment_json &&
              (latestReview?.decision === 'accept' ||
                latestReview?.decision === 'needs_evidence') &&
              finding.suggested_next_experiment_json.validation_status === 'valid' && (
                <Button
                  size='sm'
                  variant='outline'
                  onClick={() =>
                    router.push(
                      `/dashboard/projects/${projectId}/experiments/new?finding_id=${finding.id}`
                    )
                  }
                >
                  {t('createDraft')}
                </Button>
              )}
            {finding.review_status === 'accepted' && (
              <Button
                size='sm'
                variant='outline'
                disabled={caseBusy}
                onClick={() => void createEvaluationCase('reference')}
              >
                {t('createReferenceCase')}
              </Button>
            )}
          </div>
          {finding.review_status === 'rejected' && caseFormOpen && (
            <div className='grid gap-2 rounded border border-dashed p-3 text-sm'>
              <p className='font-medium'>{t('badCaseBehavior')}</p>
              <p className='text-muted-foreground'>{t('badCaseHint')}</p>
              <label className='grid gap-1'>
                {t('expectedGate')}
                <select
                  className='h-8 rounded-lg border bg-background px-2 text-sm'
                  value={expectedGate}
                  onChange={(e) => setExpectedGate(e.target.value)}
                >
                  <option value=''>{t('doNotAssertGate')}</option>
                  <option value='supported'>{statusT('supported')}</option>
                  <option value='partially_supported'>{statusT('partiallySupported')}</option>
                  <option value='insufficient_evidence'>{statusT('insufficientEvidence')}</option>
                  <option value='contradicted'>{statusT('contradicted')}</option>
                </select>
              </label>
              {finding.reviews.at(-1)?.reason_code === 'missed_limitation' && (
                <Input
                  value={requiredLimitationCode}
                  onChange={(e) => setRequiredLimitationCode(e.target.value)}
                  placeholder={t('requiredLimitation')}
                />
              )}
              {requiresExplicitExpectedBehavior && (
                <Textarea
                  value={expectedBehaviorNotes}
                  onChange={(e) => setExpectedBehaviorNotes(e.target.value)}
                  placeholder={t('expectedBehavior')}
                />
              )}
              <label className='flex items-center gap-2'>
                <input
                  type='checkbox'
                  checked={requireValidCitations}
                  onChange={(e) => setRequireValidCitations(e.target.checked)}
                />
                {t('requireCitations')}
              </label>
              <Button
                size='sm'
                disabled={
                  caseBusy ||
                  (finding.reviews.at(-1)?.reason_code === 'missed_limitation' &&
                    !requiredLimitationCode.trim()) ||
                  (requiresExplicitExpectedBehavior && !expectedBehaviorNotes.trim()) ||
                  (finding.reviews.at(-1)?.reason_code === 'insufficient_evidence' && !expectedGate)
                }
                onClick={() => void createEvaluationCase('bad')}
              >
                {t('saveBadCase')}
              </Button>
            </div>
          )}
          {caseMessage && <p className='text-sm text-muted-foreground'>{caseMessage}</p>}
          {finding.reviews.length > 0 && (
            <div className='grid gap-1 text-xs text-muted-foreground'>
              {finding.reviews.map((item) => (
                <div key={item.id}>
                  #{item.sequence_number} <StatusBadge status={item.decision} /> ·{' '}
                  {item.reviewer_name} · {item.comment || '—'}
                </div>
              ))}
            </div>
          )}
          {error && <p className='text-sm text-destructive'>{error}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export function AnalysisDetail({ analysisRunId }: { analysisRunId: string }) {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Analysis');
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      setRun(await api.getAnalysisRun(analysisRunId));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorLoad'));
    }
  }, [analysisRunId, t]);
  useEffect(() => {
    void load();
  }, [load]);
  if (error || !run)
    return (
      <div className='flex flex-1 flex-col px-4 pt-4 md:px-6'>
        <PageState loading={!error} error={error} />
      </div>
    );
  return (
    <div className='mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-6 px-4 pt-3 pb-8 md:px-6'>
      <BackLink href='/dashboard/analysis'>{t('title')}</BackLink>
      <PageHeader
        title={t('detailTitle')}
        description={t('detailDescription', {
          provider: run.provider_key,
          model: run.requested_model,
          date: formatDate(run.created_at, locale)
        })}
        action={<StatusBadge status={run.status} />}
      />
      <Card>
        <CardHeader>
          <CardTitle>{t('frozenContext')}</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-2 text-sm'>
          <p>
            <strong>{t('profile')}:</strong> {run.model_profile_key} · <strong>{t('mode')}:</strong>{' '}
            {run.structured_output_mode}
          </p>
          <p>
            <strong>{t('prompt')}:</strong> {run.prompt_key} v{run.prompt_version} ·{' '}
            {run.prompt_sha256}
          </p>
          <p>
            <strong>{t('context')}:</strong>{' '}
            {run.context_snapshot?.snapshot_sha256 ?? t('notPersisted')} (
            {run.context_snapshot?.size_bytes ?? 0} bytes)
          </p>
          <p>
            <strong>{t('langfuse')}:</strong> {run.langfuse_sync_status}
          </p>
          {run.context_snapshot && (
            <details className='rounded border p-3'>
              <summary className='cursor-pointer font-medium'>{t('inspectProvenance')}</summary>
              <pre className='mt-3 max-h-96 overflow-auto text-xs'>
                {JSON.stringify(run.context_snapshot.snapshot_json, null, 2)}
              </pre>
            </details>
          )}
          {run.error_message && (
            <p className='text-destructive'>
              {run.error_code}: {run.error_message}
            </p>
          )}
        </CardContent>
      </Card>
      <div className='grid gap-6'>
        {run.findings.map((finding) => (
          <FindingCard
            key={finding.id}
            finding={finding}
            projectId={run.project_id}
            onReviewed={() => void load()}
          />
        ))}
      </div>
    </div>
  );
}
