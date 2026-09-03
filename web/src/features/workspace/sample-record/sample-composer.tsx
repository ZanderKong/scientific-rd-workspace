'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Check, FlaskConical, Plus, Save } from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';
import type { ObjectType, SampleRecord } from '@/lib/domain';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ProcessBlock } from './process-block';
import {
  buildNewDraft,
  clientId,
  draftToCreatePayload,
  draftToPutPayload,
  recordToDraft,
  type DraftStep,
  type SampleRecordDraft
} from './model';

type SampleComposerProps = {
  projectId: string | null;
  initialRecord?: SampleRecord | null;
  mode?: 'create' | 'edit';
  zh: boolean;
  onCancel?: () => void;
  onSaved?: (record: SampleRecord) => void;
};

function readableError(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Request failed';
}

function reorder<T>(items: T[], index: number, direction: -1 | 1) {
  const target = index + direction;
  if (target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function SampleComposer({
  projectId,
  initialRecord,
  mode = 'create',
  zh,
  onCancel,
  onSaved
}: SampleComposerProps) {
  const initialKey = `${mode}:${initialRecord?.sample.id ?? 'new'}`;
  const [draft, setDraft] = useState<SampleRecordDraft>(() =>
    initialRecord ? recordToDraft(initialRecord) : buildNewDraft(projectId ?? '')
  );
  const [types, setTypes] = useState<ObjectType[]>([]);
  const [typeError, setTypeError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedRecord, setSavedRecord] = useState<SampleRecord | null>(null);

  useEffect(() => {
    setDraft(initialRecord ? recordToDraft(initialRecord) : buildNewDraft(projectId ?? ''));
    setSavedRecord(null);
    setError(null);
  }, [initialKey, initialRecord, projectId]);

  useEffect(() => {
    api
      .listTypes()
      .then(setTypes)
      .catch((cause) => setTypeError(readableError(cause)));
  }, []);

  const heading =
    mode === 'edit'
      ? zh
        ? '编辑 Sample Record'
        : 'Edit Sample Record'
      : zh
        ? '记录一个新 Sample'
        : 'Record a new Sample';
  const stepCount = draft.steps.length;

  const payloadHint = useMemo(() => {
    if (mode === 'edit')
      return zh
        ? '一次提交会重建当前线性链的 desired state。'
        : 'One request reconciles the desired state of this linear chain.';
    return zh
      ? '一次提交会创建 Sample、Process、资源关系与 revision。'
      : 'One request creates the Sample, Processes, resource relations, and revisions.';
  }, [mode, zh]);

  function updateStep(index: number, next: DraftStep) {
    setDraft((current) => ({
      ...current,
      steps: current.steps.map((step, stepIndex) => (stepIndex === index ? next : step))
    }));
  }

  function addStep() {
    setDraft((current) => ({
      ...current,
      steps: [
        ...current.steps,
        {
          clientId: clientId('step'),
          title: '',
          status: 'active',
          properties_jsonb: {},
          content_document: [],
          resources: []
        }
      ]
    }));
  }

  function removeStep(index: number) {
    setDraft((current) => ({
      ...current,
      steps: current.steps.filter((_, stepIndex) => stepIndex !== index)
    }));
  }

  function moveStep(index: number, direction: -1 | 1) {
    setDraft((current) => ({ ...current, steps: reorder(current.steps, index, direction) }));
  }

  async function save() {
    if (!projectId) {
      setError(zh ? '请先选择 Project Scope。' : 'Choose a Project Scope first.');
      return;
    }
    if (!draft.sample.title.trim()) {
      setError(zh ? '请填写 Sample 标题。' : 'Add a Sample title.');
      return;
    }
    if (draft.steps.some((step) => !step.title.trim())) {
      setError(
        zh
          ? '每个 Process Block 都需要标题，或用 / 选择定义。'
          : 'Every Process Block needs a title, or choose a definition with /.'
      );
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved =
        mode === 'edit' && initialRecord
          ? await api.updateSampleRecord(initialRecord.sample.id, draftToPutPayload(draft))
          : await api.createSampleRecord(draftToCreatePayload(projectId, draft));
      setSavedRecord(saved);
      onSaved?.(saved);
    } catch (cause) {
      setError(readableError(cause));
    } finally {
      setSaving(false);
    }
  }

  if (savedRecord) {
    return (
      <div className='mx-auto w-full max-w-4xl px-4 py-8 md:px-8' data-testid='sample-success'>
        <div className='overflow-hidden rounded-[1.75rem] border border-emerald-500/25 bg-emerald-500/[0.06] shadow-sm'>
          <div className='flex items-start gap-4 border-b border-emerald-500/15 p-6 md:p-8'>
            <div className='flex size-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-600 text-white'>
              <Check />
            </div>
            <div>
              <p className='font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-300'>
                Commit complete
              </p>
              <h1 className='mt-1 text-2xl font-semibold tracking-tight'>
                {zh ? 'Sample Record 已保存' : 'Sample Record saved'}
              </h1>
              <p className='mt-2 text-sm text-muted-foreground'>
                {savedRecord.sample.code} · {savedRecord.sample.title} · {savedRecord.steps.length}{' '}
                {zh ? '个 Process' : 'Processes'}
              </p>
            </div>
          </div>
          <div className='grid gap-2 p-6 sm:grid-cols-3 md:p-8'>
            <Link
              href={`/dashboard/samples/${savedRecord.sample.id}`}
              className='rounded-xl bg-primary px-3 py-3 text-center text-sm font-medium text-primary-foreground hover:opacity-90'
            >
              {zh ? '查看样品' : 'View Sample'}
            </Link>
            <Link
              href={`/dashboard/samples/new?project=${projectId}&from=${savedRecord.sample.id}`}
              className='rounded-xl border bg-background px-3 py-3 text-center text-sm font-medium hover:bg-muted'
            >
              {zh ? '基于此样品新建' : 'Create from this Sample'}
            </Link>
            <Link
              href={`/dashboard/samples/new?project=${projectId}`}
              className='rounded-xl border bg-background px-3 py-3 text-center text-sm font-medium hover:bg-muted'
            >
              {zh ? '录入全新样品' : 'Record a new Sample'}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <form
      aria-label={heading}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      className='min-h-full bg-[radial-gradient(circle_at_85%_0%,color-mix(in_oklch,var(--primary)_10%,transparent),transparent_28rem)]'
      data-testid='sample-composer'
    >
      <div className='mx-auto w-full max-w-[1320px] px-4 py-6 md:px-8 md:py-9'>
        <div className='mb-8 flex flex-wrap items-end justify-between gap-4'>
          <div>
            <Link
              href='/dashboard/samples'
              className='mb-4 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground'
            >
              <ArrowLeft className='size-3' /> {zh ? '返回 Samples' : 'Back to Samples'}
            </Link>
            <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
              Sample-first / record
            </p>
            <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
              <FlaskConical className='size-7 text-primary' />
              {heading}
            </h1>
            <p className='mt-2 max-w-2xl text-sm leading-6 text-muted-foreground'>
              {payloadHint}{' '}
              {typeError && (
                <span className='text-amber-700 dark:text-amber-300'>
                  ·{' '}
                  {zh
                    ? 'Process 定义暂不可用，可继续使用自定义过程。'
                    : 'Definitions unavailable; custom Processes remain available.'}
                </span>
              )}
            </p>
          </div>
          <div className='flex items-center gap-2'>
            {onCancel && (
              <Button type='button' variant='ghost' onClick={onCancel}>
                {zh ? '取消' : 'Cancel'}
              </Button>
            )}
            <Button type='submit' size='lg' disabled={saving} data-testid='save-sample-record'>
              <Save />{' '}
              {saving
                ? zh
                  ? '保存中…'
                  : 'Saving…'
                : zh
                  ? '保存 Sample Record'
                  : 'Save Sample Record'}
            </Button>
          </div>
        </div>

        <div className='mb-6 grid gap-4 rounded-[1.35rem] border bg-card/70 p-4 md:grid-cols-[minmax(0,1fr)_10rem_10rem] md:p-5'>
          <label className='grid gap-1.5 text-xs font-medium'>
            {zh ? 'Sample 标题' : 'Sample title'}
            <Input
              value={draft.sample.title}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  sample: { ...current.sample, title: event.target.value }
                }))
              }
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={
                zh ? '例如：KI 氯气纸带 · 2026-09-03' : 'e.g. KI chlorine strip · 2026-09-03'
              }
              className='h-10 bg-background/70'
              autoFocus
            />
          </label>
          <label className='grid gap-1.5 text-xs font-medium'>
            {zh ? 'Sample ID（可选）' : 'Sample ID (optional)'}
            <Input
              value={draft.sample.code ?? ''}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  sample: { ...current.sample, code: event.target.value }
                }))
              }
              placeholder='SMP-…'
              className='h-10 bg-background/70 font-mono text-xs'
            />
          </label>
          <label className='grid gap-1.5 text-xs font-medium'>
            {zh ? '状态' : 'Status'}
            <select
              value={draft.sample.status}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  sample: { ...current.sample, status: event.target.value }
                }))
              }
              className='h-10 rounded-lg border bg-background/70 px-2 text-sm'
            >
              <option value='draft'>{zh ? '草稿' : 'Draft'}</option>
              <option value='active'>{zh ? '活跃' : 'Active'}</option>
              <option value='completed'>{zh ? '已完成' : 'Completed'}</option>
            </select>
          </label>
        </div>

        <div className='mb-3 flex items-end justify-between gap-3'>
          <div>
            <p className='font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground'>
              Workflow chain
            </p>
            <h2 className='mt-1 text-xl font-semibold'>
              {zh ? 'Process Blocks' : 'Process Blocks'}{' '}
              <span className='ml-1 font-mono text-sm font-normal text-muted-foreground'>
                {stepCount}
              </span>
            </h2>
          </div>
          <Button type='button' variant='outline' onClick={addStep}>
            <Plus /> {zh ? '添加 Process' : 'Add Process'}
          </Button>
        </div>
        <div className='space-y-4'>
          {draft.steps.map((step, index) => (
            <ProcessBlock
              key={step.clientId}
              index={index}
              total={draft.steps.length}
              draft={step}
              projectId={projectId ?? ''}
              types={types}
              zh={zh}
              onChange={(next) => updateStep(index, next)}
              onRemove={() => removeStep(index)}
              onMove={(direction) => moveStep(index, direction)}
            />
          ))}
        </div>
        <div className='mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed bg-muted/20 px-4 py-3 text-xs text-muted-foreground'>
          <span>
            {zh
              ? '快捷键：/ 选 Process · @ 找资源 · ↑↓ 移动 · Alt+↑↓ 重排 · Tab 浏览 · Cmd/Ctrl+Enter 保存'
              : 'Shortcuts: / Process · @ resources · ↑↓ move · Alt+↑↓ reorder · Tab navigate · Cmd/Ctrl+Enter save'}
          </span>
          <button
            type='button'
            onClick={addStep}
            className='font-medium text-primary hover:underline'
          >
            + {zh ? '继续添加步骤' : 'Add another step'}
          </button>
        </div>
        {error && (
          <div
            role='alert'
            className='mt-4 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive'
          >
            {error}
          </div>
        )}
      </div>
    </form>
  );
}
