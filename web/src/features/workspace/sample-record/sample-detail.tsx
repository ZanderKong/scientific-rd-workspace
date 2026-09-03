'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Edit3,
  ExternalLink,
  FlaskConical,
  GitBranch,
  RotateCcw
} from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';
import type { ResearchObject, SampleRecordResource } from '@/lib/domain';
import { Button } from '@/components/ui/button';
import { SampleComposer } from './sample-composer';
import { objectKindLabel, usageSchema, usageValueText } from './model';

type SampleDetailProps = { sampleId: string; zh: boolean };

function readableError(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : 'Request failed';
}

function resourceClass(kind: ResearchObject['kind']) {
  return kind === 'material'
    ? 'border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100'
    : kind === 'equipment'
      ? 'border-sky-500/30 bg-sky-500/10 text-sky-900 dark:text-sky-100'
      : 'border-violet-500/30 bg-violet-500/10 text-violet-900 dark:text-violet-100';
}

function ResourceInspection({ resource, zh }: { resource: SampleRecordResource; zh: boolean }) {
  const [open, setOpen] = useState(false);
  const fields = usageSchema(resource.object).fields;
  return (
    <div className='relative'>
      <button
        type='button'
        onClick={() => setOpen((value) => !value)}
        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition hover:-translate-y-px ${resourceClass(resource.object.kind)}`}
        data-testid='detail-resource-token'
      >
        <span className='size-1.5 rounded-full bg-current/60' />
        {resource.object.title}
        <span className='font-mono text-[10px] opacity-60'>{resource.object.code}</span>
      </button>
      {open && (
        <div
          className='absolute top-full left-0 z-20 mt-2 w-72 rounded-2xl border bg-popover p-4 text-xs shadow-xl'
          data-testid='detail-resource-preview'
        >
          <div className='flex items-start justify-between gap-2'>
            <div>
              <p className='font-semibold'>{resource.object.title}</p>
              <p className='mt-1 font-mono text-[10px] text-muted-foreground'>
                {resource.object.code}
              </p>
            </div>
            <span className='rounded-full bg-muted px-2 py-0.5'>
              {objectKindLabel(resource.object.kind, zh)}
            </span>
          </div>
          <p className='mt-3 leading-5 text-muted-foreground'>
            {zh ? '身份对象' : 'Identity object'} · {resource.object.type_label_zh}
          </p>
          <div className='mt-3 space-y-1 border-t pt-3'>
            {fields.map((field) => (
              <div key={field.key} className='flex justify-between gap-3 text-muted-foreground'>
                <span>{field.label}</span>
                <span className='font-mono text-foreground'>
                  {usageValueText(resource.usage_values[field.key]) || '—'}{' '}
                  {resource.usage_values[field.key]?.unit ?? field.default_unit ?? ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function RecordView({
  record,
  zh,
  onEdit,
  onClone
}: {
  record: NonNullable<Awaited<ReturnType<typeof api.getSampleRecord>>>;
  zh: boolean;
  onEdit: () => void;
  onClone: () => void;
}) {
  return (
    <main className='min-h-full bg-[radial-gradient(circle_at_82%_0%,color-mix(in_oklch,var(--primary)_10%,transparent),transparent_26rem)]'>
      <div className='mx-auto w-full max-w-[1180px] px-4 py-7 md:px-8 md:py-10'>
        <Link
          href='/dashboard/samples'
          className='mb-5 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground'
        >
          <ArrowLeft className='size-3' /> {zh ? '全部 Samples' : 'All Samples'}
        </Link>
        <header className='mb-8 flex flex-wrap items-start justify-between gap-5'>
          <div>
            <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
              Sample record / {record.sample.code}
            </p>
            <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
              <FlaskConical className='size-7 text-primary' />
              {record.sample.title}
            </h1>
            <div className='mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground'>
              <span className='rounded-full border px-2 py-1'>{record.sample.status}</span>
              <span>
                {record.steps.length} {zh ? '个 Process step' : 'Process steps'}
              </span>
              <span>·</span>
              <span>
                {zh ? '最后更新' : 'Updated'}{' '}
                {new Date(record.sample.updated_at).toLocaleString(zh ? 'zh-CN' : 'en-US')}
              </span>
            </div>
          </div>
          <div className='flex flex-wrap gap-2'>
            <Button variant='outline' onClick={onClone}>
              <RotateCcw /> {zh ? '基于此样品新建' : 'Create from this Sample'}
            </Button>
            {record.editable && (
              <Button onClick={onEdit}>
                <Edit3 /> {zh ? '编辑记录' : 'Edit record'}
              </Button>
            )}
          </div>
        </header>

        {!record.editable && (
          <div className='mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/[0.07] px-4 py-4'>
            <p className='text-sm font-semibold text-amber-900 dark:text-amber-100'>
              {zh
                ? '这是可查看但不可安全编辑的复杂图结构'
                : 'This graph is viewable but not safely editable'}
            </p>
            <p className='mt-1 text-xs leading-5 text-muted-foreground'>
              {zh
                ? 'Composer 不会把分支或外部依赖压平成线性记录。'
                : 'The Composer will not flatten branches or external dependencies into a linear record.'}
            </p>
            <ul className='mt-2 list-disc pl-5 text-xs text-muted-foreground'>
              {record.edit_blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          </div>
        )}

        <div className='relative space-y-4'>
          <div className='absolute top-7 bottom-7 left-4 w-px bg-border md:left-5' />
          {record.steps.map((step) => (
            <section
              key={step.process.id}
              className='relative grid gap-4 md:grid-cols-[2.5rem_minmax(0,1fr)]'
            >
              <div className='relative z-10 flex size-8 items-center justify-center rounded-xl border bg-background font-mono text-[10px] font-semibold md:size-10'>
                {String(step.ordinal + 1).padStart(2, '0')}
              </div>
              <div className='rounded-[1.35rem] border bg-card/75 p-4 md:p-5'>
                <div className='flex flex-wrap items-start justify-between gap-3'>
                  <div>
                    <p className='font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground'>
                      Process
                    </p>
                    <h2 className='mt-1 text-lg font-semibold'>{step.process.title}</h2>
                  </div>
                  <span className='rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground'>
                    {step.process.status}
                  </span>
                </div>
                <div className='mt-4 flex flex-wrap gap-2'>
                  {step.resources.map((resource) => (
                    <ResourceInspection key={resource.relation_id} resource={resource} zh={zh} />
                  ))}
                  {step.resources.length === 0 && (
                    <span className='text-xs text-muted-foreground'>
                      {zh ? '无附加资源' : 'No attached resources'}
                    </span>
                  )}
                </div>
                <div className='mt-4 grid gap-3 lg:grid-cols-2'>
                  <div className='rounded-xl bg-muted/35 p-3'>
                    <p className='mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground'>
                      {zh ? 'Process 参数' : 'Process parameters'}
                    </p>
                    <pre className='whitespace-pre-wrap break-words font-mono text-xs leading-5 text-foreground'>
                      {JSON.stringify(
                        (step.process.properties_jsonb.parameters as object | undefined) ?? {},
                        null,
                        2
                      )}
                    </pre>
                  </div>
                  <div className='rounded-xl bg-muted/35 p-3'>
                    <p className='mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground'>
                      {zh ? '本步说明' : 'Step notes'}
                    </p>
                    <p className='text-xs leading-5 text-muted-foreground'>
                      {step.process.content_document
                        .map((item) => String(item.text ?? ''))
                        .join(' ') || (zh ? '暂无补充说明。' : 'No additional notes.')}
                    </p>
                  </div>
                </div>
              </div>
            </section>
          ))}
        </div>

        <section className='mt-8 rounded-[1.35rem] border bg-card/70 p-4 md:p-5'>
          <div className='flex items-center gap-2'>
            <GitBranch className='size-4 text-primary' />
            <h2 className='text-base font-semibold'>
              {zh ? '当前 Data / provenance' : 'Current Data / provenance'}
            </h2>
          </div>
          <p className='mt-1 text-xs text-muted-foreground'>
            {zh
              ? '只显示由这条记录中的 Process 直接产生的 Data；前驱 Sample 保持为 lineage 输入。'
              : 'Only Data directly produced by Processes in this record is shown; precursor Samples remain lineage inputs.'}
          </p>
          {record.data.length ? (
            <div className='mt-4 grid gap-2 md:grid-cols-2'>
              {record.data.map((item) => (
                <Link
                  key={item.id}
                  href={`/dashboard/data/${item.id}`}
                  className='flex items-center justify-between rounded-xl border px-3 py-3 text-sm hover:bg-muted'
                >
                  <span>
                    <span className='font-mono text-[10px] text-muted-foreground'>{item.code}</span>
                    <span className='ml-2 font-medium'>{item.title}</span>
                  </span>
                  <ExternalLink className='size-3.5 text-muted-foreground' />
                </Link>
              ))}
            </div>
          ) : (
            <p className='mt-4 rounded-xl border border-dashed px-3 py-4 text-xs text-muted-foreground'>
              {zh ? '当前尚无直接 Data 输出。' : 'No direct Data output yet.'}
            </p>
          )}
        </section>
        <div className='mt-6 flex justify-end'>
          <Link
            href={`/dashboard/samples/new?project=${record.sample.project_scope_id}&from=${record.sample.id}`}
            className='inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline'
          >
            {zh ? '打开为新记录草稿' : 'Open as a new record draft'}{' '}
            <ArrowRight className='size-3' />
          </Link>
        </div>
      </div>
    </main>
  );
}

export function SampleDetail({ sampleId, zh }: SampleDetailProps) {
  const router = useRouter();
  const params = useSearchParams();
  const [record, setRecord] = useState<Awaited<ReturnType<typeof api.getSampleRecord>> | null>(
    null
  );
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true);
    api
      .getSampleRecord(sampleId)
      .then(setRecord)
      .catch((cause) => setError(readableError(cause)))
      .finally(() => setLoading(false));
  }, [sampleId]);
  if (loading)
    return (
      <div className='px-8 py-16 text-center text-sm text-muted-foreground'>
        {zh ? '正在读取 Sample Record…' : 'Reading Sample Record…'}
      </div>
    );
  if (error || !record)
    return (
      <div
        role='alert'
        className='m-8 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-5 text-sm text-destructive'
      >
        {error ?? (zh ? '未找到 Sample。' : 'Sample not found.')}
      </div>
    );
  if (editing)
    return (
      <SampleComposer
        projectId={record.sample.project_scope_id}
        initialRecord={record}
        mode='edit'
        zh={zh}
        onCancel={() => setEditing(false)}
        onSaved={(next) => {
          setRecord(next);
        }}
      />
    );
  return (
    <RecordView
      record={record}
      zh={zh}
      onEdit={() => setEditing(true)}
      onClone={() =>
        router.push(
          `/dashboard/samples/new?project=${params.get('project') ?? record.sample.project_scope_id}&from=${record.sample.id}`
        )
      }
    />
  );
}
