'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import { buildSampleLineageTree, projectXYToPolyline, type LineageTreeNode } from '../presentation';
import { RichNoteEditor } from './rich-note-editor';
import type {
  Attachment,
  ExperimentContext,
  ImportPreview,
  JsonObject,
  LineageContext,
  ObjectRelation,
  ObjectRevision,
  ProcessComposition,
  ProcessCompositionItem,
  ResearchObject,
  ResearchObjectKind,
  SampleContext
} from '@/lib/domain';

const KIND_META: Record<
  ResearchObjectKind,
  { zh: string; en: string; prefix: string; path: string }
> = {
  project: { zh: '项目', en: 'Project', prefix: 'PRJ', path: 'projects' },
  experiment: { zh: '实验', en: 'Experiment', prefix: 'EXP', path: 'experiments' },
  sample: { zh: '样品', en: 'Sample', prefix: 'SMP', path: 'samples' },
  process: { zh: '过程 / 操作', en: 'Process', prefix: 'PRC', path: 'processes' },
  data: { zh: '数据 / 测试结果', en: 'Data', prefix: 'DAT', path: 'data' },
  material: { zh: '原料 / 试剂', en: 'Material', prefix: 'MAT', path: 'materials' },
  equipment: { zh: '设备', en: 'Equipment', prefix: 'EQP', path: 'equipment' }
};

const pageClass = 'mx-auto w-full max-w-[1440px] px-4 py-5 md:px-7 md:py-7';
const cardClass = 'rounded-xl border bg-card p-4 shadow-xs';
const inputClass =
  'h-9 w-full rounded-md border bg-background px-3 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring';
const buttonClass =
  'inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50';
const secondaryButtonClass =
  'inline-flex h-9 items-center justify-center rounded-md border bg-background px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50';

function kindLabel(kind: ResearchObjectKind, locale: string) {
  const meta = KIND_META[kind];
  return locale === 'zh-CN' ? meta.zh : meta.en;
}

function objectHref(object: Pick<ResearchObject, 'id' | 'kind'>) {
  return `/dashboard/${KIND_META[object.kind].path}/${object.id}`;
}

function readableError(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : 'Request failed';
}

function useRemote<T>(key: string, loader: (() => Promise<T>) | null) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>({
    data: null,
    loading: Boolean(loader),
    error: null
  });
  useEffect(() => {
    let alive = true;
    if (!key) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    const activeLoader = loaderRef.current;
    if (!activeLoader) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    setState({ data: null, loading: true, error: null });
    activeLoader()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch(
        (error) => alive && setState({ data: null, loading: false, error: readableError(error) })
      );
    return () => {
      alive = false;
    };
  }, [key]);
  return state;
}

function PageState({
  loading,
  error,
  empty
}: {
  loading?: boolean;
  error?: string | null;
  empty?: string;
}) {
  const t = useTranslations('Common');
  if (loading)
    return (
      <div className='flex min-h-40 items-center justify-center text-sm text-muted-foreground'>
        {t('loading')}
      </div>
    );
  if (error)
    return (
      <div className={`${cardClass} border-destructive/40 text-sm text-destructive`}>{error}</div>
    );
  if (empty)
    return (
      <div className={`${cardClass} py-12 text-center text-sm text-muted-foreground`}>{empty}</div>
    );
  return null;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className='rounded-full border px-2 py-0.5 text-xs text-muted-foreground'>
      {status.replaceAll('_', ' ')}
    </span>
  );
}

function ObjectLink({ object, locale: _locale }: { object: ResearchObject; locale?: string }) {
  return (
    <Link
      href={objectHref(object)}
      className='group flex min-w-0 items-center justify-between gap-3 rounded-lg border px-3 py-2 transition hover:bg-muted/60'
    >
      <span className='min-w-0'>
        <span className='font-mono text-xs text-muted-foreground'>{object.code}</span>
        <span className='ml-2 truncate text-sm font-medium group-hover:underline'>
          {object.title}
        </span>
      </span>
      <StatusBadge status={object.status} />
    </Link>
  );
}

function Section({
  title,
  description,
  children,
  action
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className='space-y-3'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h2 className='text-base font-semibold'>{title}</h2>
          {description && <p className='mt-1 text-xs text-muted-foreground'>{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function ObjectCreateForm({
  kind,
  scopeId,
  onCreated
}: {
  kind: ResearchObjectKind;
  scopeId?: string;
  onCreated: (object: ResearchObject) => void;
}) {
  const t = useTranslations('Workspace');
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState(
    kind === 'project' ? 'active' : kind === 'experiment' ? 'draft' : 'active'
  );
  const [properties, setProperties] = useState('{}');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    let parsed: JsonObject;
    try {
      parsed = JSON.parse(properties) as JsonObject;
    } catch {
      setError(t('invalidJson'));
      return;
    }
    setSaving(true);
    try {
      const created = await api.createObject({
        kind,
        title: title.trim(),
        status,
        project_scope_id: kind === 'project' ? null : (scopeId ?? null),
        properties_jsonb: parsed
      });
      setTitle('');
      setProperties('{}');
      onCreated(created);
    } catch (cause) {
      setError(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  return (
    <form
      onSubmit={submit}
      className={`${cardClass} grid gap-3 md:grid-cols-[1.4fr_0.7fr_1.5fr_auto] md:items-end`}
    >
      <label className='grid gap-1 text-xs font-medium'>
        {t('title')}
        <input
          required
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className={inputClass}
          placeholder={t('titlePlaceholder')}
        />
      </label>
      <label className='grid gap-1 text-xs font-medium'>
        {t('status')}
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className={inputClass}
        >
          <option value='active'>active</option>
          <option value='draft'>draft</option>
          <option value='planned'>planned</option>
          <option value='running'>running</option>
          <option value='completed'>completed</option>
          <option value='archived'>archived</option>
        </select>
      </label>
      <label className='grid gap-1 text-xs font-medium'>
        {t('properties')}
        <input
          value={properties}
          onChange={(event) => setProperties(event.target.value)}
          className={inputClass}
          aria-label={t('properties')}
        />
      </label>
      <button disabled={saving || !title.trim()} className={buttonClass}>
        {saving ? t('saving') : t('create')}
      </button>
      {error && <p className='text-xs text-destructive md:col-span-full'>{error}</p>}
    </form>
  );
}

function ObjectList({ kind }: { kind: ResearchObjectKind }) {
  const locale = useLocale();
  const t = useTranslations('Workspace');
  const searchParams = useSearchParams();
  const scopeId = searchParams.get('project');
  const [query, setQuery] = useState('');
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const router = useRouter();
  const isGlobalList = kind === 'project' || kind === 'material' || kind === 'equipment';
  const canList = isGlobalList || Boolean(scopeId);
  const resource = useRemote(
    `${kind}:${scopeId ?? ''}:${query}:${refresh}`,
    canList
      ? () =>
          api.listObjects({
            kind,
            q: query || undefined,
            project_scope_id: kind === 'project' ? undefined : (scopeId ?? undefined),
            include_global: isGlobalList
          })
      : null
  );
  const objects = resource.data ?? [];
  const title = kindLabel(kind, locale);
  const empty = canList ? t('emptyObjects', { kind: title }) : t('chooseProjectFirst');
  return (
    <div className={pageClass}>
      <div className='mb-6 flex flex-wrap items-start justify-between gap-4'>
        <div>
          <p className='font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground'>
            Research Object Graph
          </p>
          <h1 className='mt-2 text-2xl font-semibold tracking-tight'>{title}</h1>
          <p className='mt-1 text-sm text-muted-foreground'>
            {t('listDescription', { kind: title })}
          </p>
        </div>
        <button
          className={buttonClass}
          disabled={!canList}
          onClick={() => setCreating((value) => !value)}
        >
          {creating ? t('close') : `${t('create')} ${title}`}
        </button>
      </div>
      {creating && (
        <div className='mb-5'>
          <ObjectCreateForm
            kind={kind}
            scopeId={scopeId ?? undefined}
            onCreated={(object) => {
              setCreating(false);
              setRefresh((value) => value + 1);
              router.push(objectHref(object));
            }}
          />
        </div>
      )}
      <div className='mb-4 flex flex-wrap gap-2'>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className={`${inputClass} max-w-md`}
          placeholder={t('searchObjects')}
          aria-label={t('searchObjects')}
        />
        <span className='self-center text-xs text-muted-foreground'>
          {objects.length} {t('records')}
        </span>
      </div>
      <PageState
        loading={resource.loading}
        error={resource.error}
        empty={!resource.loading && !resource.error && objects.length === 0 ? empty : undefined}
      />
      {!resource.loading && !resource.error && objects.length > 0 && (
        <div className='grid gap-2'>
          {objects.map((object) => (
            <ObjectLink key={object.id} object={object} locale={locale} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectOverview({ projectId }: { projectId: string }) {
  const locale = useLocale();
  const t = useTranslations('Workspace');
  const project = useRemote(`project:${projectId}`, () => api.getObject(projectId));
  const summary = useRemote(`project-summary:${projectId}`, () => api.getProjectSummary(projectId));
  const recent = summary.data?.recent ?? [];
  const experiments = recent.filter((object) => object.kind === 'experiment');
  if (project.data && project.data.kind !== 'project')
    return (
      <div className={pageClass}>
        <PageState error={t('notFound')} />
      </div>
    );
  return (
    <div className={pageClass}>
      <PageState
        loading={project.loading || summary.loading}
        error={project.error || summary.error}
      />
      {project.data && (
        <>
          <div className='mb-7 flex flex-wrap items-start justify-between gap-4'>
            <div>
              <p className='font-mono text-xs text-muted-foreground'>
                {project.data.code} · Vault Scope
              </p>
              <h1 className='mt-2 text-2xl font-semibold'>{project.data.title}</h1>
              <p className='mt-2 max-w-2xl text-sm text-muted-foreground'>
                {String(project.data.properties_jsonb.description ?? t('noDescription'))}
              </p>
            </div>
            <div className='flex gap-2'>
              <StatusBadge status={project.data.status} />
              <Link
                href={`/dashboard/projects/${projectId}/experiments/new`}
                className={buttonClass}
              >
                {t('newExperiment')}
              </Link>
            </div>
          </div>
          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
            {(['experiment', 'sample', 'process', 'data'] as ResearchObjectKind[]).map((kind) => (
              <Link
                key={kind}
                href={`/dashboard/${KIND_META[kind].path}?project=${projectId}`}
                className={`${cardClass} transition hover:border-primary`}
              >
                <p className='text-xs text-muted-foreground'>{kindLabel(kind, locale)}</p>
                <p className='mt-2 text-2xl font-semibold'>{summary.data?.counts[kind] ?? 0}</p>
              </Link>
            ))}
          </div>
          <div className='mt-8 grid gap-8 lg:grid-cols-2'>
            <Section
              title={t('experiments')}
              action={
                <Link
                  href={`/dashboard/experiments?project=${projectId}`}
                  className='text-xs text-primary hover:underline'
                >
                  {t('viewAll')}
                </Link>
              }
            >
              {experiments.length ? (
                <div className='grid gap-2'>
                  {experiments.map((object) => (
                    <ObjectLink key={object.id} object={object} locale={locale} />
                  ))}
                </div>
              ) : (
                <p className='text-sm text-muted-foreground'>{t('noObjects')}</p>
              )}
            </Section>
            <Section title={t('recentObjects')}>
              <div className='grid gap-2'>
                {recent.slice(0, 8).map((object) => (
                  <ObjectLink key={object.id} object={object} locale={locale} />
                ))}
              </div>
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

function Overview() {
  const locale = useLocale();
  const t = useTranslations('Workspace');
  const summary = useRemote('workspace-summary', () => api.getWorkspaceSummary());
  const projects = summary.data?.projects ?? [];
  const recent = summary.data?.recent ?? [];
  return (
    <div className={pageClass}>
      <div className='mb-7'>
        <p className='font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground'>
          Scientific R&amp;D Workspace · v0.2
        </p>
        <h1 className='mt-2 text-3xl font-semibold tracking-tight'>{t('overview')}</h1>
        <p className='mt-2 max-w-2xl text-sm text-muted-foreground'>{t('overviewDescription')}</p>
      </div>
      <div className={`${cardClass} mb-7 border-primary/30 bg-primary/5`}>
        <p className='text-sm font-medium'>{t('syntheticDemo')}</p>
        <p className='mt-1 text-xs text-muted-foreground'>{t('syntheticDescription')}</p>
      </div>
      <PageState loading={summary.loading} error={summary.error} />
      <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
        {(['project', 'experiment', 'sample', 'data'] as ResearchObjectKind[]).map((kind) => (
          <div key={kind} className={cardClass}>
            <p className='text-xs text-muted-foreground'>{kindLabel(kind, locale)}</p>
            <p className='mt-2 text-2xl font-semibold'>{summary.data?.counts[kind] ?? 0}</p>
          </div>
        ))}
      </div>
      <div className='mt-8 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]'>
        <Section
          title={t('projects')}
          action={
            <Link href='/dashboard/projects' className='text-xs text-primary hover:underline'>
              {t('viewAll')}
            </Link>
          }
        >
          {projects.length ? (
            <div className='grid gap-2'>
              {projects.slice(0, 6).map((project) => (
                <ObjectLink key={project.id} object={project} locale={locale} />
              ))}
            </div>
          ) : (
            <p className='text-sm text-muted-foreground'>{t('noObjects')}</p>
          )}
        </Section>
        <Section title={t('recentObjects')}>
          <div className='grid gap-2'>
            {recent
              .filter((object) => object.kind !== 'project')
              .slice(0, 8)
              .map((object) => (
                <ObjectLink key={object.id} object={object} locale={locale} />
              ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

type ObjectRef = Pick<ResearchObject, 'id' | 'code' | 'kind' | 'title'>;

function ObjectReferencePicker({
  value,
  onChange,
  placeholder,
  projectScopeId,
  kinds
}: {
  value: ObjectRef | null;
  onChange: (object: ObjectRef | null) => void;
  placeholder: string;
  projectScopeId?: string | null;
  kinds?: ResearchObjectKind[];
}) {
  const [query, setQuery] = useState(value ? `@${value.code}` : '');
  const [items, setItems] = useState<ResearchObject[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!query.startsWith('@') || query.length < 2) {
      setItems([]);
      return;
    }
    let alive = true;
    api
      .listObjects({
        q: query.slice(1),
        project_scope_id: projectScopeId ?? undefined,
        kinds,
        include_global: true,
        limit: 8
      })
      .then((result) => alive && setItems(result))
      .catch(() => alive && setItems([]));
    return () => {
      alive = false;
    };
  }, [kinds, projectScopeId, query]);
  function choose(item: ResearchObject) {
    onChange(item);
    setQuery(`@${item.code}`);
    setOpen(false);
  }
  return (
    <div className='relative min-w-0'>
      <input
        className={inputClass}
        value={query}
        placeholder={placeholder}
        onFocus={() => setOpen(true)}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          onChange(null);
        }}
        onKeyDown={(event) => {
          if (!open || !items.length) {
            if (event.key === 'Escape') setOpen(false);
            return;
          }
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActive((index) => (index + 1) % items.length);
          } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive((index) => (index - 1 + items.length) % items.length);
          } else if (event.key === 'Enter') {
            event.preventDefault();
            choose(items[active]);
          } else if (event.key === 'Escape') setOpen(false);
        }}
        aria-label={placeholder}
      />
      {open && items.length > 0 && (
        <div className='absolute inset-x-0 top-full z-30 mt-1 max-h-56 overflow-auto rounded-md border bg-popover p-1 shadow-lg'>
          {items.map((item, index) => (
            <button
              type='button'
              key={item.id}
              onMouseDown={(event) => {
                event.preventDefault();
                choose(item);
              }}
              className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-xs ${active === index ? 'bg-accent' : 'hover:bg-muted'}`}
            >
              <span>
                <span className='font-mono text-muted-foreground'>{item.code}</span>
                <span className='ml-2'>{item.title}</span>
              </span>
              <span className='text-muted-foreground'>{kindLabel(item.kind, 'zh-CN')}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

type ComposerRow = {
  relationId?: string;
  relationType: 'uses' | 'produces';
  role: string;
  object: ObjectRef | null;
  value: string;
  unit: string;
};

function ProcessComposer({
  object,
  composition,
  loading,
  onSaved
}: {
  object: ResearchObject;
  composition: ProcessComposition | null;
  loading: boolean;
  onSaved: () => void;
}) {
  const t = useTranslations('Workspace');
  const [rows, setRows] = useState<ComposerRow[]>([]);
  const [outputTitle, setOutputTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const composerRef = useRef<HTMLFormElement>(null);
  const saveRef = useRef<() => Promise<void>>(async () => undefined);
  useEffect(() => {
    const next = [...(composition?.uses ?? []), ...(composition?.produces ?? [])].map(
      (relation) => ({
        relationId: relation.id,
        relationType: relation.relation_type as 'uses' | 'produces',
        role: relation.role ?? '',
        object: relation.target,
        value: String((relation.properties_jsonb.quantity as JsonObject | undefined)?.value ?? ''),
        unit: String((relation.properties_jsonb.quantity as JsonObject | undefined)?.unit ?? '')
      })
    );
    setRows(next);
  }, [composition]);
  async function save() {
    setSaving(true);
    setError(null);
    try {
      const items: ProcessCompositionItem[] = rows
        .filter((row): row is ComposerRow & { object: ObjectRef } => Boolean(row.object))
        .map((row) => ({
          relation_id: row.relationId,
          relation_type: row.relationType,
          target_object_id: row.object.id,
          role: row.role || null,
          properties_jsonb:
            row.value || row.unit ? { quantity: { value: Number(row.value), unit: row.unit } } : {}
        }));
      if (outputTitle.trim()) {
        items.push({
          relation_type: 'produces',
          create_target: {
            kind: 'sample',
            title: outputTitle.trim(),
            properties_jsonb: {}
          },
          role: null,
          properties_jsonb: {}
        });
      }
      await api.putComposition(object.id, items);
      setOutputTitle('');
      onSaved();
    } catch (cause) {
      setError(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  saveRef.current = save;
  useEffect(() => {
    const form = composerRef.current;
    if (!form) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        void saveRef.current();
      }
    };
    form.addEventListener('keydown', handleKeyDown);
    return () => form.removeEventListener('keydown', handleKeyDown);
  }, []);
  return (
    <form
      ref={composerRef}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      className={`${cardClass} space-y-4`}
    >
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h2 className='text-base font-semibold'>{t('structuredComposer')}</h2>
          <p className='mt-1 text-xs text-muted-foreground'>{t('composerHint')}</p>
        </div>
        <span className='rounded border px-2 py-1 font-mono text-[11px] text-muted-foreground'>
          ⌘/Ctrl + Enter
        </span>
      </div>
      {loading && <p className='text-xs text-muted-foreground'>{t('loading')}</p>}
      <div className='grid gap-2'>
        {rows.map((row, index) => (
          <div
            key={`${row.relationType}-${index}`}
            className='grid gap-2 rounded-lg border p-2 md:grid-cols-[0.8fr_1.4fr_0.8fr_0.7fr_auto]'
          >
            <select
              value={row.relationType}
              onChange={(event) =>
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index
                      ? {
                          ...item,
                          relationType: event.target.value as 'uses' | 'produces',
                          relationId:
                            item.relationType === event.target.value ? item.relationId : undefined
                        }
                      : item
                  )
                )
              }
              className={inputClass}
              aria-label={t('relation')}
            >
              <option value='uses'>{t('uses')}</option>
              <option value='produces'>{t('produces')}</option>
            </select>
            <ObjectReferencePicker
              value={row.object}
              onChange={(value) =>
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, object: value } : item
                  )
                )
              }
              projectScopeId={object.project_scope_id}
              kinds={
                row.relationType === 'produces'
                  ? ['sample', 'data']
                  : ['material', 'sample', 'equipment', 'data']
              }
              placeholder='@SMP-001 / @MAT-KI'
            />
            <input
              className={inputClass}
              value={row.role}
              onChange={(event) =>
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, role: event.target.value } : item
                  )
                )
              }
              placeholder={t('role')}
            />
            <div className='flex gap-1'>
              <input
                className={`${inputClass} min-w-0`}
                value={row.value}
                onChange={(event) =>
                  setRows((current) =>
                    current.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, value: event.target.value } : item
                    )
                  )
                }
                placeholder={t('value')}
                inputMode='decimal'
              />
              <input
                className={`${inputClass} min-w-0`}
                value={row.unit}
                onChange={(event) =>
                  setRows((current) =>
                    current.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, unit: event.target.value } : item
                    )
                  )
                }
                placeholder={t('unit')}
              />
            </div>
            <button
              type='button'
              className={secondaryButtonClass}
              onClick={() =>
                setRows((current) => current.filter((_, itemIndex) => itemIndex !== index))
              }
            >
              {t('remove')}
            </button>
          </div>
        ))}
      </div>
      <div className='flex flex-wrap gap-2'>
        <button
          type='button'
          className={secondaryButtonClass}
          onClick={() =>
            setRows((current) => [
              ...current,
              { relationType: 'uses', role: '', object: null, value: '', unit: '' }
            ])
          }
        >
          {t('addInput')}
        </button>
        <label className='flex min-w-64 flex-1 gap-2'>
          <span className='sr-only'>{t('newOutput')}</span>
          <input
            className={inputClass}
            value={outputTitle}
            onChange={(event) => setOutputTitle(event.target.value)}
            placeholder={t('newOutput')}
          />
        </label>
        <button
          type='button'
          className={secondaryButtonClass}
          onClick={() =>
            setRows((current) => [
              ...current,
              { relationType: 'produces', role: '', object: null, value: '', unit: '' }
            ])
          }
        >
          {t('addOutput')}
        </button>
        <button type='button' disabled={saving} className={buttonClass} onClick={() => void save()}>
          {saving ? t('saving') : t('saveRelations')}
        </button>
      </div>
      {error && <p className='text-xs text-destructive'>{error}</p>}
    </form>
  );
}

function ObjectEditor({
  object,
  onSaved
}: {
  object: ResearchObject;
  onSaved: (object: ResearchObject) => void;
}) {
  const t = useTranslations('Workspace');
  const [title, setTitle] = useState(object.title);
  const [status, setStatus] = useState(object.status);
  const [properties, setProperties] = useState(JSON.stringify(object.properties_jsonb, null, 2));
  const [contentDocument, setContentDocument] = useState<Array<JsonObject>>(
    object.content_document
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setTitle(object.title);
    setStatus(object.status);
    setProperties(JSON.stringify(object.properties_jsonb, null, 2));
    setContentDocument(object.content_document);
  }, [object]);
  async function save() {
    try {
      setSaving(true);
      setError(null);
      const parsed = JSON.parse(properties) as JsonObject;
      const updated = await api.updateObject(object.id, {
        title: title.trim(),
        status,
        properties_jsonb: parsed,
        content_document: contentDocument
      });
      onSaved(updated);
    } catch (cause) {
      setError(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className={`${cardClass} space-y-4`}>
      <div className='grid gap-3 md:grid-cols-[1.5fr_0.7fr]'>
        <label className='grid gap-1 text-xs font-medium'>
          {t('title')}
          <input
            className={inputClass}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className='grid gap-1 text-xs font-medium'>
          {t('status')}
          <select
            className={inputClass}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value='active'>active</option>
            <option value='draft'>draft</option>
            <option value='planned'>planned</option>
            <option value='running'>running</option>
            <option value='completed'>completed</option>
            <option value='cancelled'>cancelled</option>
            <option value='archived'>archived</option>
          </select>
        </label>
      </div>
      <label className='grid gap-1 text-xs font-medium'>
        {t('properties')}
        <textarea
          className={`${inputClass} h-32 py-2 font-mono text-xs`}
          value={properties}
          onChange={(event) => setProperties(event.target.value)}
          spellCheck={false}
        />
      </label>
      <div className='grid gap-1 text-xs font-medium'>
        {t('record')}
        <RichNoteEditor
          key={`${object.id}:${object.updated_at}`}
          initialContent={object.content_document}
          onChange={setContentDocument}
        />
      </div>
      <div className='flex items-center justify-between gap-3'>
        <span className='text-xs text-muted-foreground'>{t('explicitSave')}</span>
        <button
          disabled={saving || !title.trim()}
          className={buttonClass}
          onClick={() => void save()}
        >
          {saving ? t('saving') : t('save')}
        </button>
      </div>
      {error && <p className='text-xs text-destructive'>{error}</p>}
    </div>
  );
}

function RelationList({
  relations,
  objectId,
  locale: _locale
}: {
  relations: ObjectRelation[];
  objectId: string;
  locale?: string;
}) {
  const t = useTranslations('Workspace');
  return (
    <div className='grid gap-2'>
      {relations.map((relation) => {
        const other = relation.source_object_id === objectId ? relation.target : relation.source;
        return (
          <div
            key={relation.id}
            className='flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm'
          >
            <Link href={objectHref(other)} className='min-w-0 hover:underline'>
              <span className='font-mono text-xs text-muted-foreground'>{other.code}</span>
              <span className='ml-2'>{other.title}</span>
            </Link>
            <span className='shrink-0 text-xs text-muted-foreground'>
              {relation.relation_type}
              {relation.role ? ` · ${relation.role}` : ''}
            </span>
          </div>
        );
      })}
      {relations.length === 0 && (
        <p className='text-sm text-muted-foreground'>{t('noRelations')}</p>
      )}
    </div>
  );
}

function ContextSection({
  title,
  items,
  locale: _locale
}: {
  title: string;
  items: ResearchObject[];
  locale?: string;
}) {
  return (
    <Section title={title}>
      <div className='grid gap-2'>
        {items.length ? (
          items.map((item) => <ObjectLink key={item.id} object={item} />)
        ) : (
          <p className='text-sm text-muted-foreground'>—</p>
        )}
      </div>
    </Section>
  );
}

function LineageTree({ node }: { node: LineageTreeNode }) {
  return (
    <div className='space-y-2 border-l pl-3'>
      <ObjectLink object={node.object} />
      {node.children.length > 0 && (
        <div className='space-y-2 pl-3'>
          {node.children.map((child) => (
            <LineageTree key={child.object.id} node={child} />
          ))}
        </div>
      )}
    </div>
  );
}

function SampleContextView({ context, locale }: { context: SampleContext; locale: string }) {
  const t = useTranslations('Workspace');
  const lineage = (section: LineageContext, title: string) => (
    <Section
      title={`${title} (${section.samples.length})`}
      description={section.truncated ? t('lineageTruncated') : undefined}
    >
      <div className='grid gap-2'>
        {section.samples.length ? (
          section.samples.map((item) => <ObjectLink key={item.id} object={item} locale={locale} />)
        ) : (
          <p className='text-sm text-muted-foreground'>—</p>
        )}
      </div>
      <div className='mt-3 rounded-lg border bg-muted/30 p-3'>
        <p className='mb-2 text-xs font-medium'>{t('lineageTree')}</p>
        <LineageTree
          node={buildSampleLineageTree(
            context.current,
            section.samples,
            section.edges,
            title === t('upstream') ? 'upstream' : 'downstream'
          )}
        />
      </div>
      {section.data.length > 0 && (
        <p className='mt-3 text-xs text-muted-foreground'>
          {t('upstreamData')}: {section.data.map((item) => item.code).join(', ')}
        </p>
      )}
    </Section>
  );
  return (
    <div className='grid gap-8 lg:grid-cols-2'>
      <div className='space-y-8'>
        <Section title={t('directProvenance')} description={t('directProvenanceHint')}>
          <ContextSection
            title={t('producingProcess')}
            items={context.direct.producing_processes}
            locale={locale}
          />
          <ContextSection
            title={t('precursors')}
            items={context.direct.precursor_samples}
            locale={locale}
          />
          <ContextSection title={t('materials')} items={context.direct.materials} locale={locale} />
          <ContextSection title={t('equipment')} items={context.direct.equipment} locale={locale} />
          <Section title={t('sampleInputs')}>
            <div className='grid gap-2'>
              {context.direct.sample_inputs.length ? (
                context.direct.sample_inputs.map((input) => (
                  <div key={input.relation_id} className='flex items-center gap-2'>
                    <ObjectLink object={input.object} locale={locale} />
                    <span className='shrink-0 text-xs text-muted-foreground'>{input.role}</span>
                  </div>
                ))
              ) : (
                <p className='text-sm text-muted-foreground'>—</p>
              )}
            </div>
          </Section>
        </Section>
        <ContextSection title={t('currentData')} items={context.direct.data} locale={locale} />
      </div>
      <div className='space-y-8'>
        {lineage(context.upstream, t('upstream'))}
        {lineage(context.downstream, t('downstream'))}
      </div>
    </div>
  );
}

function ExperimentContextView({
  context,
  locale
}: {
  context: ExperimentContext;
  locale: string;
}) {
  const t = useTranslations('Workspace');
  return (
    <div className='grid gap-8 lg:grid-cols-2'>
      <ContextSection title={t('samples')} items={context.samples} locale={locale} />
      <ContextSection title={t('inputSamples')} items={context.input_samples} locale={locale} />
      <ContextSection title={t('processes')} items={context.processes} locale={locale} />
      <ContextSection title={t('data')} items={context.data} locale={locale} />
      <ContextSection title={t('derivedMaterials')} items={context.materials} locale={locale} />
      <ContextSection title={t('derivedEquipment')} items={context.equipment} locale={locale} />
    </div>
  );
}

function DataView({ object, locale: _locale }: { object: ResearchObject; locale?: string }) {
  const t = useTranslations('Workspace');
  const payloads = useRemote(`payloads:${object.id}`, () => api.listPayloads(object.id));
  const attachments = useRemote(`data-attachments:${object.id}`, () =>
    api.listAttachments(object.id)
  );
  const [points, setPoints] = useState<{ x_value: number; y_value: number }[]>([]);
  const [uploading, setUploading] = useState(false);
  const [importState, setImportState] = useState<{
    attachment: Attachment | null;
    preview: ImportPreview | null;
    error: string | null;
  }>({ attachment: null, preview: null, error: null });
  const [mapping, setMapping] = useState({
    name: 'Imported XY series',
    x: '',
    y: '',
    xUnit: '',
    yUnit: ''
  });
  const payload = payloads.data?.[0];
  const payloadId = payload?.id;
  useEffect(() => {
    if (payloadId) api.listPoints(payloadId).then((items) => setPoints(items));
  }, [payloadId]);
  const chart = points.length ? (
    <svg
      viewBox='0 0 640 220'
      className='h-56 w-full rounded-lg border bg-background p-3'
      role='img'
      aria-label={t('chart')}
    >
      <polyline
        fill='none'
        stroke='currentColor'
        strokeWidth='2'
        points={projectXYToPolyline(points, 640, 220, 20)}
      />
    </svg>
  ) : (
    <div className='flex h-56 items-center justify-center rounded-lg border text-sm text-muted-foreground'>
      {t('noPayload')}
    </div>
  );
  async function upload(file: File) {
    setUploading(true);
    try {
      const attachment = await api.uploadAttachment(object.id, file);
      const result = await api.previewImport(object.id, attachment.id);
      setImportState({ attachment, preview: result, error: null });
      setMapping((current) => ({
        ...current,
        x: result.headers[0] ?? '',
        y: result.headers[1] ?? ''
      }));
    } catch (cause) {
      setImportState((state) => ({ ...state, error: readableError(cause) }));
    } finally {
      setUploading(false);
    }
  }
  async function preview(attachment: Attachment) {
    try {
      const result = await api.previewImport(object.id, attachment.id);
      setImportState({ attachment, preview: result, error: null });
      setMapping((current) => ({
        ...current,
        x: result.headers[0] ?? '',
        y: result.headers[1] ?? ''
      }));
    } catch (cause) {
      setImportState({ attachment, preview: null, error: readableError(cause) });
    }
  }
  async function commit() {
    if (!importState.preview) return;
    try {
      await api.commitImport(object.id, importState.preview.id, {
        payload_name: mapping.name,
        sheet_name: importState.preview.sheet_name,
        x: { column: mapping.x, label: mapping.x, unit: mapping.xUnit || 'x' },
        y: { column: mapping.y, label: mapping.y, unit: mapping.yUnit || 'y' }
      });
      setImportState({ attachment: null, preview: null, error: null });
      window.location.reload();
    } catch (cause) {
      setImportState((state) => ({ ...state, error: readableError(cause) }));
    }
  }
  return (
    <div className='space-y-8'>
      <Section title={t('payload')} description={t('payloadHint')}>
        <PageState loading={payloads.loading} error={payloads.error} />
        {payload && (
          <div className='grid gap-3 md:grid-cols-3'>
            <div className={cardClass}>
              <p className='text-xs text-muted-foreground'>{t('points')}</p>
              <p className='mt-1 text-xl font-semibold'>{payload.points_count}</p>
            </div>
            <div className={cardClass}>
              <p className='text-xs text-muted-foreground'>{t('summary')}</p>
              <p className='mt-1 text-sm'>{JSON.stringify(payload.summary_jsonb)}</p>
            </div>
            <div className={cardClass}>
              <p className='text-xs text-muted-foreground'>{t('checksum')}</p>
              <p className='mt-1 break-all font-mono text-xs'>{payload.payload_sha256}</p>
            </div>
          </div>
        )}
        {chart}
      </Section>
      <Section title={t('sourceProvenance')}>
        <div className='grid gap-2'>
          {(attachments.data ?? []).map((attachment) => (
            <div
              key={attachment.id}
              className='flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm'
            >
              <span>
                {attachment.original_filename}{' '}
                <span className='font-mono text-xs text-muted-foreground'>
                  {attachment.sha256.slice(0, 12)}…
                </span>
              </span>
              <button className={secondaryButtonClass} onClick={() => void preview(attachment)}>
                {t('preview')}
              </button>
            </div>
          ))}
        </div>
        <label className={`${secondaryButtonClass} mt-3 cursor-pointer`}>
          <input
            type='file'
            className='sr-only'
            accept='.csv,.xlsx'
            disabled={uploading}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
            }}
          />
          {uploading ? t('uploading') : t('upload')}
        </label>
        {importState.preview && (
          <div className='mt-4 space-y-3 rounded-lg border p-3'>
            <p className='text-sm font-medium'>
              {t('preview')} · {importState.preview.row_count} rows
            </p>
            <div className='overflow-auto'>
              <table className='w-full min-w-[480px] text-left text-xs'>
                <thead>
                  <tr>
                    {importState.preview.headers.map((header) => (
                      <th key={header} className='border-b px-2 py-2'>
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {importState.preview.preview_rows.map((row, index) => (
                    <tr key={index}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className='border-b px-2 py-2'>
                          {String(cell ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className='grid gap-2 md:grid-cols-5'>
              <input
                className={inputClass}
                value={mapping.name}
                onChange={(event) => setMapping({ ...mapping, name: event.target.value })}
                placeholder={t('payloadName')}
              />
              <input
                className={inputClass}
                value={mapping.x}
                onChange={(event) => setMapping({ ...mapping, x: event.target.value })}
                placeholder='x column'
              />
              <input
                className={inputClass}
                value={mapping.xUnit}
                onChange={(event) => setMapping({ ...mapping, xUnit: event.target.value })}
                placeholder='x unit'
              />
              <input
                className={inputClass}
                value={mapping.y}
                onChange={(event) => setMapping({ ...mapping, y: event.target.value })}
                placeholder='y column'
              />
              <input
                className={inputClass}
                value={mapping.yUnit}
                onChange={(event) => setMapping({ ...mapping, yUnit: event.target.value })}
                placeholder='y unit'
              />
            </div>
            <button className={buttonClass} onClick={() => void commit()}>
              {t('commit')}
            </button>
          </div>
        )}
        {importState.error && <p className='mt-3 text-xs text-destructive'>{importState.error}</p>}
      </Section>
    </div>
  );
}

function ObjectDetail({ objectId }: { objectId: string }) {
  const locale = useLocale();
  const t = useTranslations('Workspace');
  const [refresh, setRefresh] = useState(0);
  const object = useRemote(`object:${objectId}:${refresh}`, () => api.getObject(objectId));
  const relations = useRemote(`relations:${objectId}:${refresh}`, () =>
    api.listRelations(objectId)
  );
  const composition = useRemote(
    object.data?.kind === 'process' ? `composition:${objectId}:${refresh}` : '',
    object.data?.kind === 'process' ? () => api.getComposition(objectId) : null
  );
  const revisions = useRemote(`revisions:${objectId}:${refresh}`, () =>
    api.listRevisions(objectId)
  );
  const attachments = useRemote(`attachments:${objectId}:${refresh}`, () =>
    api.listAttachments(objectId)
  );
  const sample = useRemote(
    object.data?.kind === 'sample' ? `sample-context:${objectId}:${refresh}` : '',
    object.data?.kind === 'sample' ? () => api.sampleContext(objectId) : null
  );
  const experiment = useRemote(
    object.data?.kind === 'experiment' ? `experiment-context:${objectId}:${refresh}` : '',
    object.data?.kind === 'experiment' ? () => api.experimentContext(objectId) : null
  );
  const [revisionNote, setRevisionNote] = useState('');
  const [savingRevision, setSavingRevision] = useState(false);
  const [selectedRevision, setSelectedRevision] = useState<ObjectRevision | null>(null);
  if (object.loading)
    return (
      <div className={pageClass}>
        <PageState loading />
      </div>
    );
  if (object.error || !object.data)
    return (
      <div className={pageClass}>
        <PageState error={object.error ?? t('notFound')} />
      </div>
    );
  const item = object.data;
  async function createRevision() {
    setSavingRevision(true);
    try {
      await api.createRevision(item.id, revisionNote);
      setRevisionNote('');
      setRefresh((value) => value + 1);
    } catch (cause) {
      window.alert(readableError(cause));
    } finally {
      setSavingRevision(false);
    }
  }
  return (
    <div className={pageClass}>
      <div className='mb-6 flex flex-wrap items-start justify-between gap-4'>
        <div>
          <Link
            href={`/dashboard/${KIND_META[item.kind].path}${item.project_scope_id ? `?project=${item.project_scope_id}` : ''}`}
            className='text-xs text-primary hover:underline'
          >
            ← {kindLabel(item.kind, locale)}
          </Link>
          <p className='mt-3 font-mono text-xs text-muted-foreground'>
            {item.code} · {item.type_key} v{item.type_version}
          </p>
          <h1 className='mt-1 text-2xl font-semibold'>{item.title}</h1>
        </div>
        <StatusBadge status={item.status} />
      </div>
      <div className='space-y-8'>
        <Section title={t('objectEditor')} description={t('editorHint')}>
          <ObjectEditor object={item} onSaved={() => setRefresh((value) => value + 1)} />
        </Section>
        {item.kind === 'process' && (
          <ProcessComposer
            object={item}
            composition={composition.data}
            loading={composition.loading}
            onSaved={() => setRefresh((value) => value + 1)}
          />
        )}
        {item.kind === 'sample' && (
          <Section title={t('sampleContext')}>
            <PageState loading={sample.loading} error={sample.error} />
            {sample.data && <SampleContextView context={sample.data} locale={locale} />}
          </Section>
        )}
        {item.kind === 'experiment' && (
          <Section title={t('experimentContext')}>
            <PageState loading={experiment.loading} error={experiment.error} />
            {experiment.data && <ExperimentContextView context={experiment.data} locale={locale} />}
          </Section>
        )}
        {item.kind === 'data' && <DataView object={item} locale={locale} />}
        {item.kind !== 'data' && (
          <Section title={t('relations')} description={t('relationsHint')}>
            <RelationList relations={relations.data ?? []} objectId={item.id} locale={locale} />
          </Section>
        )}
        <Section title={t('attachments')}>
          <div className='grid gap-2'>
            {(attachments.data ?? []).map((attachment) => (
              <div
                key={attachment.id}
                className='flex flex-wrap justify-between gap-2 rounded-lg border px-3 py-2 text-sm'
              >
                <span>
                  {attachment.original_filename}{' '}
                  <span className='font-mono text-xs text-muted-foreground'>
                    {attachment.size_bytes} B
                  </span>
                </span>
                <a
                  className='text-xs text-primary hover:underline'
                  href={api.downloadUrl(attachment.id)}
                >
                  {t('download')}
                </a>
              </div>
            ))}
          </div>
          <p className='mt-2 text-xs text-muted-foreground'>{t('attachmentHint')}</p>
        </Section>
        <Section title={t('revisions')} description={t('revisionHint')}>
          <div className='flex flex-wrap gap-2'>
            <input
              className={`${inputClass} max-w-md`}
              value={revisionNote}
              onChange={(event) => setRevisionNote(event.target.value)}
              placeholder={t('revisionNote')}
            />
            <button
              disabled={savingRevision}
              className={buttonClass}
              onClick={() => void createRevision()}
            >
              {savingRevision ? t('saving') : t('createRevision')}
            </button>
          </div>
          <div className='mt-3 grid gap-2'>
            {(revisions.data ?? []).map((revision) => (
              <button
                key={revision.id}
                className='flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted/60'
                onClick={() => setSelectedRevision(revision)}
              >
                <span>
                  {t('revision')} {revision.revision_number} · {revision.change_note || t('noNote')}
                </span>
                <span className='font-mono text-xs text-muted-foreground'>
                  {revision.snapshot_sha256.slice(0, 12)}…
                </span>
              </button>
            ))}
          </div>
          {selectedRevision && (
            <pre className='mt-3 max-h-80 overflow-auto rounded-lg bg-muted p-3 text-xs'>
              {JSON.stringify(selectedRevision.snapshot_jsonb, null, 2)}
            </pre>
          )}
        </Section>
      </div>
    </div>
  );
}

function NewObjectPage({ kind, scopeId }: { kind: ResearchObjectKind; scopeId: string }) {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations('Workspace');
  return (
    <div className={pageClass}>
      <Link
        href={`/dashboard/projects/${scopeId}`}
        className='text-xs text-primary hover:underline'
      >
        ← {t('backToProject')}
      </Link>
      <h1 className='mt-5 text-2xl font-semibold'>
        {t('create')} {kindLabel(kind, locale)}
      </h1>
      <p className='mt-1 mb-5 text-sm text-muted-foreground'>{t('keyboardReady')}</p>
      <ObjectCreateForm
        kind={kind}
        scopeId={scopeId}
        onCreated={(object) => router.push(objectHref(object))}
      />
    </div>
  );
}

export function WorkspaceApp({
  view,
  kind,
  objectId,
  projectId
}: {
  view: 'overview' | 'list' | 'detail' | 'project' | 'new';
  kind?: ResearchObjectKind;
  objectId?: string;
  projectId?: string;
}) {
  if (view === 'overview') return <Overview />;
  if (view === 'project' && projectId) return <ProjectOverview projectId={projectId} />;
  if (view === 'detail' && objectId) return <ObjectDetail objectId={objectId} />;
  if (view === 'new' && kind && projectId) return <NewObjectPage kind={kind} scopeId={projectId} />;
  if (view === 'list' && kind) return <ObjectList kind={kind} />;
  return (
    <div className={pageClass}>
      <PageState empty='Not found' />
    </div>
  );
}
