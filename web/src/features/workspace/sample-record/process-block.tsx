'use client';

import { useState } from 'react';
import { ArrowDown, ArrowUp, GripVertical, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { ObjectType, ResearchObject } from '@/lib/domain';
import { cn } from '@/lib/utils';
import { ProcessCommand } from './process-command';
import { ResourceResolver } from './resource-resolver';
import { UsageFields } from './usage-fields';
import {
  objectKindLabel,
  processParameters,
  resourceLabel,
  withProcessParameters,
  type DraftResource,
  type DraftStep
} from './model';

type ProcessBlockProps = {
  index: number;
  total: number;
  draft: DraftStep;
  projectId: string;
  types: ObjectType[];
  zh: boolean;
  onChange: (draft: DraftStep) => void;
  onRemove: () => void;
  onMove: (direction: -1 | 1) => void;
};

function tokenClass(kind?: ResearchObject['kind']) {
  if (kind === 'material')
    return 'border-amber-500/35 bg-amber-500/10 text-amber-900 dark:text-amber-100';
  if (kind === 'equipment') return 'border-sky-500/35 bg-sky-500/10 text-sky-900 dark:text-sky-100';
  return 'border-violet-500/35 bg-violet-500/10 text-violet-900 dark:text-violet-100';
}

function ResourceToken({
  resource,
  zh,
  onRemove
}: {
  resource: DraftResource;
  zh: boolean;
  onRemove: () => void;
}) {
  const [preview, setPreview] = useState(false);
  const kind = resource.object?.kind ?? resource.create_target?.kind;
  return (
    <div className='relative' data-kind={kind}>
      <button
        type='button'
        onClick={() => setPreview((value) => !value)}
        className={cn(
          'inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition hover:-translate-y-px hover:shadow-sm',
          tokenClass(kind)
        )}
        data-testid={`resource-token-${kind ?? 'draft'}`}
      >
        <span className='size-1.5 rounded-full bg-current/60' />
        <span className='truncate'>{resourceLabel(resource.object, resource)}</span>
        <span className='font-mono text-[10px] opacity-60'>{resource.object?.code ?? 'draft'}</span>
      </button>
      <button
        type='button'
        onClick={onRemove}
        aria-label={
          zh
            ? `移除 ${resourceLabel(resource.object, resource)}`
            : `Remove ${resourceLabel(resource.object, resource)}`
        }
        className='absolute -top-1 -right-1 flex size-4 items-center justify-center rounded-full border bg-background text-[11px] text-muted-foreground hover:text-destructive'
      >
        ×
      </button>
      {preview && (
        <div
          className='absolute top-full left-0 z-20 mt-2 w-64 rounded-xl border bg-popover p-3 text-xs shadow-lg'
          data-testid='resource-preview'
        >
          <div className='flex items-start justify-between gap-2'>
            <div>
              <p className='font-semibold'>{resourceLabel(resource.object, resource)}</p>
              <p className='mt-0.5 font-mono text-[10px] text-muted-foreground'>
                {resource.object?.code ?? 'draft resource'}
              </p>
            </div>
            <span className='rounded-full bg-muted px-1.5 py-0.5 text-[10px]'>
              {kind ? objectKindLabel(kind, zh) : 'draft'}
            </span>
          </div>
          {resource.object && (
            <p className='mt-2 text-muted-foreground'>{resource.object.type_label_zh}</p>
          )}
          <p className='mt-2 leading-5 text-muted-foreground'>
            {zh
              ? '对象身份保持不变；下方字段只表示本次 Process 使用。'
              : 'Identity stays unchanged; fields below describe this Process use.'}
          </p>
        </div>
      )}
    </div>
  );
}

function ResourceEditor({
  resource,
  zh,
  onChange,
  onRemove
}: {
  resource: DraftResource;
  zh: boolean;
  onChange: (resource: DraftResource) => void;
  onRemove: () => void;
}) {
  return (
    <div className='rounded-2xl border bg-background/70 p-3'>
      <div className='flex items-center justify-between gap-3'>
        <div className='flex min-w-0 items-center gap-2'>
          <span
            className={cn(
              'size-2 shrink-0 rounded-full',
              resource.object?.kind === 'material'
                ? 'bg-amber-500'
                : resource.object?.kind === 'equipment'
                  ? 'bg-sky-500'
                  : 'bg-violet-500'
            )}
          />
          <span className='truncate text-sm font-medium'>
            {resourceLabel(resource.object, resource)}
          </span>
          <span className='font-mono text-[10px] text-muted-foreground'>
            {resource.object?.code ?? 'draft'}
          </span>
        </div>
        <Button
          type='button'
          variant='ghost'
          size='icon-xs'
          onClick={onRemove}
          aria-label={zh ? '移除资源' : 'Remove resource'}
        >
          <Trash2 />
        </Button>
      </div>
      <UsageFields resource={resource} zh={zh} onChange={onChange} />
    </div>
  );
}

export function ProcessBlock({
  index,
  total,
  draft,
  projectId,
  types,
  zh,
  onChange,
  onRemove,
  onMove
}: ProcessBlockProps) {
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [notesOpen, setNotesOpen] = useState(Boolean(draft.content_document?.length));
  const parameters = processParameters(draft.properties_jsonb);
  const parameterEntries = Object.entries(parameters);
  const [newParameter, setNewParameter] = useState('');

  function change(patch: Partial<DraftStep>) {
    onChange({ ...draft, ...patch });
  }

  function openProcessCommand(value: string) {
    const query = value.startsWith('/') ? value.slice(1) : '';
    setCommandQuery(query);
    setCommandOpen(value.startsWith('/'));
  }

  function selectProcess(selection: { typeVersionId?: string; label: string }) {
    change({ title: selection.label, type_version_id: selection.typeVersionId });
    setCommandQuery('');
    setCommandOpen(false);
  }

  function attach(object: ResearchObject) {
    const resource: DraftResource = {
      clientId: `resource-${object.id}`,
      target_object_id: object.id,
      role: object.kind === 'sample' ? 'precursor' : object.kind,
      usage_values: {},
      usage_schema_additions: [],
      object
    };
    change({ resources: [...draft.resources, resource] });
  }

  function addInlineResource(resource: {
    kind: 'material' | 'equipment';
    title: string;
    properties_jsonb: Record<string, unknown>;
  }) {
    change({
      resources: [
        ...draft.resources,
        {
          clientId: `resource-draft-${Date.now()}`,
          create_target: { ...resource, status: 'active', usage_schema_jsonb: {} },
          role: resource.kind,
          usage_values: {},
          usage_schema_additions: []
        }
      ]
    });
  }

  function setParameter(key: string, value: string, unit?: string) {
    const previous = parameters[key];
    const numeric = value !== '' && !Number.isNaN(Number(value)) ? Number(value) : value;
    change({
      properties_jsonb: withProcessParameters(draft.properties_jsonb, {
        ...parameters,
        [key]: { value: numeric, unit: unit ?? previous?.unit ?? undefined }
      })
    });
  }

  function addParameter() {
    const key = newParameter.trim();
    if (!key || parameters[key]) return;
    setParameter(key, '');
    setNewParameter('');
  }

  return (
    <section
      className='relative rounded-[1.35rem] border border-foreground/10 bg-card/80 p-4 shadow-sm shadow-black/[0.04] md:p-5'
      data-testid={`process-block-${index}`}
      aria-label={`${zh ? 'Process' : 'Process'} ${index + 1}`}
    >
      <div className='mb-4 flex items-start gap-3'>
        <div className='mt-1 hidden text-muted-foreground sm:block'>
          <GripVertical className='size-4' />
        </div>
        <div className='flex size-8 shrink-0 items-center justify-center rounded-xl bg-foreground text-xs font-semibold text-background'>
          {String(index + 1).padStart(2, '0')}
        </div>
        <div className='min-w-0 flex-1'>
          <div className='relative'>
            <Input
              value={draft.title}
              onChange={(event) => {
                change({ title: event.target.value });
                openProcessCommand(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === '/' && !draft.title) {
                  setCommandOpen(true);
                  setCommandQuery('');
                }
                if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
                if (event.altKey && event.key === 'ArrowUp' && index > 0) {
                  event.preventDefault();
                  onMove(-1);
                }
                if (event.altKey && event.key === 'ArrowDown' && index + 1 < total) {
                  event.preventDefault();
                  onMove(1);
                }
              }}
              placeholder={zh ? '输入 / 选择 Process…' : 'Type / to choose a Process…'}
              aria-label={zh ? `第 ${index + 1} 个 Process` : `Process ${index + 1}`}
              className='h-10 rounded-xl border-transparent bg-transparent px-0 text-lg font-semibold shadow-none focus-visible:border-transparent focus-visible:ring-0'
            />
            <ProcessCommand
              open={commandOpen}
              types={types}
              query={commandQuery}
              zh={zh}
              onQueryChange={(query) => {
                setCommandQuery(query);
                change({ title: `/${query}` });
              }}
              onSelect={selectProcess}
              onClose={() => {
                setCommandOpen(false);
                if (draft.title.startsWith('/')) change({ title: '' });
              }}
            />
          </div>
          <div className='mt-1 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground'>
            <span className='font-mono'>
              {draft.process_id ? 'existing process' : 'new process'}
            </span>
            {draft.type_version_id && (
              <span className='rounded-full bg-muted px-2 py-0.5'>
                {zh ? '已选定义' : 'definition selected'}
              </span>
            )}
          </div>
        </div>
        <div className='flex shrink-0 items-center gap-1'>
          <Button
            type='button'
            variant='ghost'
            size='icon-xs'
            onClick={() => onMove(-1)}
            disabled={index === 0}
            aria-label={zh ? '上移 Process' : 'Move Process up'}
          >
            <ArrowUp />
          </Button>
          <Button
            type='button'
            variant='ghost'
            size='icon-xs'
            onClick={() => onMove(1)}
            disabled={index + 1 === total}
            aria-label={zh ? '下移 Process' : 'Move Process down'}
          >
            <ArrowDown />
          </Button>
          {total > 1 && (
            <Button
              type='button'
              variant='ghost'
              size='icon-xs'
              onClick={onRemove}
              aria-label={zh ? '移除 Process' : 'Remove Process'}
            >
              <Trash2 />
            </Button>
          )}
        </div>
      </div>

      <div className='grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)]'>
        <div className='space-y-3'>
          <div className='rounded-2xl border border-dashed bg-background/50 p-3'>
            <div className='mb-2 flex items-center justify-between gap-2'>
              <div>
                <p className='text-xs font-semibold'>{zh ? '资源使用' : 'Resources used'}</p>
                <p className='mt-0.5 text-[10px] text-muted-foreground'>
                  {zh ? '身份与本次使用值分离保存' : 'Identity and this-use values stay separate'}
                </p>
              </div>
              <span className='font-mono text-[10px] text-muted-foreground'>
                {draft.resources.length} linked
              </span>
            </div>
            <div className='mb-3 flex flex-wrap gap-2' data-testid='resource-token-strip'>
              {draft.resources.map((resource) => (
                <ResourceToken
                  key={resource.clientId}
                  resource={resource}
                  zh={zh}
                  onRemove={() =>
                    change({
                      resources: draft.resources.filter(
                        (candidate) => candidate.clientId !== resource.clientId
                      )
                    })
                  }
                />
              ))}
              {draft.resources.length === 0 && (
                <span className='text-xs text-muted-foreground'>
                  {zh
                    ? '从 @ 开始添加 Material、Equipment 或 precursor Sample'
                    : 'Start with @ to add Material, Equipment or a precursor Sample'}
                </span>
              )}
            </div>
            <ResourceResolver
              projectId={projectId}
              zh={zh}
              onAttach={attach}
              onCreateDraft={addInlineResource}
            />
          </div>
          <div className='space-y-2'>
            {draft.resources.map((resource) => (
              <ResourceEditor
                key={resource.clientId}
                resource={resource}
                zh={zh}
                onChange={(next) =>
                  change({
                    resources: draft.resources.map((candidate) =>
                      candidate.clientId === next.clientId ? next : candidate
                    )
                  })
                }
                onRemove={() =>
                  change({
                    resources: draft.resources.filter(
                      (candidate) => candidate.clientId !== resource.clientId
                    )
                  })
                }
              />
            ))}
          </div>
        </div>
        <div className='rounded-2xl border bg-muted/20 p-3'>
          <div className='mb-3 flex items-start justify-between gap-2'>
            <div>
              <p className='text-xs font-semibold'>{zh ? 'Process 参数' : 'Process parameters'}</p>
              <p className='mt-0.5 text-[10px] text-muted-foreground'>
                {zh ? '只记录此 Process 自身的条件' : 'Conditions owned by this Process only'}
              </p>
            </div>
            <span className='rounded-full bg-background px-2 py-0.5 font-mono text-[10px] text-muted-foreground'>
              properties.parameters
            </span>
          </div>
          <div className='space-y-2'>
            {parameterEntries.map(([key, value]) => (
              <div key={key} className='grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_4rem] gap-1.5'>
                <label className='text-[10px] text-muted-foreground'>
                  {key}
                  <Input
                    value={value.value === undefined ? '' : String(value.value)}
                    onChange={(event) => setParameter(key, event.target.value)}
                    className='mt-1 h-8 text-xs'
                  />
                </label>
                <label className='text-[10px] text-muted-foreground'>
                  {zh ? '单位' : 'Unit'}
                  <Input
                    value={value.unit ?? ''}
                    onChange={(event) =>
                      setParameter(key, String(value.value ?? ''), event.target.value)
                    }
                    className='mt-1 h-8 text-xs'
                  />
                </label>
                <span className='pt-5 text-[10px] text-muted-foreground'>
                  #{Object.keys(parameters).indexOf(key) + 1}
                </span>
              </div>
            ))}
            <div className='flex gap-2 border-t border-dashed pt-2'>
              <Input
                value={newParameter}
                onChange={(event) => setNewParameter(event.target.value)}
                placeholder={zh ? '新参数 key' : 'New parameter key'}
                className='h-8 text-xs'
                aria-label={zh ? '新参数' : 'New parameter'}
              />
              <Button type='button' onClick={addParameter} variant='outline' size='sm'>
                <Plus /> {zh ? '参数' : 'parameter'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className='mt-4 border-t border-dashed pt-3'>
        <button
          type='button'
          onClick={() => setNotesOpen((value) => !value)}
          className='text-xs text-muted-foreground hover:text-foreground'
        >
          {notesOpen ? '−' : '+'} {zh ? '补充过程记录' : 'Add process notes'}
        </button>
        {notesOpen && (
          <Textarea
            value={(draft.content_document ?? []).map((item) => String(item.text ?? '')).join('\n')}
            onChange={(event) =>
              change({
                content_document: event.target.value
                  ? [{ type: 'paragraph', text: event.target.value }]
                  : []
              })
            }
            placeholder={zh ? '观察、偏差、判断…' : 'Observations, deviations, decisions…'}
            className='mt-2 min-h-20 bg-background/60 text-sm'
          />
        )}
      </div>
    </section>
  );
}
