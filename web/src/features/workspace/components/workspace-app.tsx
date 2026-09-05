'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { ResearchObject, ResearchObjectKind } from '@/lib/domain';
import { Button } from '@/components/ui/button';

const meta: Record<ResearchObjectKind, { zh: string; en: string; path: string }> = {
  research_object: { zh: 'Research Object', en: 'Research Object', path: 'research-objects' },
  process_definition: { zh: '过程定义', en: 'Process Definition', path: 'processes' },
  data: { zh: '数据', en: 'Data', path: 'data' },
  experiment: { zh: '实验', en: 'Experiment', path: 'experiments' },
  project: { zh: '项目', en: 'Project', path: 'projects' },
  view: { zh: '视图', en: 'View', path: 'views' },
  claim: { zh: '论断', en: 'Claim', path: 'claims' }
};

const card = 'rounded-2xl border bg-card/80 p-5 shadow-xs';
const input = 'h-9 w-full rounded-md border bg-background px-3 text-sm';

function errorText(error: unknown) {
  return error instanceof ApiError || error instanceof Error ? error.message : 'Request failed';
}

export function objectPath(object: Pick<ResearchObject, 'id' | 'kind'>) {
  return `/dashboard/${meta[object.kind].path}/${object.id}`;
}

function ObjectCard({ object }: { object: ResearchObject }) {
  return (
    <Link href={objectPath(object)} className={`${card} block transition hover:border-primary`}>
      <div className='flex items-start justify-between gap-3'>
        <div className='min-w-0'>
          <p className='font-mono text-[10px] text-muted-foreground'>{object.code}</p>
          <h2 className='mt-1 truncate text-base font-semibold'>{object.title}</h2>
        </div>
        <span className='rounded-full border px-2 py-1 text-[11px] text-muted-foreground'>{object.status}</span>
      </div>
      <div className='mt-3 flex flex-wrap gap-1'>
        {object.tags.map((tag) => <span key={tag} className='rounded bg-muted px-2 py-1 text-[10px] text-muted-foreground'>{tag}</span>)}
      </div>
    </Link>
  );
}

function CreateObject({ kind, tag, projectId, onCreated }: { kind: ResearchObjectKind; tag?: string; projectId?: string; onCreated: (object: ResearchObject) => void }) {
  const [title, setTitle] = useState('');
  const [tags, setTags] = useState(tag ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const payload = { kind, title: title.trim(), project_scope_id: projectId ?? null, tags: tags.split(',').map((item) => item.trim()).filter(Boolean) };
      const object = kind === 'process_definition'
        ? (await api.createProcessDefinition({ ...payload, execution_field_definitions: {} })).process_definition
        : kind === 'view'
          ? (await api.createView({ project_scope_id: projectId, title: title.trim(), config: {}, data_ids: [] })).view
          : kind === 'claim'
            ? (await api.createClaim({ project_scope_id: projectId, title: title.trim(), statement: `Draft claim: ${title.trim()}` })).claim
            : await api.createObject(payload);
      onCreated(object);
      setTitle('');
    } catch (cause) { setError(errorText(cause)); } finally { setSaving(false); }
  }
  return (
    <form onSubmit={submit} className={`${card} grid gap-3 md:grid-cols-[1fr_1fr_auto]`}>
      <input required className={input} value={title} onChange={(event) => setTitle(event.target.value)} placeholder='Title' />
      <input className={input} value={tags} onChange={(event) => setTags(event.target.value)} placeholder='Tags, comma separated' />
      <Button type='submit' disabled={saving || !title.trim()}>{saving ? 'Saving…' : 'Create'}</Button>
      {error && <p className='text-sm text-destructive md:col-span-full'>{error}</p>}
    </form>
  );
}

function ObjectList({ kind, tag }: { kind: ResearchObjectKind; tag?: string }) {
  const searchParams = useSearchParams();
  const projectId = searchParams.get('project') ?? undefined;
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<ResearchObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const router = useRouter();
  useEffect(() => {
    setLoading(true);
    api.listObjects({ kind, tag, q: query || undefined, project_scope_id: projectId, include_global: true, limit: 100 })
      .then(setItems).catch((cause) => setError(errorText(cause))).finally(() => setLoading(false));
  }, [kind, projectId, query, tag]);
  const label = meta[kind].en;
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <div className='mb-6 flex flex-wrap items-start justify-between gap-3'>
        <div><p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>v0.3 domain</p><h1 className='mt-2 text-3xl font-semibold'>{label}</h1><p className='mt-2 text-sm text-muted-foreground'>Canonical objects and typed records.</p></div>
        <Button onClick={() => setCreating((value) => !value)}>{creating ? 'Close' : 'Create'}</Button>
      </div>
      {creating && <div className='mb-5'><CreateObject kind={kind} tag={tag} projectId={projectId} onCreated={(object) => { setCreating(false); router.push(objectPath(object)); }} /></div>}
      <input className={`${input} mb-5`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder='Search title, code, tags…' />
      {loading ? <p className='py-12 text-center text-sm text-muted-foreground'>Loading…</p> : error ? <p className='rounded-xl border border-destructive/30 p-4 text-sm text-destructive'>{error}</p> : items.length === 0 ? <p className='rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground'>No records.</p> : <div className='grid gap-3 md:grid-cols-2'>{items.map((object) => <ObjectCard key={object.id} object={object} />)}</div>}
    </main>
  );
}

function ObjectDetail({ objectId }: { objectId: string }) {
  const [object, setObject] = useState<ResearchObject | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.getObject(objectId).then(setObject).catch((cause) => setError(errorText(cause))); }, [objectId]);
  if (error) return <main className='mx-auto max-w-[1320px] p-8 text-destructive'>{error}</main>;
  if (!object) return <main className='mx-auto max-w-[1320px] p-8 text-muted-foreground'>Loading…</main>;
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>{object.kind}</p>
      <h1 className='mt-2 text-3xl font-semibold'>{object.title}</h1>
      <p className='mt-2 font-mono text-xs text-muted-foreground'>{object.code} · {object.status}</p>
      <section className={`${card} mt-6 grid gap-5 md:grid-cols-2`}>
        <div><h2 className='font-semibold'>Tags</h2><div className='mt-2 flex flex-wrap gap-2'>{object.tags.map((tag) => <span key={tag} className='rounded-full bg-muted px-2.5 py-1 text-xs'>{tag}</span>)}</div></div>
        <div><h2 className='font-semibold'>Properties</h2><pre className='mt-2 overflow-auto rounded-lg bg-muted/40 p-3 text-xs'>{JSON.stringify(object.properties_jsonb, null, 2)}</pre></div>
      </section>
    </main>
  );
}

function Overview() {
  const [summary, setSummary] = useState<import('@/lib/domain').WorkspaceSummary | null>(null);
  useEffect(() => { api.getWorkspaceSummary().then(setSummary).catch(() => setSummary(null)); }, []);
  return <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'><p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>Scientific workspace</p><h1 className='mt-2 text-3xl font-semibold'>v0.3 Domain Overview</h1><div className='mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>{Object.entries(summary?.counts ?? {}).map(([key, value]) => <div key={key} className={card}><p className='text-xs text-muted-foreground'>{key}</p><p className='mt-2 text-3xl font-semibold'>{value}</p></div>)}</div></main>;
}

export function WorkspaceApp({ view, kind, objectId, tag }: { view: 'list' | 'detail' | 'overview'; kind?: ResearchObjectKind; objectId?: string; tag?: string }) {
  if (view === 'overview') return <Overview />;
  if (view === 'detail' && objectId) return <ObjectDetail objectId={objectId} />;
  return <ObjectList kind={kind ?? 'research_object'} tag={tag} />;
}
