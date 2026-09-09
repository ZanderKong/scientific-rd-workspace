'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { LibraryBig, Plus, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api, ApiError } from '@/lib/api-client';
import type { ProcessDefinition, ResearchObject, ResourceRole } from '@/lib/domain';

const roleLabels: Record<ResourceRole, string> = {
  material: '原料',
  equipment: '设备',
  process: '过程'
};

const roleStyles: Record<ResourceRole, string> = {
  material: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  equipment: 'bg-sky-500/10 text-sky-700 dark:text-sky-300',
  process: 'bg-violet-500/10 text-violet-700 dark:text-violet-300'
};

type ResourceRow = {
  id: string;
  title: string;
  code: string;
  status: string;
  role: ResourceRole;
  href: string;
  updated_at: string;
  project_scope_id: string | null;
};

function errorText(error: unknown) {
  return error instanceof ApiError || error instanceof Error ? error.message : '加载失败';
}

function roleForObject(object: ResearchObject): ResourceRole | null {
  if (object.authoring_kind === 'sample' || object.authoring_kind === 'data') return null;
  if (object.resource_role) return object.resource_role;
  if (object.tags.some((tag) => tag.trim().toLocaleLowerCase() === '设备')) return 'equipment';
  if (object.tags.some((tag) => tag.trim().toLocaleLowerCase() === '原料')) return 'material';
  if (object.tags.some((tag) => tag.trim().toLocaleLowerCase() === '过程')) return 'process';
  return object.kind === 'process_definition' ? 'process' : null;
}

export function ResourceWorkspace() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get('project') ?? undefined;
  const [query, setQuery] = useState('');
  const [role, setRole] = useState<'all' | ResourceRole>('all');
  const [rows, setRows] = useState<ResourceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState('');
  const [newRole, setNewRole] = useState<ResourceRole>('material');
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      api.listObjects({
        kind: 'research_object',
        q: query || undefined,
        project_scope_id: projectId,
        include_global: true,
        limit: 200,
        signal: controller.signal
      }),
      api.listProcessDefinitions({
        q: query || undefined,
        project_scope_id: projectId,
        limit: 200,
        signal: controller.signal
      })
    ])
      .then(([objects, processes]) => {
        const objectRows = objects.flatMap((object) => {
          const itemRole = roleForObject(object);
          if (!itemRole) return [];
          return [{
            id: object.id,
            title: object.title,
            code: object.code,
            status: object.status,
            role: itemRole,
            href: `/dashboard/research-objects/${object.id}`,
            updated_at: object.updated_at,
            project_scope_id: object.project_scope_id
          }];
        });
        const processRows = processes.map((item: ProcessDefinition) => ({
          id: item.process_definition.id,
          title: item.process_definition.title,
          code: item.process_definition.code,
          status: item.process_definition.status,
          role: 'process' as const,
          href: `/dashboard/processes/${item.process_definition.id}`,
          updated_at: item.process_definition.updated_at,
          project_scope_id: item.process_definition.project_scope_id
        }));
        setRows(
          [...objectRows, ...processRows].toSorted((a, b) =>
            b.updated_at.localeCompare(a.updated_at)
          )
        );
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(errorText(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [projectId, query]);

  const visibleRows = useMemo(
    () => rows.filter((item) => role === 'all' || item.role === role),
    [role, rows]
  );

  async function createResource(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    setCreateError(null);
    try {
      const created = newRole === 'process'
        ? (await api.createProcessDefinition({
            project_scope_id: projectId ?? null,
            title: title.trim(),
            tags: [],
            properties_jsonb: {},
            execution_field_definitions: { fields: [] }
          }, crypto.randomUUID())).process_definition
        : await api.createObject({
            kind: 'research_object',
            project_scope_id: projectId ?? null,
            title: title.trim(),
            resource_role: newRole,
            tags: [],
            properties_jsonb: {},
            process_field_definitions: { fields: [] }
          }, crypto.randomUUID());
      window.location.assign(newRole === 'process'
        ? `/dashboard/processes/${created.id}`
        : `/dashboard/research-objects/${created.id}`);
    } catch (cause) {
      setCreateError(errorText(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className='mx-auto w-full max-w-[1200px] px-5 py-8 md:px-10 md:py-12'>
      <div className='mb-8 flex flex-wrap items-end justify-between gap-4'>
        <div>
          <div className='mb-3 flex items-center gap-2 text-sm text-muted-foreground'>
            <LibraryBig className='size-4' />
            <span>项目资源</span>
          </div>
          <h1 className='text-3xl font-semibold tracking-tight'>资源</h1>
          <p className='mt-2 max-w-xl text-sm leading-6 text-muted-foreground'>
            统一管理可复用的原料、设备和过程。资源在记录中通过 @ 引用，过程仍保留自己的版本历史。
          </p>
        </div>
        <Button onClick={() => setCreating((value) => !value)}>
          <Plus className='size-4' />
          {creating ? '关闭' : '新建资源'}
        </Button>
      </div>

      {creating && (
        <form onSubmit={createResource} className='mb-8 rounded-2xl border bg-card p-5 shadow-sm'>
          <div className='grid gap-3 md:grid-cols-[1fr_180px_auto]'>
            <input
              className='h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring'
              placeholder='资源名称'
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
            <select
              className='h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring'
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as ResourceRole)}
            >
              {(Object.keys(roleLabels) as ResourceRole[]).map((item) => (
                <option key={item} value={item}>{roleLabels[item]}</option>
              ))}
            </select>
            <Button type='submit' disabled={saving || !title.trim()}>
              {saving ? '保存中…' : '创建'}
            </Button>
          </div>
          {createError && <p className='mt-3 text-sm text-destructive'>{createError}</p>}
        </form>
      )}

      <div className='mb-4 flex flex-wrap gap-3'>
        <label className='relative min-w-[240px] flex-1'>
          <Search className='absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground' />
          <input
            className='h-10 w-full rounded-lg border bg-background ps-9 pe-3 text-sm outline-none focus:ring-2 focus:ring-ring'
            placeholder='搜索资源名称或编号'
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className='flex rounded-lg border bg-card p-1'>
          {(['all', 'material', 'equipment', 'process'] as const).map((item) => (
            <button
              key={item}
              type='button'
              className={`rounded-md px-3 py-1.5 text-sm transition ${role === item ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground'}`}
              onClick={() => setRole(item)}
            >
              {item === 'all' ? '全部' : roleLabels[item]}
            </button>
          ))}
        </div>
      </div>

      {loading ? <p className='py-16 text-center text-sm text-muted-foreground'>正在加载资源…</p> : null}
      {!loading && error ? (
        <div className='rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive'>{error}</div>
      ) : null}
      {!loading && !error && visibleRows.length === 0 ? (
        <div className='rounded-2xl border border-dashed p-14 text-center text-sm text-muted-foreground'>
          没有符合条件的资源。可以直接新建一个原料、设备或过程。
        </div>
      ) : null}
      {!loading && !error && visibleRows.length > 0 ? (
        <div className='overflow-hidden rounded-2xl border bg-card'>
          <div className='grid grid-cols-[minmax(0,1fr)_110px_100px_130px] gap-4 border-b bg-muted/30 px-5 py-3 text-xs font-medium text-muted-foreground'>
            <span>资源</span><span>分类</span><span>状态</span><span>更新时间</span>
          </div>
          {visibleRows.map((item) => (
            <Link key={`${item.role}-${item.id}`} href={item.href} className='grid grid-cols-[minmax(0,1fr)_110px_100px_130px] items-center gap-4 border-b px-5 py-4 text-sm last:border-b-0 hover:bg-muted/30'>
              <span className='min-w-0'><span className='block truncate font-medium'>{item.title}</span><span className='mt-1 block truncate font-mono text-xs text-muted-foreground'>{item.code}</span></span>
              <span className={`w-fit rounded-full px-2 py-1 text-xs ${roleStyles[item.role]}`}>{roleLabels[item.role]}</span>
              <span className='text-muted-foreground'>{item.status}</span>
              <span className='text-xs text-muted-foreground'>{new Date(item.updated_at).toLocaleDateString('zh-CN')}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </main>
  );
}
