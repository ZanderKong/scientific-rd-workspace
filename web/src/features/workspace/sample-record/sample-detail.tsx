'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { SampleRecord } from '@/lib/domain';

export function SampleDetail({ sampleId }: { sampleId: string }) {
  const [record, setRecord] = useState<SampleRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.getSampleRecord(sampleId).then(setRecord).catch((cause) => setError(cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed')); }, [sampleId]);
  if (error) return <main className='mx-auto max-w-[1320px] p-8 text-destructive'>{error}</main>;
  if (!record) return <main className='mx-auto max-w-[1320px] p-8 text-muted-foreground'>Loading…</main>;
  return <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'><Link href='/dashboard/samples' className='text-sm text-muted-foreground hover:text-foreground'>← Samples</Link><div className='mt-5 flex flex-wrap items-start justify-between gap-3'><div><p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>Sample projection</p><h1 className='mt-2 text-3xl font-semibold'>{record.sample.title}</h1><p className='mt-2 font-mono text-xs text-muted-foreground'>{record.sample.code} · {record.record_sha256.slice(0, 16)}…</p></div><span className='rounded-full border px-3 py-1 text-xs'>{record.sample.status}</span></div><section className='mt-7 space-y-3'><h2 className='text-lg font-semibold'>Process Executions</h2>{record.steps.map(({ execution, ordinal }) => <article key={execution.id} className='rounded-2xl border bg-card/80 p-5'><div className='flex items-center justify-between gap-3'><h3 className='font-semibold'>Step {ordinal + 1} · {execution.title_snapshot ?? execution.process_definition_id}</h3><span className='rounded-full bg-muted px-2 py-1 text-xs'>{execution.status}</span></div><p className='mt-2 text-xs text-muted-foreground'>Definition version {execution.process_definition_version_id}</p><div className='mt-4 grid gap-2 md:grid-cols-2'>{execution.object_bindings.filter((binding) => binding.role !== 'sample_record').map((binding) => <div key={binding.id} className='rounded-lg border px-3 py-2 text-sm'><span className='text-muted-foreground'>{binding.direction}</span> · {binding.object.title}{binding.role ? ` · ${binding.role}` : ''}</div>)}{execution.data_bindings.map((binding) => <div key={binding.id} className='rounded-lg border px-3 py-2 text-sm'><span className='text-muted-foreground'>{binding.direction}</span> · {binding.data.title}</div>)}</div></article>)}</section><section className='mt-7'><h2 className='text-lg font-semibold'>Subject Data</h2><div className='mt-3 grid gap-2 md:grid-cols-2'>{record.data.map((item) => <Link key={item.id} href={`/dashboard/data/${item.id}`} className='rounded-xl border px-3 py-3 hover:border-primary'>{item.title}</Link>)}</div></section></main>;
}
