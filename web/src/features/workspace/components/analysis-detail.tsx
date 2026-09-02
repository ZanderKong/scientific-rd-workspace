'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api-client';
import type { AnalysisRun, Finding } from '@/lib/domain';
import { BackLink, PageHeader, PageState, StatusBadge, formatDate } from './shared';

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
      setError(e instanceof Error ? e.message : 'Review failed.');
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
        `${caseType === 'bad' ? 'Bad' : 'Reference'} Case ready: ${evaluationCase.id}`
      );
      setCaseFormOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to create Evaluation Case.');
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
              <Badge variant='outline'>{finding.claim_type.replaceAll('_', ' ')}</Badge>
              <Badge variant='secondary'>Confidence: {finding.confidence_label}</Badge>
              <StatusBadge status={finding.evidence_gate_status} />
            </div>
          </div>
          <Badge>{finding.review_status.replaceAll('_', ' ')}</Badge>
        </div>
      </CardHeader>
      <CardContent className='grid gap-4 text-sm'>
        <p className='text-muted-foreground'>{finding.confidence_rationale}</p>
        <p>
          <strong>Applicability:</strong> {finding.applicability_scope}
        </p>
        <div className='grid gap-3 md:grid-cols-2'>
          <div className='rounded-lg border p-3'>
            <h3 className='mb-2 font-medium'>Direct Structured Support</h3>
            {finding.structured_support_json.length ? (
              finding.structured_support_json.map((item, i) => (
                <pre key={i} className='mb-2 overflow-auto text-xs'>
                  {JSON.stringify(item, null, 2)}
                </pre>
              ))
            ) : (
              <p className='text-muted-foreground'>None verified.</p>
            )}
          </div>
          <div className='rounded-lg border p-3'>
            <h3 className='mb-2 font-medium'>Curated Evidence</h3>
            {finding.evidence_links.length ? (
              finding.evidence_links.map((item) => (
                <div key={item.id} className='mb-2'>
                  <Badge variant='outline'>{item.role}</Badge>{' '}
                  <span className='text-muted-foreground'>{item.rationale}</span>
                </div>
              ))
            ) : (
              <p className='text-muted-foreground'>No EvidenceRecord links selected.</p>
            )}
          </div>
        </div>
        <div className='rounded-lg bg-muted/40 p-3'>
          <h3 className='mb-1 font-medium'>Evidence Gate (authoritative)</h3>
          <p>{JSON.stringify(finding.evidence_gate_rationale_json)}</p>
        </div>
        {finding.limitations_json.length > 0 && (
          <div>
            <h3 className='font-medium'>Limitations</h3>
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
            <h3 className='font-medium'>Risks</h3>
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
            <h3 className='font-medium'>Missing evidence</h3>
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
            <h3 className='font-medium'>Suggested next experiment (non-authoritative)</h3>
            <pre className='mt-2 overflow-auto text-xs'>
              {JSON.stringify(finding.suggested_next_experiment_json, null, 2)}
            </pre>
          </div>
        )}
        <div className='grid gap-2 rounded-lg border p-3'>
          <h3 className='font-medium'>Human review (append-only)</h3>
          <Input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder='Reviewer name'
          />
          <select
            className='h-8 rounded-lg border bg-background px-2 text-sm'
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            <option value=''>Reject reason (required for Reject)</option>
            {reasonCodes.map((code) => (
              <option key={code} value={code}>
                {code.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder='Comment (required for Reject / Needs Evidence)'
          />
          <div className='flex flex-wrap gap-2'>
            <Button size='sm' disabled={busy} onClick={() => void review('accept')}>
              Accept
            </Button>
            <Button
              size='sm'
              variant='secondary'
              disabled={busy || !comment.trim()}
              onClick={() => void review('needs_evidence')}
            >
              Needs Evidence
            </Button>
            <Button
              size='sm'
              variant='destructive'
              disabled={busy || !comment.trim() || !reason}
              onClick={() => void review('reject')}
            >
              Reject
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
                {caseFormOpen ? 'Close Bad Case form' : 'Create Bad Case'}
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
                  Create Draft Experiment
                </Button>
              )}
            {finding.review_status === 'accepted' && (
              <Button
                size='sm'
                variant='outline'
                disabled={caseBusy}
                onClick={() => void createEvaluationCase('reference')}
              >
                Create Reference Case
              </Button>
            )}
          </div>
          {finding.review_status === 'rejected' && caseFormOpen && (
            <div className='grid gap-2 rounded border border-dashed p-3 text-sm'>
              <p className='font-medium'>Expected Bad Case behavior</p>
              <p className='text-muted-foreground'>
                The rejected output is stored as observed behavior. Confirm only the bounded
                expectations that the replay must satisfy.
              </p>
              <label className='grid gap-1'>
                Expected gate (optional unless the reason is insufficient_evidence)
                <select
                  className='h-8 rounded-lg border bg-background px-2 text-sm'
                  value={expectedGate}
                  onChange={(e) => setExpectedGate(e.target.value)}
                >
                  <option value=''>Do not assert a gate state</option>
                  <option value='supported'>supported</option>
                  <option value='partially_supported'>partially_supported</option>
                  <option value='insufficient_evidence'>insufficient_evidence</option>
                  <option value='contradicted'>contradicted</option>
                </select>
              </label>
              {finding.reviews.at(-1)?.reason_code === 'missed_limitation' && (
                <Input
                  value={requiredLimitationCode}
                  onChange={(e) => setRequiredLimitationCode(e.target.value)}
                  placeholder='Required limitation code'
                />
              )}
              {requiresExplicitExpectedBehavior && (
                <Textarea
                  value={expectedBehaviorNotes}
                  onChange={(e) => setExpectedBehaviorNotes(e.target.value)}
                  placeholder='Expected behavior statement (required for this rejection reason)'
                />
              )}
              <label className='flex items-center gap-2'>
                <input
                  type='checkbox'
                  checked={requireValidCitations}
                  onChange={(e) => setRequireValidCitations(e.target.checked)}
                />
                Require valid citations
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
                Save Bad Case expectations
              </Button>
            </div>
          )}
          {caseMessage && <p className='text-sm text-muted-foreground'>{caseMessage}</p>}
          {finding.reviews.length > 0 && (
            <div className='grid gap-1 text-xs text-muted-foreground'>
              {finding.reviews.map((item) => (
                <div key={item.id}>
                  #{item.sequence_number} {item.decision} · {item.reviewer_name} ·{' '}
                  {item.comment || '—'}
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
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      setRun(await api.getAnalysisRun(analysisRunId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load analysis.');
    }
  }, [analysisRunId]);
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
    <div className='flex flex-1 flex-col gap-6 px-4 pt-3 pb-8 md:px-6'>
      <BackLink href='/dashboard/analysis'>Analysis</BackLink>
      <PageHeader
        title='Scientific analysis run'
        description={`${run.provider_key} · ${run.requested_model} · ${formatDate(run.created_at)}`}
        action={<StatusBadge status={run.status} />}
      />
      <Card>
        <CardHeader>
          <CardTitle>Frozen context and configuration</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-2 text-sm'>
          <p>
            <strong>Profile:</strong> {run.model_profile_key} · <strong>Mode:</strong>{' '}
            {run.structured_output_mode}
          </p>
          <p>
            <strong>Prompt:</strong> {run.prompt_key} v{run.prompt_version} · {run.prompt_sha256}
          </p>
          <p>
            <strong>Context:</strong> {run.context_snapshot?.snapshot_sha256 ?? 'not persisted'} (
            {run.context_snapshot?.size_bytes ?? 0} bytes)
          </p>
          <p>
            <strong>Langfuse:</strong> {run.langfuse_sync_status}
          </p>
          {run.context_snapshot && (
            <details className='rounded border p-3'>
              <summary className='cursor-pointer font-medium'>Inspect frozen provenance</summary>
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
