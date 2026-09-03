'use client';

import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { ObjectType, ResearchObject, ResearchObjectKind } from '@/lib/domain';
import { objectKindLabel } from './model';

type ResourceResolverProps = {
  projectId: string;
  types?: ObjectType[];
  zh: boolean;
  onAttach: (object: ResearchObject) => void;
  onCreateDraft: (draft: {
    kind: 'material' | 'equipment';
    title: string;
    properties_jsonb: Record<string, unknown>;
  }) => void;
};

const allowedKinds: ResearchObjectKind[] = ['material', 'equipment', 'sample'];

function kindClass(kind: ResearchObjectKind) {
  if (kind === 'material')
    return 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200';
  if (kind === 'equipment') return 'border-sky-500/30 bg-sky-500/10 text-sky-800 dark:text-sky-200';
  return 'border-violet-500/30 bg-violet-500/10 text-violet-800 dark:text-violet-200';
}

function previewProperty(object: ResearchObject, keys: string[]) {
  for (const key of keys) {
    const value = object.properties_jsonb[key];
    if (typeof value === 'string' || typeof value === 'number') return `${key}: ${value}`;
  }
  return object.type_label_zh;
}

function identityFieldLabel(field: string) {
  if (field === 'cas') return 'CAS';
  if (field === 'asset_number') return 'Asset number';
  return field.replaceAll('_', ' ');
}

export function ResourceResolver({
  projectId,
  types = [],
  zh,
  onAttach,
  onCreateDraft
}: ResourceResolverProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [objects, setObjects] = useState<ResearchObject[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inlineCreate, setInlineCreate] = useState(false);
  const [createKind, setCreateKind] = useState<'material' | 'equipment'>('material');
  const [createTitle, setCreateTitle] = useState('');
  const [createProperties, setCreateProperties] = useState<Record<string, string>>({});

  function identityFields(kind: 'material' | 'equipment') {
    const objectType = types.find((candidate) => candidate.kind === kind && candidate.is_default);
    const activeVersion =
      objectType?.versions.find((version) => version.is_active) ?? objectType?.versions[0];
    const properties = activeVersion?.json_schema.properties;
    if (properties && typeof properties === 'object' && !Array.isArray(properties)) {
      const fields = Object.keys(properties).filter((key) => key !== 'demo_tags');
      if (fields.length) return fields;
    }
    return [kind === 'material' ? 'cas' : 'asset_number'];
  }

  const createFields = identityFields(createKind);

  useEffect(() => {
    if (!open) return;
    setSelectedIndex(0);
    const timer = window.setTimeout(() => {
      setLoading(true);
      api
        .listObjects({
          kinds: allowedKinds,
          project_scope_id: projectId,
          include_global: true,
          q: query.trim() || undefined,
          limit: 40
        })
        .then((items) => {
          setObjects(items);
          setError(null);
        })
        .catch((cause) =>
          setError(cause instanceof ApiError ? cause.message : 'Resolver unavailable')
        )
        .finally(() => setLoading(false));
    }, 120);
    return () => window.clearTimeout(timer);
  }, [open, projectId, query]);

  useEffect(() => {
    setSelectedIndex((index) => Math.min(index, Math.max(0, objects.length - 1)));
  }, [objects.length]);

  function close() {
    setOpen(false);
    setInlineCreate(false);
    inputRef.current?.blur();
  }

  function attachSelected() {
    const object = objects[selectedIndex];
    if (!object) return;
    onAttach(object);
    setQuery('');
    close();
  }

  function submitInlineCreate() {
    if (!createTitle.trim()) return;
    onCreateDraft({
      kind: createKind,
      title: createTitle.trim(),
      properties_jsonb: Object.fromEntries(
        Object.entries(createProperties).filter(([, value]) => value.trim())
      )
    });
    setCreateTitle('');
    setCreateProperties({});
    close();
  }

  return (
    <div className='relative'>
      <div className='flex items-center gap-2 rounded-xl border border-dashed bg-background/70 px-3 py-2 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20'>
        <span className='font-mono text-sm text-muted-foreground'>@</span>
        <input
          ref={inputRef}
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            const next = event.target.value.replace(/^@/, '');
            setQuery(next);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              setSelectedIndex((index) => Math.min(index + 1, objects.length - 1));
            } else if (event.key === 'ArrowUp') {
              event.preventDefault();
              setSelectedIndex((index) => Math.max(index - 1, 0));
            } else if (event.key === 'Enter') {
              event.preventDefault();
              attachSelected();
            } else if (event.key === 'Escape') {
              event.preventDefault();
              close();
            }
          }}
          placeholder={
            zh
              ? '搜索 Material、Equipment 或 precursor Sample…'
              : 'Search Material, Equipment or precursor Sample…'
          }
          className='h-7 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground'
          aria-label={zh ? '资源解析器' : 'Resource resolver'}
        />
        <kbd className='hidden rounded border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline'>
          @
        </kbd>
      </div>
      {open && (
        <div
          className='absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-foreground/10 bg-popover shadow-xl shadow-black/10'
          data-testid='resource-resolver'
        >
          <div className='grid min-h-52 md:grid-cols-[minmax(12rem,0.9fr)_minmax(15rem,1.1fr)]'>
            <div className='border-b p-2 md:border-r md:border-b-0'>
              <div className='flex items-center justify-between px-2 pb-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground'>
                <span>{zh ? '对象' : 'Objects'}</span>
                <span>{loading ? '…' : objects.length}</span>
              </div>
              <div className='max-h-60 overflow-y-auto'>
                {error && <p className='px-2 py-4 text-xs text-destructive'>{error}</p>}
                {!loading && !error && objects.length === 0 && (
                  <p className='px-2 py-4 text-xs text-muted-foreground'>
                    {zh ? '没有匹配对象，可直接创建。' : 'No match. Create an object inline.'}
                  </p>
                )}
                {(['material', 'equipment', 'sample'] as const).map((kind) => {
                  const matches = objects
                    .map((object, index) => ({ object, index }))
                    .filter(({ object }) => object.kind === kind);
                  if (!matches.length) return null;
                  return (
                    <div key={kind} data-testid={`resource-group-${kind}`}>
                      <p className='px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground'>
                        {objectKindLabel(kind, zh)}
                      </p>
                      {matches.map(({ object, index }) => (
                        <button
                          type='button'
                          key={object.id}
                          aria-label={`${object.title} ${object.code}`}
                          onMouseEnter={() => setSelectedIndex(index)}
                          onClick={() => {
                            onAttach(object);
                            setQuery('');
                            close();
                          }}
                          className={`mb-1 flex w-full items-start gap-2 rounded-xl px-2 py-2 text-left transition ${index === selectedIndex ? 'bg-accent' : 'hover:bg-muted'}`}
                          data-testid={`resource-option-${object.id}`}
                        >
                          <span
                            className={`mt-0.5 size-2 shrink-0 rounded-full ${object.kind === 'material' ? 'bg-amber-500' : object.kind === 'equipment' ? 'bg-sky-500' : 'bg-violet-500'}`}
                          />
                          <span className='min-w-0'>
                            <span className='block truncate text-sm font-medium'>
                              {object.title}
                            </span>
                            <span className='block truncate font-mono text-[10px] text-muted-foreground'>
                              {object.code}
                            </span>
                          </span>
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
              <button
                type='button'
                onClick={() => {
                  setCreateTitle(query.trim());
                  setCreateProperties({});
                  setInlineCreate(true);
                }}
                className='mt-1 w-full rounded-xl border border-dashed px-2 py-2 text-left text-xs text-muted-foreground transition hover:border-foreground/30 hover:text-foreground'
              >
                + {zh ? '内联创建 Material / Equipment' : 'Create Material / Equipment inline'}
              </button>
            </div>
            <div className='hidden p-4 md:block'>
              {objects[selectedIndex] ? (
                <div className='space-y-4'>
                  <div className='flex items-start justify-between gap-3'>
                    <div>
                      <p
                        className={`mb-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium ${kindClass(objects[selectedIndex].kind)}`}
                      >
                        {objectKindLabel(objects[selectedIndex].kind, zh)}
                      </p>
                      <h3 className='text-base font-semibold'>{objects[selectedIndex].title}</h3>
                      <p className='mt-1 font-mono text-xs text-muted-foreground'>
                        {objects[selectedIndex].code}
                      </p>
                    </div>
                    <span className='rounded-full bg-muted px-2 py-1 text-[10px] text-muted-foreground'>
                      {objects[selectedIndex].status}
                    </span>
                  </div>
                  <div className='rounded-xl bg-muted/50 p-3 text-xs text-muted-foreground'>
                    {previewProperty(
                      objects[selectedIndex],
                      objects[selectedIndex].kind === 'material'
                        ? ['cas', 'supplier']
                        : ['asset_number', 'location']
                    )}
                  </div>
                  <p className='text-xs leading-5 text-muted-foreground'>
                    {zh
                      ? '身份来自对象库；本次用量只会写入当前 Process relation。'
                      : 'Identity comes from the object library; this use value is stored on the current Process relation.'}
                  </p>
                </div>
              ) : (
                <div className='flex h-full items-center justify-center text-center text-xs text-muted-foreground'>
                  {zh ? '选择左侧对象查看身份预览' : 'Select an object to preview its identity'}
                </div>
              )}
            </div>
          </div>
          {inlineCreate && (
            <div className='border-t bg-muted/20 p-3'>
              <div className='mb-2 flex items-center justify-between'>
                <p className='text-xs font-semibold'>
                  {zh ? '创建资源草稿' : 'Create resource draft'}
                </p>
                <button
                  type='button'
                  className='text-xs text-muted-foreground'
                  onClick={() => setInlineCreate(false)}
                >
                  ×
                </button>
              </div>
              <div className='grid gap-2 sm:grid-cols-[8rem_1fr_1fr_auto]'>
                <select
                  value={createKind}
                  onChange={(event) => {
                    setCreateKind(event.target.value as 'material' | 'equipment');
                    setCreateProperties({});
                  }}
                  className='h-8 rounded-lg border bg-background px-2 text-xs'
                >
                  <option value='material'>{zh ? 'Material' : 'Material'}</option>
                  <option value='equipment'>{zh ? 'Equipment' : 'Equipment'}</option>
                </select>
                <input
                  value={createTitle}
                  onChange={(event) => setCreateTitle(event.target.value)}
                  required
                  placeholder={zh ? '名称' : 'Title'}
                  className='h-8 rounded-lg border bg-background px-2 text-xs'
                />
                <div className='contents'>
                  {createFields.map((field) => (
                    <label key={field} className='grid gap-1 text-[10px] text-muted-foreground'>
                      {identityFieldLabel(field)}
                      <input
                        value={createProperties[field] ?? ''}
                        onChange={(event) =>
                          setCreateProperties((current) => ({
                            ...current,
                            [field]: event.target.value
                          }))
                        }
                        placeholder={identityFieldLabel(field)}
                        className='h-8 rounded-lg border bg-background px-2 text-xs text-foreground'
                      />
                    </label>
                  ))}
                </div>
                <button
                  type='button'
                  onClick={submitInlineCreate}
                  className='h-8 rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground'
                >
                  {zh ? '加入草稿' : 'Add draft'}
                </button>
              </div>
            </div>
          )}
          <div className='flex items-center justify-between border-t bg-muted/30 px-3 py-2 text-[10px] text-muted-foreground'>
            <span>
              {zh ? '↑↓ 移动 · Enter 附加 · Esc 关闭' : '↑↓ move · Enter attach · Esc close'}
            </span>
            <span>{zh ? '同一输入流可混合资源' : 'Mixed resource stream'}</span>
          </div>
        </div>
      )}
    </div>
  );
}
