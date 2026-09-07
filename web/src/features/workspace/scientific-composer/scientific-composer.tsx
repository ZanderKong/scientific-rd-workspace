'use client';

import { BlockNoteSchema, defaultInlineContentSpecs } from '@blocknote/core';
import { filterSuggestionItems } from '@blocknote/core/extensions';
import { BlockNoteView } from '@blocknote/shadcn';
import {
  SuggestionMenuController,
  useCreateBlockNote,
  useEditorChange,
  type DefaultReactSuggestionItem
} from '@blocknote/react';
import { useEffect, useMemo, useState } from 'react';
import type {
  BindingDirection,
  JsonObject,
  ProcessDefinition,
  ResearchObject,
  ScientificOccurrenceDraft
} from '@/lib/domain';
import { canonicalizeDocument, occurrenceRef } from '../scientific-document/model';
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

function retainMatchingValues(values: JsonObject, definitions: JsonObject): JsonObject {
  const nested = definitions.fields;
  const keys = new Set(
    Array.isArray(nested)
      ? nested.flatMap((field) =>
          field && typeof field === 'object' && typeof field.key === 'string' ? [field.key] : []
        )
      : Object.keys(definitions)
  );
  return Object.fromEntries(Object.entries(values).filter(([key]) => keys.has(key)));
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

function ghostPreview(definitions: JsonObject) {
  const labels = previewFieldLabels(definitions);
  return labels.length ? labels.slice(0, 4).join(' · ') : '无默认使用字段';
}

export function ScientificComposer({
  initialBlocks,
  searchProcesses,
  searchObjects,
  onChange,
  editable = true
}: {
  initialBlocks: JsonObject[];
  searchProcesses: (query: string) => Promise<ProcessDefinition[]>;
  searchObjects: (query: string) => Promise<ResearchObject[]>;
  onChange: (blocks: JsonObject[]) => void;
  editable?: boolean;
}) {
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
  useEditorChange((current) => {
    const next = current.document as unknown as JsonObject[];
    setBlocks(next);
    onChange(next);
  }, editor);
  useEffect(() => {
    const handle = (event: Event) => {
      const occurrenceId = (event as CustomEvent<{ occurrenceId: string }>).detail?.occurrenceId;
      if (occurrenceId) setSelectedId(occurrenceId);
    };
    document.addEventListener('scientific-ref-focus', handle);
    return () => document.removeEventListener('scientific-ref-focus', handle);
  }, []);

  const occurrences = useMemo(() => currentOccurrences(blocks), [blocks]);
  const selected = occurrences.find((item) => item.occurrence_id === selectedId) ?? null;
  const processes = occurrences.filter((item) => item.kind === 'process');

  const replaceSelected = (replacement: ProcessDefinition | ResearchObject) => {
    if (!selected) return;
    if ('process_definition' in replacement) {
      const definition = replacement.process_definition;
      const version = replacement.current_version;
      setOccurrence({
        ...selected,
        target_id: definition.id,
        target_revision_id: null,
        process_definition_version_id: version.id,
        label_snapshot: definition.title,
        field_definitions: version.execution_field_definitions,
        values: retainMatchingValues(selected.values, version.execution_field_definitions)
      });
    } else {
      setOccurrence({
        ...selected,
        target_id: replacement.id,
        target_revision_id: null,
        label_snapshot: replacement.title,
        field_definitions: replacement.process_field_definitions,
        values: retainMatchingValues(selected.values, replacement.process_field_definitions),
        binding: selected.binding ? { ...selected.binding, binding_id: null } : selected.binding
      });
    }
    setReplaceQuery('');
    setReplaceResults([]);
  };

  const findReplacements = async () => {
    if (!selected) return;
    setReplaceResults(
      selected.kind === 'process'
        ? await searchProcesses(replaceQuery)
        : await searchObjects(replaceQuery)
    );
  };

  const processItems = async (query: string): Promise<DefaultReactSuggestionItem[]> => {
    const definitions = await searchProcesses(query);
    return filterSuggestionItems(
      definitions.map((definition) => {
        const target = definition.process_definition;
        const version = definition.current_version;
        return {
          title: target.title,
          subtext: `v${version.version} · ${ghostPreview(version.execution_field_definitions)}`,
          aliases: [target.code, ...target.tags],
          group: 'Processes',
          onItemClick: () => {
            const occurrence: ScientificOccurrenceDraft = {
              occurrence_id: crypto.randomUUID(),
              kind: 'process',
              target_id: target.id,
              process_definition_version_id: version.id,
              label_snapshot: target.title,
              field_definitions: version.execution_field_definitions,
              values: {},
              status: 'recorded'
            };
            editor.insertInlineContent([occurrenceRef(occurrence, target.title) as never]);
            requestAnimationFrame(() => {
              const scope =
                editor.prosemirrorView.dom.closest<HTMLElement>('[data-scientific-composer]') ??
                document;
              scope
                .querySelector<HTMLInputElement>(
                  `[data-occurrence-id="${occurrence.occurrence_id}"][data-scientific-slot="true"]`
                )
                ?.focus();
            });
          }
        };
      }),
      query
    );
  };

  const objectItems = async (query: string): Promise<DefaultReactSuggestionItem[]> => {
    const objects = await searchObjects(query);
    return filterSuggestionItems(
      objects.map((object) => ({
        title: object.title,
        subtext: `${object.code} · ${ghostPreview(object.process_field_definitions)}`,
        aliases: [object.code, ...object.tags],
        group: 'Objects',
        onItemClick: () => {
          const occurrence: ScientificOccurrenceDraft = {
            occurrence_id: crypto.randomUUID(),
            kind: 'object',
            target_id: object.id,
            label_snapshot: object.title,
            field_definitions: object.process_field_definitions,
            values: {},
            status: 'recorded',
            binding: null
          };
          editor.insertInlineContent([occurrenceRef(occurrence, object.title) as never]);
        }
      })),
      query
    );
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
    <div className='space-y-3' data-testid='scientific-composer' data-scientific-composer='true'>
      <div className='overflow-hidden rounded-xl border bg-background'>
        <BlockNoteView editor={editor} editable={editable} slashMenu={false}>
          {editable && (
            <>
              <SuggestionMenuController triggerCharacter='/' getItems={processItems} />
              <SuggestionMenuController triggerCharacter='@' getItems={objectItems} />
            </>
          )}
        </BlockNoteView>
      </div>
      {editable && selected?.kind === 'object' && (
        <section className='flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 p-3 text-sm'>
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
        <section className='rounded-lg border bg-muted/30 p-3 text-sm'>
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
