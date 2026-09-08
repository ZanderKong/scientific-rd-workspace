'use client';

import { BlockNoteSchema, defaultInlineContentSpecs } from '@blocknote/core';
import { BlockNoteView } from '@blocknote/shadcn';
import {
  SuggestionMenuController,
  useCreateBlockNote,
  useEditorChange,
  type DefaultReactSuggestionItem,
  type SuggestionMenuProps
} from '@blocknote/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import type {
  BindingDirection,
  JsonObject,
  ProcessDefinition,
  ResearchObject,
  ScientificOccurrenceDraft
} from '@/lib/domain';
import { canonicalizeDocument, occurrenceRef } from '../scientific-document/model';
import {
  readUsageFields,
  ScientificFieldEditor,
  StructuredPropertiesEditor
} from '../components/scientific-field-editor';
import { createRefIdentityExtension, ObjectRef, ProcessRef } from './ref-spec';

const schema = BlockNoteSchema.create({
  inlineContentSpecs: {
    ...defaultInlineContentSpecs,
    processRef: ProcessRef,
    objectRef: ObjectRef
  }
});

function currentOccurrences(blocks: JsonObject[]) {
  try {
    return canonicalizeDocument(blocks).occurrences;
  } catch {
    return [];
  }
}

function identifiedFields(definitions: JsonObject, ownerId: string): JsonObject {
  return {
    fields: readUsageFields(definitions).map((field, order) => ({
      ...field,
      source: field.source ?? 'template',
      owner_id: field.source === 'local' ? null : (field.owner_id ?? ownerId),
      order
    }))
  };
}

function retainedForReplacement(occurrence: ScientificOccurrenceDraft, definitions: JsonObject) {
  const previous = readUsageFields(occurrence.field_definitions);
  const local = previous.filter((field) => field.source === 'local' && field.field_id);
  const identities = new Set(
    readUsageFields(definitions).map((field) => `${field.owner_id ?? ''}:${field.key}`)
  );
  return {
    definitions: { fields: [...readUsageFields(definitions), ...local] },
    values: Object.fromEntries(
      Object.entries(occurrence.values).filter(([key]) => {
        const field = previous.find((item) => item.key === key);
        return Boolean(
          field?.source === 'local' ||
          identities.has(`${field?.owner_id ?? ''}:${field?.key ?? ''}`)
        );
      })
    ),
    removed: previous
      .filter((field) => field.source !== 'local')
      .filter((field) => displayOccurrenceValue(occurrence, field) !== '')
      .filter((field) => !identities.has(`${field.owner_id ?? ''}:${field.key}`))
      .map((field) => `${field.label}: ${displayOccurrenceValue(occurrence, field)}`)
  };
}

function displayOccurrenceValue(occurrence: ScientificOccurrenceDraft, field: { key: string }) {
  const value = occurrence.values[field.key];
  if (value && typeof value === 'object' && 'value' in value) return String(value.value ?? '');
  return value == null ? '' : String(value);
}

function previewFieldLabels(definitions: JsonObject): string[] {
  const nested = definitions.fields;
  if (Array.isArray(nested)) {
    return nested.flatMap((field) =>
      field && typeof field === 'object' && 'label' in field && typeof field.label === 'string'
        ? [field.label]
        : []
    );
  }
  return Object.entries(definitions).flatMap(([key, field]) => {
    if (!field || typeof field !== 'object') return [];
    return ['label' in field && typeof field.label === 'string' ? field.label : key];
  });
}

function ghostPreview(definitions: JsonObject, emptyLabel: string) {
  const labels = previewFieldLabels(definitions);
  return labels.length ? labels.slice(0, 4).join(' · ') : emptyLabel;
}

type ComposerSuggestionItem = DefaultReactSuggestionItem & { ghost?: string };

export type ComposerSearchOptions = {
  offset?: number;
  limit?: number;
  signal?: AbortSignal;
};

type SearchPage<T> = T[] | { items: T[]; nextOffset?: number | null };

function ComposerSuggestionMenu(props: SuggestionMenuProps<ComposerSuggestionItem>) {
  const t = useTranslations('ProductCompletion.menu');
  const selected =
    props.selectedIndex === undefined ? null : (props.items[props.selectedIndex] ?? null);
  return (
    <div className='flex max-w-[min(46rem,90vw)] items-start gap-2 rounded-lg border bg-popover p-1 shadow-md'>
      <div className='min-w-64'>
        {props.loadingState !== 'loaded' && props.items.length === 0 ? (
          <p className='px-3 py-2 text-xs text-muted-foreground'>{t('loading')}</p>
        ) : (
          props.items.map((item, index) => (
            <button
              key={`${item.title}:${index}`}
              type='button'
              className={`flex w-full items-start gap-2 rounded px-3 py-2 text-left text-sm ${index === props.selectedIndex ? 'bg-accent' : 'hover:bg-accent/60'}`}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => props.onItemClick?.(item)}
            >
              {item.icon}
              <span>
                <span className='block font-medium'>{item.title}</span>
                {item.subtext && (
                  <span className='block text-xs text-muted-foreground'>{item.subtext}</span>
                )}
              </span>
            </button>
          ))
        )}
      </div>
      {selected?.ghost && (
        <div className='max-w-64 rounded-lg border bg-popover p-3 text-xs text-muted-foreground shadow-md'>
          {selected.ghost}
        </div>
      )}
    </div>
  );
}

function objectIdentity(object: ResearchObject) {
  const details = ['CAS', 'batch', '批次', 'purity', '纯度', 'model', '型号'].flatMap((key) => {
    const value = object.properties_jsonb[key];
    return value === undefined || value === null || value === ''
      ? []
      : [`${key}: ${String(value)}`];
  });
  return [object.code, ...details.slice(0, 3)].join(' · ');
}

export function ScientificComposer({
  initialBlocks,
  searchProcesses,
  searchObjects,
  createProcess,
  createObject,
  onChange,
  editable = true
}: {
  initialBlocks: JsonObject[];
  searchProcesses: (
    query: string,
    options?: ComposerSearchOptions
  ) => Promise<SearchPage<ProcessDefinition>>;
  searchObjects: (
    query: string,
    options?: ComposerSearchOptions
  ) => Promise<SearchPage<ResearchObject>>;
  createProcess?: (
    draft: {
      title: string;
      tags: string[];
      properties_jsonb: JsonObject;
      execution_field_definitions: JsonObject;
    },
    commandId?: string
  ) => Promise<ProcessDefinition>;
  createObject?: (
    draft: {
      title: string;
      tags: string[];
      properties_jsonb: JsonObject;
      process_field_definitions: JsonObject;
    },
    commandId?: string
  ) => Promise<ResearchObject>;
  onChange: (blocks: JsonObject[]) => void;
  editable?: boolean;
}) {
  const t = useTranslations('ProductCompletion.menu');
  const editor = useCreateBlockNote({
    schema,
    initialContent: (initialBlocks.length
      ? initialBlocks
      : [{ type: 'paragraph', content: [] }]) as never,
    extensions: [createRefIdentityExtension()]
  });
  const [blocks, setBlocks] = useState<JsonObject[]>(initialBlocks);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [replaceQuery, setReplaceQuery] = useState('');
  const [replaceResults, setReplaceResults] = useState<Array<ProcessDefinition | ResearchObject>>(
    []
  );
  const [createDraft, setCreateDraft] = useState<{
    kind: 'process' | 'object';
    title: string;
    tags: string;
    properties: JsonObject;
    fields: JsonObject;
  } | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const composerRootRef = useRef<HTMLDivElement>(null);
  const searchSequence = useRef(0);
  const searchAbort = useRef<AbortController | null>(null);
  const createTitleRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (createDraft) createTitleRef.current?.focus();
  }, [createDraft]);
  const setOccurrence = (occurrence: ScientificOccurrenceDraft) => {
    editor.transact((transaction) => {
      transaction.doc.descendants((node, pos) => {
        if (node.attrs.occurrenceId !== occurrence.occurrence_id) return;
        transaction.setNodeMarkup(pos, undefined, {
          ...node.attrs,
          occurrenceId: occurrence.occurrence_id,
          targetId: occurrence.target_id,
          label: occurrence.label_snapshot ?? node.attrs.label,
          payload: JSON.stringify(occurrence)
        });
      });
    });
  };
  const focusOccurrence = (occurrenceId: string) => {
    requestAnimationFrame(() => {
      const scope =
        editor.prosemirrorView.dom.closest<HTMLElement>('[data-scientific-composer]') ?? document;
      const ref = scope.querySelector<HTMLElement>(
        `[data-occurrence-id="${CSS.escape(occurrenceId)}"]`
      );
      const slot = ref?.querySelector<HTMLElement>('[data-scientific-slot="true"]');
      if (slot) slot.focus();
      else {
        ref?.querySelector<HTMLElement>('button')?.focus();
        requestAnimationFrame(() =>
          ref?.querySelector<HTMLElement>('[data-scientific-slot="true"]')?.focus()
        );
      }
    });
  };
  useEditorChange((current) => {
    const next = current.document as unknown as JsonObject[];
    setBlocks(next);
    onChange(next);
  }, editor);
  useEffect(() => {
    const root = composerRootRef.current;
    if (!root) return;
    const handle = (event: Event) => {
      const occurrenceId = (event as CustomEvent<{ occurrenceId: string }>).detail?.occurrenceId;
      if (occurrenceId) setSelectedId(occurrenceId);
    };
    root.addEventListener('scientific-ref-focus', handle);
    return () => root.removeEventListener('scientific-ref-focus', handle);
  }, []);

  const searchPage = async <T,>(
    search: (query: string, options?: ComposerSearchOptions) => Promise<SearchPage<T>>,
    query: string
  ) => {
    searchAbort.current?.abort();
    const controller = new AbortController();
    searchAbort.current = controller;
    const sequence = ++searchSequence.current;
    try {
      await new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(resolve, 150);
        controller.signal.addEventListener(
          'abort',
          () => {
            window.clearTimeout(timer);
            reject(new DOMException('Search superseded', 'AbortError'));
          },
          { once: true }
        );
      });
      const result = await search(query, { offset: 0, limit: 21, signal: controller.signal });
      if (controller.signal.aborted || sequence !== searchSequence.current) return [];
      const items = Array.isArray(result) ? result : result.items;
      return items.slice(0, 20);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return [];
      throw error;
    }
  };

  const occurrences = useMemo(() => currentOccurrences(blocks), [blocks]);
  const selected = occurrences.find((item) => item.occurrence_id === selectedId) ?? null;
  const processes = occurrences.filter((item) => item.kind === 'process');

  const replaceSelected = (replacement: ProcessDefinition | ResearchObject) => {
    if (!selected) return;
    if ('process_definition' in replacement) {
      const definition = replacement.process_definition;
      const version = replacement.current_version;
      const retained = retainedForReplacement(
        selected,
        identifiedFields(version.execution_field_definitions, definition.id)
      );
      if (
        retained.removed.length > 0 &&
        !window.confirm(t('replaceImpactConfirm', { values: retained.removed.join('\n') }))
      )
        return;
      setOccurrence({
        ...selected,
        target_id: definition.id,
        target_revision_id: null,
        process_definition_version_id: version.id,
        label_snapshot: definition.title,
        field_definitions: retained.definitions,
        values: retained.values
      });
    } else {
      const retained = retainedForReplacement(
        selected,
        identifiedFields(replacement.process_field_definitions, replacement.id)
      );
      if (
        retained.removed.length > 0 &&
        !window.confirm(t('replaceImpactConfirm', { values: retained.removed.join('\n') }))
      )
        return;
      setOccurrence({
        ...selected,
        target_id: replacement.id,
        target_revision_id: null,
        label_snapshot: replacement.title,
        field_definitions: retained.definitions,
        values: retained.values,
        binding: selected.binding ? { ...selected.binding, binding_id: null } : selected.binding
      });
    }
    focusOccurrence(selected.occurrence_id);
    setReplaceQuery('');
    setReplaceResults([]);
  };

  const findReplacements = async () => {
    if (!selected) return;
    setReplaceResults(
      selected.kind === 'process'
        ? await searchPage(searchProcesses, replaceQuery)
        : await searchPage(searchObjects, replaceQuery)
    );
  };

  const processItems = async (query: string): Promise<ComposerSuggestionItem[]> => {
    const definitions = await searchPage(searchProcesses, query);
    const items: ComposerSuggestionItem[] = definitions.map((definition) => {
      const target = definition.process_definition;
      const version = definition.current_version;
      const ghost = ghostPreview(version.execution_field_definitions, t('noFields'));
      return {
        title: target.title,
        subtext: `v${version.version} · ${ghost}`,
        ghost,
        aliases: [target.code, ...target.tags],
        group: t('processes'),
        onItemClick: () => {
          const occurrence: ScientificOccurrenceDraft = {
            occurrence_id: crypto.randomUUID(),
            kind: 'process',
            target_id: target.id,
            process_definition_version_id: version.id,
            label_snapshot: target.title,
            field_definitions: identifiedFields(version.execution_field_definitions, target.id),
            values: {},
            status: 'recorded'
          };
          editor.insertInlineContent([occurrenceRef(occurrence, target.title) as never]);
          focusOccurrence(occurrence.occurrence_id);
        }
      };
    });
    if (createProcess) {
      items.push({
        title: query ? t('newProcessNamed', { name: query }) : t('newProcess'),
        subtext: t('createProcessHint'),
        aliases: [query],
        group: t('createGroup'),
        onItemClick: () =>
          setCreateDraft({
            kind: 'process',
            title: query,
            tags: '',
            properties: {},
            fields: { fields: [] }
          })
      });
    }
    return items;
  };

  const objectItems = async (query: string): Promise<ComposerSuggestionItem[]> => {
    const objects = await searchPage(searchObjects, query);
    const items: ComposerSuggestionItem[] = objects.map((object) => ({
      title: object.title,
      subtext: objectIdentity(object),
      ghost: ghostPreview(object.process_field_definitions, t('noFields')),
      aliases: [object.code, ...object.tags],
      group: t('objects'),
      onItemClick: () => {
        const occurrence: ScientificOccurrenceDraft = {
          occurrence_id: crypto.randomUUID(),
          kind: 'object',
          target_id: object.id,
          label_snapshot: object.title,
          field_definitions: identifiedFields(object.process_field_definitions, object.id),
          values: {},
          status: 'recorded',
          binding: null
        };
        editor.insertInlineContent([occurrenceRef(occurrence, object.title) as never]);
        focusOccurrence(occurrence.occurrence_id);
      }
    }));
    if (createObject) {
      items.push({
        title: query ? t('newObjectNamed', { name: query }) : t('newObject'),
        subtext: t('createObjectHint'),
        aliases: [query],
        group: t('createGroup'),
        onItemClick: () =>
          setCreateDraft({
            kind: 'object',
            title: query,
            tags: '',
            properties: {},
            fields: { fields: [] }
          })
      });
    }
    return items;
  };

  const submitCreate = async () => {
    if (!createDraft?.title.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const tags = createDraft.tags
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
      if (createDraft.kind === 'process' && createProcess) {
        const created = await createProcess(
          {
            title: createDraft.title.trim(),
            tags,
            properties_jsonb: createDraft.properties,
            execution_field_definitions: createDraft.fields
          },
          crypto.randomUUID()
        );
        const target = created.process_definition;
        const occurrence: ScientificOccurrenceDraft = {
          occurrence_id: crypto.randomUUID(),
          kind: 'process',
          target_id: target.id,
          process_definition_version_id: created.current_version.id,
          label_snapshot: target.title,
          field_definitions: identifiedFields(
            created.current_version.execution_field_definitions,
            target.id
          ),
          values: {},
          status: 'recorded'
        };
        editor.insertInlineContent([occurrenceRef(occurrence, target.title) as never]);
        focusOccurrence(occurrence.occurrence_id);
      } else if (createDraft.kind === 'object' && createObject) {
        const target = await createObject(
          {
            title: createDraft.title.trim(),
            tags,
            properties_jsonb: createDraft.properties,
            process_field_definitions: createDraft.fields
          },
          crypto.randomUUID()
        );
        const occurrence: ScientificOccurrenceDraft = {
          occurrence_id: crypto.randomUUID(),
          kind: 'object',
          target_id: target.id,
          label_snapshot: target.title,
          field_definitions: identifiedFields(target.process_field_definitions, target.id),
          values: {},
          status: 'recorded',
          binding: null
        };
        editor.insertInlineContent([occurrenceRef(occurrence, target.title) as never]);
        focusOccurrence(occurrence.occurrence_id);
      }
      setCreateDraft(null);
    } catch (cause) {
      setCreateError(cause instanceof Error ? cause.message : t('createFailed'));
    } finally {
      setCreating(false);
    }
  };

  const updateBinding = (
    processOccurrenceId: string,
    direction: BindingDirection,
    role: string
  ) => {
    if (!selected || selected.kind !== 'object') return;
    setOccurrence({
      ...selected,
      binding: processOccurrenceId
        ? {
            process_occurrence_id: processOccurrenceId,
            binding_id:
              selected.binding?.process_occurrence_id === processOccurrenceId
                ? selected.binding.binding_id
                : null,
            direction,
            role: role || null
          }
        : null
    });
  };

  return (
    <div
      ref={composerRootRef}
      className='relative space-y-3'
      data-testid='scientific-composer'
      data-scientific-composer='true'
    >
      <div className='scientific-composer-surface overflow-visible rounded-xl bg-background'>
        <BlockNoteView editor={editor} editable={editable} slashMenu={false}>
          {editable && (
            <>
              <SuggestionMenuController
                triggerCharacter='/'
                getItems={processItems}
                suggestionMenuComponent={ComposerSuggestionMenu}
              />
              <SuggestionMenuController
                triggerCharacter='@'
                getItems={objectItems}
                suggestionMenuComponent={ComposerSuggestionMenu}
              />
            </>
          )}
        </BlockNoteView>
      </div>
      {editable && createDraft && (
        <div className='space-y-4 rounded-xl border bg-card p-4 shadow-sm'>
          <div className='flex items-center justify-between gap-3'>
            <h3 className='font-semibold'>
              {createDraft.kind === 'process' ? t('newProcess') : t('newObject')}
            </h3>
            <button
              type='button'
              className='text-sm text-muted-foreground'
              onClick={() => setCreateDraft(null)}
            >
              {t('cancel')}
            </button>
          </div>
          <div className='grid gap-3 md:grid-cols-2'>
            <label className='grid gap-1 text-xs'>
              {t('name')}
              <input
                ref={createTitleRef}
                className='h-9 rounded border bg-background px-2 text-sm'
                value={createDraft.title}
                onChange={(event) => setCreateDraft({ ...createDraft, title: event.target.value })}
              />
            </label>
            <label className='grid gap-1 text-xs'>
              {t('tags')}
              <input
                className='h-9 rounded border bg-background px-2 text-sm'
                value={createDraft.tags}
                onChange={(event) => setCreateDraft({ ...createDraft, tags: event.target.value })}
              />
            </label>
          </div>
          <StructuredPropertiesEditor
            value={createDraft.properties}
            onChange={(properties) => setCreateDraft({ ...createDraft, properties })}
          />
          <ScientificFieldEditor
            value={createDraft.fields}
            onChange={(fields) => setCreateDraft({ ...createDraft, fields })}
          />
          <button
            type='button'
            disabled={creating || !createDraft.title.trim()}
            className='rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50'
            onClick={() => void submitCreate()}
          >
            {creating ? t('creating') : t('createAndInsert')}
          </button>
          {createError && <p className='text-sm text-destructive'>{createError}</p>}
        </div>
      )}
      {editable && selected?.kind === 'object' && (
        <section className='absolute right-2 top-2 z-30 flex max-w-[min(28rem,calc(100vw-2rem))] flex-wrap items-center gap-2 rounded-xl border bg-popover/95 p-3 text-sm shadow-lg backdrop-blur'>
          <span className='font-medium'>关联过程</span>
          <select
            className='h-8 rounded border bg-background px-2'
            value={selected.binding?.process_occurrence_id ?? ''}
            onChange={(event) =>
              updateBinding(
                event.target.value,
                selected.binding?.direction ?? 'input',
                selected.binding?.role ?? 'subject'
              )
            }
          >
            <option value=''>不关联</option>
            {processes.map((process, index) => (
              <option key={process.occurrence_id} value={process.occurrence_id}>
                {process.label_snapshot ?? 'Process'} {index + 1}
              </option>
            ))}
          </select>
          {selected.binding && (
            <>
              <select
                aria-label='Binding direction'
                className='h-8 rounded border bg-background px-2'
                value={selected.binding.direction}
                onChange={(event) =>
                  updateBinding(
                    selected.binding!.process_occurrence_id,
                    event.target.value as BindingDirection,
                    selected.binding!.role ?? ''
                  )
                }
              >
                <option value='input'>投入物</option>
                <option value='context'>使用设备/上下文</option>
                <option value='output'>产物</option>
              </select>
              <input
                aria-label='Binding role'
                className='h-8 rounded border bg-background px-2'
                value={selected.binding.role ?? ''}
                onChange={(event) =>
                  updateBinding(
                    selected.binding!.process_occurrence_id,
                    selected.binding!.direction,
                    event.target.value
                  )
                }
                placeholder='用途'
              />
            </>
          )}
        </section>
      )}
      {editable && selected && (
        <section className='absolute right-2 top-16 z-20 max-w-[min(28rem,calc(100vw-2rem))] rounded-xl border bg-popover/95 p-3 text-sm shadow-lg backdrop-blur'>
          <div className='flex flex-wrap items-center gap-2'>
            <span className='font-medium'>替换 Ref</span>
            <input
              aria-label='替换 Ref 搜索'
              className='h-8 min-w-52 flex-1 rounded border bg-background px-2'
              value={replaceQuery}
              onChange={(event) => setReplaceQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  findReplacements();
                }
              }}
              placeholder={selected.kind === 'process' ? '查找 Process Definition' : '查找对象'}
            />
            <button
              type='button'
              className='h-8 rounded border bg-background px-3'
              onClick={findReplacements}
            >
              查找
            </button>
          </div>
          {replaceResults.length > 0 && (
            <ul className='mt-2 grid gap-1'>
              {replaceResults.map((result) => {
                const object = 'process_definition' in result ? result.process_definition : result;
                return (
                  <li key={object.id}>
                    <button
                      type='button'
                      className='w-full rounded px-2 py-1 text-left hover:bg-accent'
                      onClick={() => replaceSelected(result)}
                    >
                      {object.title} <span className='text-muted-foreground'>{object.code}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
