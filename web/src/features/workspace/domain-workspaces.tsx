'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Database,
  FlaskConical,
  FolderKanban,
  Play,
  Plus,
  Search,
  XCircle
} from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';
import type {
  ComparisonDimension,
  DataPayload,
  ExperimentComparison,
  ResearchObject
} from '@/lib/domain';
import { Button } from '@/components/ui/button';

const pageClass = 'mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10';
const cardClass = 'rounded-[1.25rem] border bg-card/80 p-4 shadow-xs md:p-5';
const inputClass =
  'h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring';
const muted = 'text-muted-foreground';

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
    if (!key) return;
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

function StateMessage({
  loading,
  error,
  empty
}: {
  loading?: boolean;
  error?: string | null;
  empty?: string;
}) {
  if (loading)
    return <p className={`py-10 text-center text-sm ${muted}`}>Loading workspace record…</p>;
  if (error)
    return (
      <div className='rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive'>
        {error}
      </div>
    );
  if (empty) return <p className={`py-10 text-center text-sm ${muted}`}>{empty}</p>;
  return null;
}

function Status({ value }: { value: string }) {
  return (
    <span className='rounded-full border px-2.5 py-1 text-xs text-muted-foreground'>{value}</span>
  );
}

function ObjectLink({ object }: { object: ResearchObject }) {
  const paths: Record<ResearchObject['kind'], string> = {
    project: 'projects',
    experiment: 'experiments',
    sample: 'samples',
    process: 'processes',
    data: 'data',
    material: 'materials',
    equipment: 'equipment'
  };
  return (
    <Link
      href={`/dashboard/${paths[object.kind]}/${object.id}`}
      className='flex items-center justify-between gap-3 rounded-xl border px-3 py-3 transition hover:border-primary hover:bg-muted/40'
    >
      <span className='min-w-0'>
        <span className='font-mono text-[10px] text-muted-foreground'>{object.code}</span>
        <span className='ml-2 truncate text-sm font-medium'>{object.title}</span>
      </span>
      <Status value={object.status} />
    </Link>
  );
}

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const locale = useLocale();
  const zh = locale === 'zh-CN';
  const [query, setQuery] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const record = useRemote(`project-record:${projectId}`, () => api.getProjectRecord(projectId));
  const search = useRemote(`project-search:${projectId}:${searchQuery}`, () =>
    api.searchProject(projectId, { q: searchQuery || undefined, limit: 20 })
  );
  const context = record.data?.context;
  return (
    <main className={pageClass}>
      <div className='mb-8 flex flex-wrap items-start justify-between gap-4'>
        <div>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Project record
          </p>
          <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
            <FolderKanban className='size-7 text-primary' />
            {record.data?.project.title ?? (zh ? '正在读取项目…' : 'Loading project…')}
          </h1>
          {record.data?.project && (
            <p className={`mt-2 text-sm ${muted}`}>
              <span className='font-mono'>{record.data.project.code}</span> ·{' '}
              {record.data.project.status}
            </p>
          )}
        </div>
        <div className='flex flex-wrap gap-2'>
          <Link href={`/dashboard/experiments?project=${projectId}`}>
            <Button variant='outline'>{zh ? '实验记录' : 'Experiment records'}</Button>
          </Link>
          <Link href={`/dashboard/samples?project=${projectId}`}>
            <Button>{zh ? '样品记录' : 'Sample records'}</Button>
          </Link>
          <Link href={`/dashboard/changes?project=${projectId}`}>
            <Button variant='outline'>{zh ? '变更审核' : 'Change review'}</Button>
          </Link>
          <Link href={`/dashboard/materials?project=${projectId}`}>
            <Button variant='outline'>{zh ? 'Materials' : 'Materials'}</Button>
          </Link>
          <Link href={`/dashboard/equipment?project=${projectId}`}>
            <Button variant='outline'>{zh ? 'Equipment' : 'Equipment'}</Button>
          </Link>
        </div>
      </div>
      <StateMessage loading={record.loading} error={record.error} />
      {record.data && context && (
        <>
          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
            {[
              ['experiment', zh ? 'Experiments' : 'Experiments'],
              ['sample', zh ? 'Samples' : 'Samples'],
              ['data', zh ? 'Data' : 'Data'],
              ['process', zh ? 'Processes' : 'Processes']
            ].map(([key, label]) => (
              <div key={key} className={cardClass}>
                <p className={`text-xs ${muted}`}>{label}</p>
                <p className='mt-2 text-3xl font-semibold'>{context.counts[key] ?? 0}</p>
              </div>
            ))}
          </div>
          <div className='mt-8 grid gap-8 lg:grid-cols-[1.05fr_0.95fr]'>
            <section className='space-y-3'>
              <div>
                <h2 className='text-base font-semibold'>{zh ? '最近记录' : 'Recent records'}</h2>
                <p className={`mt-1 text-xs ${muted}`}>
                  {zh
                    ? '按项目作用域读取的结构化对象。'
                    : 'Structured objects in this project scope.'}
                </p>
              </div>
              <div className='grid gap-2'>
                {[
                  ...context.recent_experiments,
                  ...context.recent_samples,
                  ...context.recent_data
                ].map((object) => (
                  <ObjectLink key={object.id} object={object} />
                ))}
              </div>
            </section>
            <section className='space-y-3'>
              <div>
                <h2 className='text-base font-semibold'>{zh ? '项目检索' : 'Project search'}</h2>
                <p className={`mt-1 text-xs ${muted}`}>
                  {zh
                    ? '搜索标题、编号和已索引属性。'
                    : 'Search titles, codes, and indexed properties.'}
                </p>
              </div>
              <form
                className='flex gap-2'
                onSubmit={(event) => {
                  event.preventDefault();
                  setSearchQuery(query.trim());
                }}
              >
                <div className='relative flex-1'>
                  <Search className='pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground' />
                  <input
                    className={`${inputClass} pl-9`}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={zh ? '搜索 Project 对象…' : 'Search project objects…'}
                    aria-label='Project search'
                  />
                </div>
                <Button type='submit'>{zh ? '搜索' : 'Search'}</Button>
              </form>
              <StateMessage
                loading={search.loading}
                error={search.error}
                empty={
                  !search.loading && !search.error && !search.data?.items.length
                    ? zh
                      ? '没有匹配对象。'
                      : 'No matching objects.'
                    : undefined
                }
              />
              {search.data && search.data.items.length > 0 && (
                <div className='grid gap-2'>
                  {search.data.items.map((object) => (
                    <ObjectLink key={object.id} object={object} />
                  ))}
                  <p className={`text-xs ${muted}`}>
                    {search.data.total} {zh ? '个匹配对象' : 'matches'}
                  </p>
                </div>
              )}
            </section>
          </div>
          <section className='mt-8'>
            <h2 className='text-base font-semibold'>
              {zh ? '全局资源摘要' : 'Global resource summary'}
            </h2>
            <div className='mt-3 grid gap-3 sm:grid-cols-2'>
              {Object.entries(context.resource_summary).map(([key, value]) => (
                <div key={key} className='rounded-xl border bg-muted/25 px-4 py-3'>
                  <p className={`text-xs capitalize ${muted}`}>{key}</p>
                  <p className='mt-1 text-xl font-semibold'>{value.count}</p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function ExperimentCreateForm({
  projectId,
  onCreated
}: {
  projectId: string;
  onCreated: (id: string) => void;
}) {
  const locale = useLocale();
  const zh = locale === 'zh-CN';
  const samples = useRemote(`experiment-samples:${projectId}`, () =>
    api.listObjects({ kind: 'sample', project_scope_id: projectId, limit: 200 })
  );
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('draft');
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || selected.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.createExperimentRecord(
        {
          project_scope_id: projectId,
          experiment: { title: title.trim(), status, properties_jsonb: {} },
          members: selected.map((sample_id) => ({ sample_id }))
        },
        globalThis.crypto?.randomUUID?.()
      );
      onCreated(result.experiment.id);
    } catch (cause) {
      setError(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  return (
    <form onSubmit={submit} className={`${cardClass} space-y-4`}>
      <div className='flex items-start gap-3'>
        <Plus className='mt-0.5 size-5 text-primary' />
        <div>
          <h2 className='font-semibold'>
            {zh ? '新建 Experiment Record' : 'New Experiment Record'}
          </h2>
          <p className={`mt-1 text-xs ${muted}`}>
            {zh
              ? 'Experiment 只通过 includes 关联 Samples，不改变 Sample 的归属。'
              : 'Experiment membership uses includes and does not change Sample ownership.'}
          </p>
        </div>
      </div>
      <div className='grid gap-3 md:grid-cols-[1.5fr_0.6fr]'>
        <label className='grid gap-1 text-xs font-medium'>
          {zh ? '标题' : 'Title'}
          <input
            className={inputClass}
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder='e.g. Heat treatment comparison'
          />
        </label>
        <label className='grid gap-1 text-xs font-medium'>
          {zh ? '状态' : 'Status'}
          <select
            className={inputClass}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value='draft'>draft</option>
            <option value='planned'>planned</option>
            <option value='active'>active</option>
            <option value='completed'>completed</option>
          </select>
        </label>
      </div>
      <div>
        <p className='mb-2 text-xs font-medium'>{zh ? '包含 Samples' : 'Included Samples'}</p>
        <StateMessage
          loading={samples.loading}
          error={samples.error}
          empty={
            !samples.loading && !samples.error && !samples.data?.length
              ? zh
                ? '项目中尚无 Sample。'
                : 'No Samples in this project.'
              : undefined
          }
        />
        <div className='grid gap-2 md:grid-cols-2'>
          {samples.data?.map((sample) => {
            const checked = selected.includes(sample.id);
            return (
              <label
                key={sample.id}
                htmlFor={`experiment-sample-${sample.id}`}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 text-sm ${checked ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'}`}
              >
                <input
                  id={`experiment-sample-${sample.id}`}
                  type='checkbox'
                  aria-label={`${sample.code} ${sample.title}`}
                  checked={checked}
                  onChange={() =>
                    setSelected((current) =>
                      checked ? current.filter((id) => id !== sample.id) : [...current, sample.id]
                    )
                  }
                />
                <span>
                  <span className='font-mono text-[10px] text-muted-foreground'>{sample.code}</span>
                  <span className='ml-2 font-medium'>{sample.title}</span>
                </span>
              </label>
            );
          })}
        </div>
      </div>
      <div className='flex flex-wrap items-center gap-3'>
        <Button type='submit' disabled={saving || selected.length === 0 || !title.trim()}>
          {saving ? (zh ? '保存中…' : 'Saving…') : zh ? '创建 Experiment' : 'Create Experiment'}
        </Button>
        {selected.length === 0 && (
          <span className={`text-xs ${muted}`}>
            {zh ? '至少选择一个 Sample' : 'Select at least one Sample'}
          </span>
        )}
        {error && <span className='text-xs text-destructive'>{error}</span>}
      </div>
    </form>
  );
}

function comparisonState(value: ComparisonDimension['state']) {
  const styles: Record<ComparisonDimension['state'], string> = {
    same: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
    different: 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200',
    missing: 'border-slate-400/30 bg-slate-400/10 text-slate-700 dark:text-slate-200',
    unit_conflict: 'border-red-500/30 bg-red-500/10 text-red-800 dark:text-red-200'
  };
  return styles[value];
}

function ExperimentDetail({ experimentId }: { experimentId: string }) {
  const locale = useLocale();
  const zh = locale === 'zh-CN';
  const [differencesOnly, setDifferencesOnly] = useState(false);
  const data = useRemote(`experiment-detail:${experimentId}:${differencesOnly}`, () =>
    Promise.all([
      api.getExperimentRecord(experimentId),
      api.getExperimentComparison(experimentId, differencesOnly)
    ])
  );
  const record = data.data?.[0];
  const comparison = data.data?.[1];
  return (
    <main className={pageClass}>
      <Link
        href='/dashboard/experiments'
        className={`mb-5 inline-flex items-center gap-1 text-xs ${muted} hover:text-foreground`}
      >
        <ArrowLeft className='size-3' /> {zh ? '全部 Experiments' : 'All Experiments'}
      </Link>
      <StateMessage loading={data.loading} error={data.error} />
      {record && comparison && (
        <>
          <header className='mb-8 flex flex-wrap items-start justify-between gap-4'>
            <div>
              <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
                Experiment record / {record.experiment.code}
              </p>
              <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
                <FlaskConical className='size-7 text-primary' />
                {record.experiment.title}
              </h1>
              <div className={`mt-3 flex flex-wrap gap-2 text-xs ${muted}`}>
                <Status value={record.experiment.status} />
                <span>
                  {record.member_count} {zh ? '个 Sample member' : 'Sample members'}
                </span>
                <span>·</span>
                <span className='font-mono'>{record.record_sha256.slice(0, 12)}</span>
              </div>
            </div>
            <Link href={`/dashboard/samples?project=${record.experiment.project_scope_id}`}>
              <Button variant='outline'>{zh ? '查看项目 Samples' : 'View project Samples'}</Button>
            </Link>
          </header>
          <section className='grid gap-8 lg:grid-cols-[0.82fr_1.18fr]'>
            <div className='space-y-3'>
              <div>
                <h2 className='text-base font-semibold'>
                  {zh ? 'Experiment members' : 'Experiment members'}
                </h2>
                <p className={`mt-1 text-xs ${muted}`}>
                  {zh
                    ? '成员顺序与 note 保存在 includes 关系元数据。'
                    : 'Order and notes live on includes relation metadata.'}
                </p>
              </div>
              <div className='grid gap-2'>
                {record.members.map((member) => (
                  <Link
                    key={member.membership_id}
                    href={`/dashboard/samples/${member.sample.id}`}
                    className='rounded-xl border px-3 py-3 hover:border-primary'
                  >
                    <div className='flex items-center justify-between gap-2'>
                      <span className='font-mono text-[10px] text-muted-foreground'>
                        #{member.ordinal + 1} · {member.sample.code}
                      </span>
                      <Status value={member.sample.status} />
                    </div>
                    <p className='mt-1 text-sm font-medium'>{member.sample.title}</p>
                    {member.note && <p className={`mt-1 text-xs ${muted}`}>{member.note}</p>}
                  </Link>
                ))}
              </div>
              <div className='rounded-xl border bg-muted/25 px-3 py-3 text-xs'>
                <p className='font-medium'>
                  {zh ? 'Legacy ownership context' : 'Legacy ownership context'}
                </p>
                <p className={`mt-1 ${muted}`}>
                  {record.legacy_ownership_context.process_count} processes ·{' '}
                  {record.legacy_ownership_context.sample_count} owned samples ·{' '}
                  {record.legacy_ownership_context.data_count} data
                </p>
              </div>
            </div>
            <div className='space-y-3'>
              <div className='flex flex-wrap items-end justify-between gap-3'>
                <div>
                  <h2 className='text-base font-semibold'>
                    {zh ? 'Deterministic comparison' : 'Deterministic comparison'}
                  </h2>
                  <p className={`mt-1 text-xs ${muted}`}>
                    {zh
                      ? '按 type key、出现次序和资源 object id 对齐；不做单位换算。'
                      : 'Aligned by type key, occurrence, and resource object id; no unit conversion.'}
                  </p>
                </div>
                <label className='flex items-center gap-2 text-xs'>
                  <input
                    type='checkbox'
                    checked={differencesOnly}
                    onChange={(event) => setDifferencesOnly(event.target.checked)}
                  />
                  {zh ? '仅显示差异' : 'Differences only'}
                </label>
              </div>
              <ComparisonTable comparison={comparison} zh={zh} />
            </div>
          </section>
          <section className='mt-8 space-y-3'>
            <h2 className='text-base font-semibold'>{zh ? 'XY series' : 'XY series'}</h2>
            {comparison.xy_series.length ? (
              <div className='grid gap-3 md:grid-cols-2'>
                {comparison.xy_series.map((series) => (
                  <div key={`${series.sample_id}-${series.data_id}`} className={cardClass}>
                    <div className='flex items-center justify-between gap-2'>
                      <p className='font-medium'>{series.name}</p>
                      <span className={`text-xs ${muted}`}>
                        {series.x_unit ?? 'x'} / {series.y_unit ?? 'y'}
                      </span>
                    </div>
                    <p className={`mt-1 text-xs ${muted}`}>
                      {series.sample_code} · {series.data_code} · {series.points.length} points
                    </p>
                    <div className='mt-3 grid grid-cols-2 gap-1 font-mono text-[10px]'>
                      {series.points.slice(0, 8).map((point) => (
                        <div key={point.ordinal} className='rounded bg-muted/50 px-2 py-1'>
                          {point.x_value} → {point.y_value}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className={`rounded-xl border border-dashed px-3 py-5 text-sm ${muted}`}>
                {zh ? '成员暂无兼容的 XY series。' : 'No compatible XY series across members.'}
              </p>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function ComparisonTable({ comparison, zh }: { comparison: ExperimentComparison; zh: boolean }) {
  return (
    <div className='overflow-x-auto rounded-xl border'>
      <table className='w-full min-w-[620px] text-left text-xs'>
        <thead className='bg-muted/45 text-muted-foreground'>
          <tr>
            <th className='px-3 py-2 font-medium'>{zh ? 'Dimension' : 'Dimension'}</th>
            {comparison.members.map((member) => (
              <th key={member.id} className='px-3 py-2 font-medium'>
                {member.code}
              </th>
            ))}
            <th className='px-3 py-2 font-medium'>State</th>
          </tr>
        </thead>
        <tbody className='divide-y'>
          {comparison.dimensions.map((dimension) => (
            <tr key={dimension.key}>
              <td className='px-3 py-2'>
                <p className='font-medium'>{dimension.label}</p>
                <p className={`font-mono text-[10px] ${muted}`}>{dimension.group}</p>
              </td>
              {comparison.members.map((member) => {
                const value = dimension.values[member.id];
                return (
                  <td key={member.id} className='px-3 py-2 align-top'>
                    {value?.available ? (
                      <>
                        {String(value.value)}
                        {value.unit ? ` ${value.unit}` : ''}
                      </>
                    ) : (
                      <span className={muted}>—</span>
                    )}
                  </td>
                );
              })}
              <td className='px-3 py-2'>
                <span
                  className={`rounded-full border px-2 py-1 text-[10px] ${comparisonState(dimension.state)}`}
                >
                  {dimension.state}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExperimentWorkspace({
  experimentId,
  projectId,
  create = false
}: {
  experimentId?: string;
  projectId?: string;
  create?: boolean;
}) {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const router = useRouter();
  const scopeId = projectId ?? searchParams.get('project');
  const [creating, setCreating] = useState(create);
  const experiments = useRemote(
    `experiments:${scopeId ?? 'none'}`,
    scopeId && !experimentId
      ? () => api.listObjects({ kind: 'experiment', project_scope_id: scopeId, limit: 100 })
      : null
  );
  if (experimentId) return <ExperimentDetail experimentId={experimentId} />;
  const zh = locale === 'zh-CN';
  return (
    <main className={pageClass}>
      <div className='mb-7 flex flex-wrap items-start justify-between gap-4'>
        <div>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Experiment workspace
          </p>
          <h1 className='mt-2 text-3xl font-semibold tracking-tight'>
            {zh ? '实验记录' : 'Experiment records'}
          </h1>
          <p className={`mt-2 max-w-2xl text-sm ${muted}`}>
            {zh
              ? '用一组 Samples 表达一次实验，并提供可复现的逐维度比较。'
              : 'Group Samples into an experiment and compare them deterministically dimension by dimension.'}
          </p>
        </div>
        {scopeId && (
          <Button onClick={() => setCreating((value) => !value)}>
            <Plus />
            {creating ? (zh ? '关闭' : 'Close') : zh ? '新建 Experiment' : 'New Experiment'}
          </Button>
        )}
      </div>
      {!scopeId && (
        <div className={`${cardClass} text-sm ${muted}`}>
          {zh
            ? '请先从侧边栏选择 Project 作用域。'
            : 'Choose a Project scope from the sidebar first.'}
        </div>
      )}
      {scopeId && creating && (
        <div className='mb-6'>
          <ExperimentCreateForm
            projectId={scopeId}
            onCreated={(id) => router.push(`/dashboard/experiments/${id}`)}
          />
        </div>
      )}
      <StateMessage
        loading={experiments.loading}
        error={experiments.error}
        empty={
          scopeId && !experiments.loading && !experiments.error && !experiments.data?.length
            ? zh
              ? '这个 Project 还没有 Experiment。'
              : 'This Project has no Experiments yet.'
            : undefined
        }
      />
      {experiments.data && experiments.data.length > 0 && (
        <div className='grid gap-3 md:grid-cols-2'>
          {experiments.data.map((experiment) => (
            <Link
              key={experiment.id}
              href={`/dashboard/experiments/${experiment.id}`}
              className={`${cardClass} transition hover:border-primary`}
            >
              <div className='flex items-start justify-between gap-3'>
                <div>
                  <p className={`font-mono text-[10px] ${muted}`}>{experiment.code}</p>
                  <h2 className='mt-1 text-lg font-semibold'>{experiment.title}</h2>
                </div>
                <Status value={experiment.status} />
              </div>
              <p className={`mt-4 text-xs ${muted}`}>
                {new Date(experiment.updated_at).toLocaleString(locale)} ·{' '}
                {zh ? '打开记录与比较' : 'Open record and comparison'}
              </p>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

function PayloadCard({ payload, zh }: { payload: DataPayload; zh: boolean }) {
  const points = useRemote(
    `payload-points:${payload.id}`,
    payload.payload_kind === 'xy_series' ? () => api.listPoints(payload.id) : null
  );
  return (
    <article className={cardClass}>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <p className={`font-mono text-[10px] uppercase tracking-[0.16em] ${muted}`}>
            {payload.payload_kind}
          </p>
          <h2 className='mt-1 text-base font-semibold'>{payload.name}</h2>
        </div>
        <span className={`rounded-full bg-muted px-2 py-1 text-xs ${muted}`}>
          {payload.schema_key} v{payload.schema_version}
        </span>
      </div>
      <div className={`mt-4 grid gap-2 text-xs ${muted}`}>
        <div className='flex justify-between gap-3'>
          <span>SHA-256</span>
          <span className='font-mono text-foreground'>{payload.payload_sha256.slice(0, 16)}…</span>
        </div>
        <div className='flex justify-between gap-3'>
          <span>{zh ? '摘要' : 'Summary'}</span>
          <span className='text-right text-foreground'>
            {payload.payload_kind === 'scalar' && payload.scalar
              ? `${payload.scalar.value}${payload.scalar.unit ? ` ${payload.scalar.unit}` : ''}`
              : payload.payload_kind === 'table'
                ? `${payload.table_rows_count} rows · ${payload.table_columns.length} columns`
                : payload.payload_kind === 'xy_series'
                  ? `${payload.points_count} points`
                  : payload.summary_jsonb.filename
                    ? String(payload.summary_jsonb.filename)
                    : 'Attached file'}
          </span>
        </div>
      </div>
      {payload.payload_kind === 'table' && (
        <div className='mt-4 overflow-x-auto rounded-lg border'>
          <table className='w-full min-w-[420px] text-left text-xs'>
            <thead className='bg-muted/45'>
              <tr>
                {payload.table_columns.map((column) => (
                  <th key={column.key} className='px-2 py-2 font-medium'>
                    {column.label}
                    {column.unit ? ` (${column.unit})` : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className='divide-y'>
              {payload.table_rows.slice(0, 12).map((row) => (
                <tr key={row.ordinal}>
                  {payload.table_columns.map((column) => (
                    <td key={column.key} className='px-2 py-2'>
                      {row.values[column.key] == null ? '—' : String(row.values[column.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {payload.payload_kind === 'xy_series' && (
        <div className='mt-4 grid grid-cols-2 gap-1 font-mono text-[10px]'>
          {points.data?.slice(0, 8).map((point) => (
            <div key={point.ordinal} className='rounded bg-muted/50 px-2 py-1'>
              {point.x_value} → {point.y_value}
            </div>
          ))}
        </div>
      )}
      {payload.source_attachment_id && (
        <a
          href={api.downloadUrl(payload.source_attachment_id)}
          className='mt-4 inline-flex text-xs font-medium text-primary hover:underline'
        >
          {zh ? '下载附件' : 'Download attachment'}
        </a>
      )}
    </article>
  );
}

export function DataWorkspace({ dataId }: { dataId: string }) {
  const locale = useLocale();
  const zh = locale === 'zh-CN';
  const record = useRemote(`data-record:${dataId}`, () => api.getDataRecord(dataId));
  return (
    <main className={pageClass}>
      <Link
        href='/dashboard/data'
        className={`mb-5 inline-flex items-center gap-1 text-xs ${muted} hover:text-foreground`}
      >
        <ArrowLeft className='size-3' /> {zh ? '全部 Data' : 'All Data'}
      </Link>
      <StateMessage loading={record.loading} error={record.error} />
      {record.data && (
        <>
          <header className='mb-8 flex flex-wrap items-start justify-between gap-4'>
            <div>
              <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
                Data record / {record.data.data.code}
              </p>
              <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
                <Database className='size-7 text-primary' />
                {record.data.data.title}
              </h1>
              <div className={`mt-3 flex flex-wrap gap-2 text-xs ${muted}`}>
                <Status value={record.data.data.status} />
                <span>{record.data.payloads.length} payloads</span>
                <span>·</span>
                <span className='font-mono'>{record.data.record_sha256.slice(0, 12)}</span>
              </div>
            </div>
            <Link href={`/dashboard/projects/${record.data.data.project_scope_id}`}>
              <Button variant='outline'>{zh ? '返回 Project' : 'Open Project'}</Button>
            </Link>
          </header>
          <section className='grid gap-3 md:grid-cols-2'>
            {record.data.payloads.length ? (
              record.data.payloads.map((payload) => (
                <PayloadCard key={payload.id} payload={payload} zh={zh} />
              ))
            ) : (
              <p className={`rounded-xl border border-dashed px-3 py-5 text-sm ${muted}`}>
                {zh ? '暂无 typed payload。' : 'No typed payloads yet.'}
              </p>
            )}
          </section>
          <section className='mt-8'>
            <h2 className='text-base font-semibold'>{zh ? '导入记录' : 'Import records'}</h2>
            <div className='mt-3 grid gap-2'>
              {record.data.imports.length ? (
                record.data.imports.map((item) => (
                  <div
                    key={item.id}
                    className='flex flex-wrap items-center justify-between gap-3 rounded-xl border px-3 py-3 text-xs'
                  >
                    <span>
                      <span className='font-mono'>{item.source_format}</span>
                      <span className='ml-2'>{item.status}</span>
                    </span>
                    <span className={muted}>
                      {item.row_count ?? 0} rows · {item.warnings.length} warnings
                    </span>
                  </div>
                ))
              ) : (
                <p className={`rounded-xl border border-dashed px-3 py-5 text-sm ${muted}`}>
                  {zh ? '暂无导入。' : 'No imports yet.'}
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export function ExecutionPanel({ sampleId, zh }: { sampleId: string; zh: boolean }) {
  const execution = useRemote(`execution:${sampleId}`, () => api.getExecution(sampleId));
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  async function start() {
    setSaving(true);
    setMessage(null);
    try {
      await api.startExecution(sampleId, globalThis.crypto?.randomUUID?.());
      window.location.reload();
    } catch (cause) {
      setMessage(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  async function update() {
    if (!note.trim() || !execution.data) return;
    setSaving(true);
    setMessage(null);
    try {
      await api.updateExecution(sampleId, {
        observations: [
          ...execution.data.observations,
          { text: note.trim(), recorded_at: new Date().toISOString() }
        ]
      });
      setNote('');
      window.location.reload();
    } catch (cause) {
      setMessage(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  async function close(cancelled: boolean) {
    setSaving(true);
    setMessage(null);
    try {
      if (cancelled) await api.cancelExecution(sampleId, globalThis.crypto?.randomUUID?.());
      else await api.completeExecution(sampleId, globalThis.crypto?.randomUUID?.());
      window.location.reload();
    } catch (cause) {
      setMessage(readableError(cause));
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className='mt-8 rounded-[1.35rem] border bg-card/70 p-4 md:p-5'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h2 className='flex items-center gap-2 text-base font-semibold'>
            <ClipboardList className='size-4 text-primary' />
            {zh ? 'Sample Execution' : 'Sample Execution'}
          </h2>
          <p className={`mt-1 text-xs ${muted}`}>
            {zh
              ? '开始时冻结 planned snapshot，as-run 变化会显示在 diff。'
              : 'Starting freezes the planned snapshot; changes are shown in the as-run diff.'}
          </p>
        </div>
        {execution.data && <Status value={execution.data.execution.status} />}
      </div>
      <StateMessage
        loading={execution.loading}
        error={
          execution.error && execution.error.toLowerCase().includes('not found')
            ? null
            : execution.error
        }
      />
      {!execution.loading &&
        execution.error &&
        execution.error.toLowerCase().includes('not found') && (
          <div className='mt-4'>
            <Button onClick={() => void start()} disabled={saving}>
              <Play />
              {zh ? '开始执行' : 'Start execution'}
            </Button>
          </div>
        )}
      {execution.data && (
        <>
          <div className='mt-4 grid gap-3 md:grid-cols-2'>
            <div className='rounded-xl bg-muted/35 p-3'>
              <p className={`text-xs ${muted}`}>{zh ? 'Planned' : 'Planned'}</p>
              <p className='mt-1 font-mono text-xs'>
                {execution.data.execution.plan_snapshot_sha256.slice(0, 20)}…
              </p>
              <p className={`mt-2 text-xs ${muted}`}>
                {Array.isArray(execution.data.planned.steps) && execution.data.planned.steps.length
                  ? `${execution.data.planned.steps.length} steps`
                  : 'Snapshot available'}
              </p>
            </div>
            <div className='rounded-xl bg-muted/35 p-3'>
              <p className={`text-xs ${muted}`}>{zh ? 'Diff' : 'Diff'}</p>
              <p className='mt-1 text-2xl font-semibold'>
                {execution.data.diff.filter((item) => item.state !== 'same').length}
              </p>
              <p className={`text-xs ${muted}`}>{zh ? '个变化维度' : 'changed dimensions'}</p>
            </div>
          </div>
          <div className='mt-4 flex flex-wrap gap-2'>
            <input
              className={`${inputClass} max-w-xl`}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder={zh ? '记录 as-run 观察…' : 'Add an as-run observation…'}
            />
            <Button onClick={() => void update()} disabled={saving || !note.trim()}>
              Save observation
            </Button>
            {execution.data.execution.status === 'running' && (
              <>
                <Button variant='outline' onClick={() => void close(false)} disabled={saving}>
                  <CheckCircle2 />
                  {zh ? '完成' : 'Complete'}
                </Button>
                <Button variant='destructive' onClick={() => void close(true)} disabled={saving}>
                  <XCircle />
                  {zh ? '取消' : 'Cancel'}
                </Button>
              </>
            )}
          </div>
          {message && <p className='mt-2 text-xs text-destructive'>{message}</p>}
          <div className='mt-4 grid gap-2'>
            {execution.data.diff
              .filter((item) => item.state !== 'same')
              .slice(0, 8)
              .map((item) => (
                <div
                  key={item.key}
                  className='flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-xs'
                >
                  <span>{item.label}</span>
                  <span className={`rounded-full border px-2 py-1 ${comparisonState(item.state)}`}>
                    {item.state}
                  </span>
                </div>
              ))}
          </div>
        </>
      )}
    </section>
  );
}

function changeValue(value: unknown) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === 'object') return 'Structured record';
  return 'Updated';
}

function ChangeDiff({ diff }: { diff: Array<Record<string, unknown>> }) {
  if (!diff.length) return <p className={`text-sm ${muted}`}>No structured changes.</p>;
  return (
    <div className='grid gap-2'>
      {diff.map((item, index) => (
        <div
          key={`${String(item.key ?? 'change')}-${index}`}
          className='grid gap-2 rounded-xl border px-3 py-3 text-sm sm:grid-cols-[1fr_0.8fr_0.8fr] sm:items-center'
        >
          <span className='font-medium'>{String(item.label ?? item.key ?? 'Change')}</span>
          <span className={`text-xs ${muted}`}>
            <span className='mr-1 uppercase tracking-wide'>Before</span>
            {changeValue(item.before)}
          </span>
          <span className='text-xs'>
            <span className='mr-1 uppercase tracking-wide text-primary'>After</span>
            {changeValue(item.after)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ChangeSetDetail({ changeSetId }: { changeSetId: string }) {
  const locale = useLocale();
  const zh = locale === 'zh-CN';
  const router = useRouter();
  const record = useRemote(`change-set:${changeSetId}`, () => api.getChangeSet(changeSetId));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  async function review(decision: 'approve' | 'reject') {
    setBusy(true);
    setMessage(null);
    try {
      await api.reviewChangeSet(changeSetId, { decision });
      router.refresh();
    } catch (cause) {
      setMessage(readableError(cause));
    } finally {
      setBusy(false);
    }
  }
  const item = record.data;
  return (
    <main className={pageClass}>
      <Link
        href='/dashboard/changes'
        className={`mb-5 inline-flex items-center gap-1 text-xs ${muted} hover:text-foreground`}
      >
        <ArrowLeft className='size-3' /> {zh ? '全部 ChangeSets' : 'All ChangeSets'}
      </Link>
      <StateMessage loading={record.loading} error={record.error} />
      {item && (
        <>
          <header className='mb-8 flex flex-wrap items-start justify-between gap-4'>
            <div>
              <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
                ChangeSet review
              </p>
              <h1 className='mt-2 text-3xl font-semibold tracking-tight'>
                {item.operation_kind.replaceAll('_', ' ')}
              </h1>
              <div className={`mt-3 flex flex-wrap gap-2 text-xs ${muted}`}>
                <Status value={item.status} />
                <span>{item.source_client_name}</span>
                <span>·</span>
                <span>{new Date(item.created_at).toLocaleString(locale)}</span>
              </div>
            </div>
            <div className='flex flex-wrap gap-2'>
              {item.status === 'proposed' && (
                <>
                  <Button onClick={() => void review('approve')} disabled={busy}>
                    <CheckCircle2 /> {zh ? '接受并应用' : 'Accept and apply'}
                  </Button>
                  <Button
                    variant='destructive'
                    onClick={() => void review('reject')}
                    disabled={busy}
                  >
                    <XCircle /> {zh ? '拒绝' : 'Reject'}
                  </Button>
                </>
              )}
            </div>
          </header>
          <section className={cardClass}>
            <div className='flex flex-wrap items-start justify-between gap-3'>
              <div>
                <h2 className='text-base font-semibold'>
                  {zh ? '结构化科学变更' : 'Structured scientific change'}
                </h2>
                <p className={`mt-1 text-xs ${muted}`}>
                  {zh
                    ? '审阅页面不展开原始 JSON；应用时由服务重新校验作用域与 record hash。'
                    : 'The review surface avoids raw JSON; apply revalidates scope and record hash.'}
                </p>
              </div>
              {item.base_record_sha256 && (
                <span className='font-mono text-[10px] text-muted-foreground'>
                  base {item.base_record_sha256.slice(0, 16)}…
                </span>
              )}
            </div>
            <div className='mt-5'>
              <ChangeDiff diff={item.diff_jsonb} />
            </div>
            {message && <p className='mt-3 text-xs text-destructive'>{message}</p>}
          </section>
          <section className='mt-6 grid gap-3 md:grid-cols-3'>
            <div className='rounded-xl border px-3 py-3 text-xs'>
              <p className={muted}>Target</p>
              <p className='mt-1 font-mono'>
                {item.target_kind} {item.target_id ? item.target_id.slice(0, 12) : 'new'}
              </p>
            </div>
            <div className='rounded-xl border px-3 py-3 text-xs'>
              <p className={muted}>Transport</p>
              <p className='mt-1'>{item.source_transport}</p>
            </div>
            <div className='rounded-xl border px-3 py-3 text-xs'>
              <p className={muted}>Provenance</p>
              <p className='mt-1'>{item.source_client_version ?? 'version not supplied'}</p>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export function ChangeSetWorkspace({
  changeSetId,
  projectId
}: {
  changeSetId?: string;
  projectId?: string;
}) {
  const locale = useLocale();
  const zh = locale === 'zh-CN';
  const searchParams = useSearchParams();
  const scopeId = projectId ?? searchParams.get('project') ?? undefined;
  const items = useRemote(`change-sets:${scopeId ?? 'all'}`, () => api.listChangeSets(scopeId));
  if (changeSetId) return <ChangeSetDetail changeSetId={changeSetId} />;
  return (
    <main className={pageClass}>
      <div className='mb-7'>
        <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
          Change review
        </p>
        <h1 className='mt-2 text-3xl font-semibold tracking-tight'>
          {zh ? '变更审核' : 'Change review'}
        </h1>
        <p className={`mt-2 text-sm ${muted}`}>
          {zh
            ? '外部 agent 的科学写入先落为 ChangeSet，再由人审阅。'
            : 'External scientific writes land as ChangeSets before human review.'}
        </p>
      </div>
      <StateMessage
        loading={items.loading}
        error={items.error}
        empty={
          !items.loading && !items.error && !items.data?.length
            ? zh
              ? '当前没有待审变更。'
              : 'No change proposals yet.'
            : undefined
        }
      />
      {items.data && items.data.length > 0 && (
        <div className='grid gap-3'>
          {items.data.map((item) => (
            <Link
              key={item.id}
              href={`/dashboard/changes/${item.id}`}
              className={`${cardClass} transition hover:border-primary`}
            >
              <div className='flex flex-wrap items-start justify-between gap-3'>
                <div>
                  <p className={`font-mono text-[10px] ${muted}`}>
                    {item.source_client_name} · {item.source_transport}
                  </p>
                  <h2 className='mt-1 text-base font-semibold'>
                    {item.operation_kind.replaceAll('_', ' ')}
                  </h2>
                </div>
                <Status value={item.status} />
              </div>
              <p className={`mt-3 text-xs ${muted}`}>
                {new Date(item.created_at).toLocaleString(locale)} · {item.diff_jsonb.length}{' '}
                changes
              </p>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
