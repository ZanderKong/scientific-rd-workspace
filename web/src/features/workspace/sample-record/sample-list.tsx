'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { ResearchObject } from '@/lib/domain';
import { useProjectScope } from '../project-scope/project-scope-context';

export function SampleList() {
  const { activeProjectId } = useProjectScope();
  const [items, setItems] = useState<ResearchObject[]>([]);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.listObjects({ kind: 'research_object', tag: '样品', q: query || undefined, project_scope_id: activeProjectId ?? undefined, include_global: true, limit: 100 }).then(setItems).catch((cause) => setError(cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed')); }, [activeProjectId, query]);
  return <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'><div className='mb-6 flex items-start justify-between gap-3'><div><p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>Research Object tag</p><h1 className='mt-2 text-3xl font-semibold'>Samples</h1><p className='mt-2 text-sm text-muted-foreground'>Samples are unified Research Objects grouped by tags.</p></div><Link href='/dashboard/samples/new' className='rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground'>Create sample</Link></div><input className='mb-5 h-9 w-full rounded-md border bg-background px-3 text-sm' value={query} onChange={(event) => setQuery(event.target.value)} placeholder='Search sample title, code, tags…' />{error ? <p className='text-sm text-destructive'>{error}</p> : <div className='grid gap-3 md:grid-cols-2'>{items.map((item) => <Link key={item.id} href={`/dashboard/samples/${item.id}`} className='rounded-2xl border bg-card/80 p-5 hover:border-primary'><p className='font-mono text-[10px] text-muted-foreground'>{item.code}</p><h2 className='mt-1 font-semibold'>{item.title}</h2><div className='mt-3 flex flex-wrap gap-1'>{item.tags.map((tag) => <span key={tag} className='rounded bg-muted px-2 py-1 text-[10px]'>{tag}</span>)}</div></Link>)}</div>}</main>;
}
