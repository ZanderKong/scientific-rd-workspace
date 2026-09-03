'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ArrowUpRight, FlaskConical, Plus, Search } from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';
import type { ResearchObject } from '@/lib/domain';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

function readableError(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : 'Request failed';
}

type SampleListProps = { zh: boolean };

export function SampleList({ zh }: SampleListProps) {
  const params = useSearchParams();
  const router = useRouter();
  const [projectId, setProjectId] = useState(params.get('project') ?? '');
  const [query, setQuery] = useState('');
  const [samples, setSamples] = useState<ResearchObject[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fromUrl = params.get('project');
    const saved = window.localStorage.getItem('scientific_workspace_project');
    const next = fromUrl ?? saved ?? '';
    if (next) setProjectId(next);
  }, [params]);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api
      .listObjects({
        kind: 'sample',
        project_scope_id: projectId,
        q: query.trim() || undefined,
        include_global: false,
        limit: 100
      })
      .then((items) => {
        setSamples(items);
        setError(null);
      })
      .catch((cause) => {
        setSamples([]);
        setError(readableError(cause));
      })
      .finally(() => setLoading(false));
  }, [projectId, query]);

  function goNew() {
    router.push(`/dashboard/samples/new${projectId ? `?project=${projectId}` : ''}`);
  }

  return (
    <main className='min-h-full bg-[radial-gradient(circle_at_80%_0%,color-mix(in_oklch,var(--primary)_11%,transparent),transparent_25rem)]'>
      <div className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
        <div className='mb-8 flex flex-wrap items-end justify-between gap-4'>
          <div>
            <p className='font-mono text-[10px] uppercase tracking-[0.22em] text-primary'>
              Sample-first / records
            </p>
            <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
              <FlaskConical className='size-7 text-primary' />
              {zh ? 'Samples' : 'Samples'}
            </h1>
            <p className='mt-2 max-w-xl text-sm leading-6 text-muted-foreground'>
              {zh
                ? '以人实际记录的样品为入口，查看每个步骤、资源使用值与当前数据。'
                : 'Start from the record a researcher actually makes: steps, resource-use values, and current data.'}
            </p>
          </div>
          <Button size='lg' onClick={goNew} disabled={!projectId}>
            <Plus /> {zh ? '新建 Sample' : 'New Sample'}
          </Button>
        </div>

        <div className='mb-5 flex flex-wrap items-center gap-3 rounded-2xl border bg-card/70 p-3'>
          <div className='relative min-w-[16rem] flex-1'>
            <Search className='pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground' />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={zh ? '搜索 Sample 标题或编号…' : 'Search Sample title or code…'}
              className='h-9 pl-9 bg-background/70'
              aria-label={zh ? '搜索 Samples' : 'Search Samples'}
            />
          </div>
          <span className='rounded-full bg-muted px-3 py-1.5 font-mono text-xs text-muted-foreground'>
            {samples.length} {zh ? 'records' : 'records'}
          </span>
        </div>

        {!projectId ? (
          <div className='rounded-[1.4rem] border border-dashed bg-card/60 px-6 py-16 text-center text-sm text-muted-foreground'>
            {zh ? '请先在左侧选择 Project Scope。' : 'Choose a Project Scope in the sidebar first.'}
          </div>
        ) : loading ? (
          <div className='py-16 text-center text-sm text-muted-foreground'>
            {zh ? '正在读取 Sample records…' : 'Reading Sample records…'}
          </div>
        ) : error ? (
          <div
            role='alert'
            className='rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-5 text-sm text-destructive'
          >
            {error}
          </div>
        ) : samples.length === 0 ? (
          <div className='rounded-[1.4rem] border border-dashed bg-card/60 px-6 py-16 text-center'>
            <p className='text-sm text-muted-foreground'>
              {zh ? '当前 Project 还没有 Sample。' : 'No Samples in this Project yet.'}
            </p>
            <Button className='mt-4' onClick={goNew}>
              <Plus /> {zh ? '开始第一条记录' : 'Start the first record'}
            </Button>
          </div>
        ) : (
          <div className='overflow-hidden rounded-[1.4rem] border bg-card/70'>
            <div className='grid grid-cols-[minmax(0,1fr)_7rem_8rem_2rem] gap-3 border-b bg-muted/25 px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground md:grid-cols-[minmax(0,1fr)_8rem_9rem_2rem]'>
              <span>{zh ? 'Sample record' : 'Sample record'}</span>
              <span>{zh ? '状态' : 'Status'}</span>
              <span>{zh ? '更新时间' : 'Updated'}</span>
              <span />
            </div>
            <div>
              {samples.map((sample) => (
                <Link
                  key={sample.id}
                  href={`/dashboard/samples/${sample.id}?project=${projectId}`}
                  className='group grid grid-cols-[minmax(0,1fr)_7rem_8rem_2rem] items-center gap-3 border-b px-4 py-4 transition last:border-b-0 hover:bg-muted/35 md:grid-cols-[minmax(0,1fr)_8rem_9rem_2rem]'
                >
                  <span className='min-w-0'>
                    <span className='block truncate text-sm font-semibold group-hover:text-primary'>
                      {sample.title}
                    </span>
                    <span className='mt-1 block font-mono text-[10px] text-muted-foreground'>
                      {sample.code}
                    </span>
                  </span>
                  <span className='text-xs text-muted-foreground'>{sample.status}</span>
                  <span className='text-xs text-muted-foreground'>
                    {new Date(sample.updated_at).toLocaleDateString(zh ? 'zh-CN' : 'en-US')}
                  </span>
                  <ArrowUpRight className='size-4 text-muted-foreground transition group-hover:text-primary' />
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
