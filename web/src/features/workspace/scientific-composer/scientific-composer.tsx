'use client';

import { BlockNoteSchema, defaultInlineContentSpecs } from '@blocknote/core';
import { SuggestionMenu } from '@blocknote/core/extensions';
import { BlockNoteView } from '@blocknote/shadcn';
import {
  SuggestionMenuController,
  createReactInlineContentSpec,
  useCreateBlockNote,
  useEditorChange,
  type DefaultReactSuggestionItem
} from '@blocknote/react';
import { useEffect, useRef, useState } from 'react';
import type {
  JsonObject,
  ProcessDefinition,
  ResearchObject,
  ResourceRole,
  ScientificOccurrenceDraft
} from '@/lib/domain';
import {
  canonicalizeDocument,
  occurrenceRef,
  parseOccurrencePayload
} from '../scientific-document/model';
import {
  filterPropertyDefinitions,
  propertyDictionary
} from '../scientific-document/property-dictionary';

export type ComposerSearchOptions = { offset?: number; limit?: number; signal?: AbortSignal };
type SearchPage<T> = T[] | { items: T[]; nextOffset?: number | null };

const referenceProps = {
  occurrenceId: { default: '' },
  targetId: { default: '' },
  label: { default: '' },
  payload: { default: '' }
} as const;
const propertyProps = {
  occurrenceId: { default: '' },
  lineId: { default: '' },
  label: { default: '' }
} as const;

function RefView({
  inlineContent
}: {
  inlineContent: { type: string; props: Record<string, string> };
}) {
  const kind =
    inlineContent.type === 'propertyRef'
      ? 'property'
      : inlineContent.type === 'processRef'
        ? 'process'
        : 'object';
  return (
    <span
      data-scientific-ref={kind}
      data-occurrence-id={inlineContent.props.occurrenceId}
      className={`scientific-ref scientific-ref--${kind}`}
      contentEditable={false}
    >
      @{inlineContent.props.label}
    </span>
  );
}

const ProcessRef = createReactInlineContentSpec(
  { type: 'processRef', propSchema: referenceProps, content: 'none' } as const,
  {
    render: RefView,
    toExternalHTML: ({ inlineContent }) => <span>@{inlineContent.props.label}</span>
  }
);
const ObjectRef = createReactInlineContentSpec(
  { type: 'objectRef', propSchema: referenceProps, content: 'none' } as const,
  {
    render: RefView,
    toExternalHTML: ({ inlineContent }) => <span>@{inlineContent.props.label}</span>
  }
);
const PropertyRef = createReactInlineContentSpec(
  { type: 'propertyRef', propSchema: propertyProps, content: 'none' } as const,
  {
    render: RefView,
    toExternalHTML: ({ inlineContent }) => <span>@{inlineContent.props.label}</span>
  }
);

const schema = BlockNoteSchema.create({
  inlineContentSpecs: {
    ...defaultInlineContentSpecs,
    processRef: ProcessRef,
    objectRef: ObjectRef,
    propertyRef: PropertyRef
  }
});

function parentOccurrenceIds(editor: ReturnType<typeof useCreateBlockNote>): string[] | null {
  const currentId = editor.getTextCursorPosition().block.id;
  const find = (blocks: readonly JsonObject[], parent: JsonObject | null): string[] | null => {
    for (const block of blocks) {
      if (block.id === currentId) {
        if (!parent) return null;
        const content = Array.isArray(parent.content) ? parent.content : [];
        return content.flatMap((item) => {
          if (!item || typeof item !== 'object') return [];
          const node = item as JsonObject;
          if (node.type !== 'processRef' && node.type !== 'objectRef') return [];
          const id = (node.props as JsonObject | undefined)?.occurrenceId;
          return typeof id === 'string' ? [id] : [];
        });
      }
      const nested = Array.isArray(block.children)
        ? find(block.children as JsonObject[], block)
        : null;
      if (nested) return nested;
    }
    return null;
  };
  return find(editor.document as unknown as JsonObject[], null);
}

function currentOccurrences(blocks: JsonObject[]) {
  const result: ScientificOccurrenceDraft[] = [];
  const walk = (items: JsonObject[]) =>
    items.forEach((block) => {
      const content = Array.isArray(block.content) ? block.content : [];
      content.forEach((item) => {
        if (!item || typeof item !== 'object') return;
        const node = item as JsonObject;
        if (node.type !== 'processRef' && node.type !== 'objectRef') return;
        const occurrence = parseOccurrencePayload((node.props as JsonObject | undefined)?.payload);
        if (occurrence) result.push(occurrence);
      });
      if (Array.isArray(block.children)) walk(block.children as JsonObject[]);
    });
  walk(blocks);
  return result;
}

function resultItems<T>(result: SearchPage<T>) {
  return (Array.isArray(result) ? result : result.items).slice(0, 20);
}

export function ScientificComposer({
  initialBlocks,
  searchProcesses,
  searchObjects,
  createProcess: _createProcess,
  createResource,
  excludeObjectId,
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
  createResource?: (
    draft: {
      title: string;
      tags: string[];
      properties_jsonb: JsonObject;
      process_field_definitions: JsonObject;
    },
    role: Exclude<ResourceRole, 'process'>,
    commandId?: string
  ) => Promise<ResearchObject>;
  excludeObjectId?: string | null;
  onChange: (blocks: JsonObject[]) => void;
  editable?: boolean;
}) {
  const editor = useCreateBlockNote({
    schema,
    initialContent: (initialBlocks.length
      ? initialBlocks
      : [{ type: 'bulletListItem', content: [], children: [] }]) as never
  });
  const [validationError, setValidationError] = useState<string | null>(null);
  const searchAbort = useRef<AbortController | null>(null);
  const searchSequence = useRef(0);
  const composing = useRef(false);
  const [, refreshSearch] = useState(0);
  const lastReferenceItems = useRef<DefaultReactSuggestionItem[]>([]);
  useEffect(() => {
    const dom = editor.prosemirrorView.dom;
    let compositionFrame = 0;
    const begin = () => {
      cancelAnimationFrame(compositionFrame);
      composing.current = true;
      searchAbort.current?.abort();
    };
    const end = () => {
      composing.current = false;
      // Wait for the final native input/ProseMirror transaction, then invalidate
      // getItems even when the final query string has already been observed.
      compositionFrame = requestAnimationFrame(() => {
        editor.prosemirrorView.dispatch(editor.prosemirrorView.state.tr);
        refreshSearch((generation) => generation + 1);
      });
    };
    dom.addEventListener('compositionstart', begin);
    dom.addEventListener('compositionend', end);
    return () => {
      dom.removeEventListener('compositionstart', begin);
      dom.removeEventListener('compositionend', end);
      searchAbort.current?.abort();
      cancelAnimationFrame(compositionFrame);
    };
  }, [editor]);
  useEditorChange((current) => {
    const next = current.document as unknown as JsonObject[];
    try {
      canonicalizeDocument(next);
      setValidationError(null);
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : '当前 bullet 结构需要修复');
    }
    onChange(next);
  }, editor);

  const searchReferences = async (query: string): Promise<DefaultReactSuggestionItem[]> => {
    if (composing.current) return lastReferenceItems.current;
    const parentIds = parentOccurrenceIds(editor);
    const activeOccurrences = currentOccurrences(editor.document as unknown as JsonObject[]);
    if (parentIds) {
      const allowed = new Set(parentIds);
      const items = activeOccurrences
        .filter((item) => allowed.has(item.occurrence_id))
        .map((item) => {
          const ordinal =
            activeOccurrences
              .filter(
                (candidate) =>
                  candidate.kind === item.kind && candidate.target_id === item.target_id
              )
              .indexOf(item) + 1;
          return {
            title: `${item.label_snapshot ?? '引用'} · 第${ordinal}次`,
            subtext: item.kind === 'process' ? '父级过程 occurrence' : '父级对象 occurrence',
            aliases: [item.label_snapshot ?? ''],
            onItemClick: () => {
              editor.insertInlineContent([
                ' ',
                {
                  type: 'propertyRef',
                  props: {
                    occurrenceId: item.occurrence_id,
                    lineId: crypto.randomUUID(),
                    label: item.label_snapshot ?? ''
                  }
                } as never,
                ' '
              ]);
              // Programmatic text insertion does not run handleTextInput.
              // Let the extension insert and own its trigger so selection
              // replaces exactly one separator and opens the menu immediately.
              editor.getExtension(SuggestionMenu)?.openSuggestionMenu('｜', {
                deleteTriggerCharacter: true,
                ignoreQueryLength: true
              });
            }
          };
        });
      const normalized = query.trim().toLocaleLowerCase();
      if (normalized.startsWith('data'))
        items.unshift({
          title: '@data',
          subtext: '记录描述性事实',
          aliases: ['data'],
          onItemClick: () => editor.insertInlineContent(['@data '])
        });
      if (normalized.startsWith('claim'))
        items.unshift({
          title: '@claim',
          subtext: '记录判断或解释',
          aliases: ['claim'],
          onItemClick: () => editor.insertInlineContent(['@claim '])
        });
      return items;
    }
    searchAbort.current?.abort();
    const controller = new AbortController();
    searchAbort.current = controller;
    const sequence = ++searchSequence.current;
    let processResult: SearchPage<ProcessDefinition>;
    let objectResult: SearchPage<ResearchObject>;
    try {
      [processResult, objectResult] = await Promise.all([
        searchProcesses(query, { offset: 0, limit: 21, signal: controller.signal }),
        searchObjects(query, { offset: 0, limit: 21, signal: controller.signal })
      ]);
    } catch (error) {
      if (
        controller.signal.aborted ||
        (error instanceof DOMException && error.name === 'AbortError')
      ) {
        return lastReferenceItems.current;
      }
      throw error;
    }
    if (controller.signal.aborted || sequence !== searchSequence.current)
      return lastReferenceItems.current;
    const items: DefaultReactSuggestionItem[] = [];
    resultItems(processResult).forEach((item) => {
      const target = item.process_definition;
      const occurrence: ScientificOccurrenceDraft = {
        occurrence_id: crypto.randomUUID(),
        kind: 'process',
        target_id: target.id,
        process_definition_version_id: item.current_version.id,
        label_snapshot: target.title,
        field_definitions: item.current_version.execution_field_definitions,
        values: {},
        status: 'recorded'
      };
      items.push({
        title: target.title,
        subtext: '过程 · 当前一级 bullet',
        aliases: [target.code, ...target.tags],
        onItemClick: () =>
          editor.insertInlineContent([' ', occurrenceRef(occurrence, target.title) as never, ' '])
      });
    });
    resultItems(objectResult)
      .filter((object) => object.authoring_kind !== 'data' && object.id !== excludeObjectId)
      .forEach((object) => {
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
      items.push({
        title: object.title,
        subtext:
          object.authoring_kind === 'sample'
            ? '样品 · 已保存记录，可作为中间体引用'
            : `${object.resource_role === 'equipment' ? '设备' : object.resource_role === 'material' ? '原料' : '资源'} · 当前一级 bullet`,
        aliases: [object.code, ...object.tags],
        onItemClick: () =>
          editor.insertInlineContent([' ', occurrenceRef(occurrence, object.title) as never, ' '])
      });
    });
    if (_createProcess && query.trim()) {
      items.push({
        title: `新建过程「${query.trim()}」`,
        subtext: '创建后插入当前一级 bullet',
        onItemClick: async () => {
          const created = await _createProcess(
            {
              title: query.trim(),
              tags: [],
              properties_jsonb: {},
              execution_field_definitions: { fields: [] }
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
            field_definitions: created.current_version.execution_field_definitions,
            values: {},
            status: 'recorded'
          };
          editor.insertInlineContent([' ', occurrenceRef(occurrence, target.title) as never, ' ']);
        }
      });
    }
    if (createResource && query.trim()) {
      (['material', 'equipment'] as const).forEach((role) => {
        items.push({
          title: `新建${role === 'material' ? '原料' : '设备'}「${query.trim()}」`,
          subtext: '创建后插入当前一级 bullet',
          onItemClick: async () => {
            const created = await createResource(
              {
                title: query.trim(),
                tags: [],
                properties_jsonb: {},
                process_field_definitions: { fields: [] }
              },
              role,
              crypto.randomUUID()
            );
            const occurrence: ScientificOccurrenceDraft = {
              occurrence_id: crypto.randomUUID(),
              kind: 'object',
              target_id: created.id,
              label_snapshot: created.title,
              field_definitions: created.process_field_definitions,
              values: {},
              status: 'recorded',
              binding: null
            };
            editor.insertInlineContent([' ', occurrenceRef(occurrence, created.title) as never, ' ']);
          }
        });
      });
    }
    const normalized = query.trim().toLocaleLowerCase();
    if (normalized.startsWith('data'))
      items.unshift({
        title: '@data',
        subtext: '记录描述性事实',
        onItemClick: () => editor.insertInlineContent(['@data '])
      });
    if (normalized.startsWith('claim'))
      items.unshift({
        title: '@claim',
        subtext: '记录判断或解释',
        onItemClick: () => editor.insertInlineContent(['@claim '])
      });
    if (composing.current && items.length === 0) return lastReferenceItems.current;
    lastReferenceItems.current = items;
    return items;
  };

  const properties = async (query: string): Promise<DefaultReactSuggestionItem[]> =>
    filterPropertyDefinitions(query).map((item) => ({
      title: item.zh,
      subtext: `${item.en} · ${item.dimension}${item.preferredUnit ? ` · ${item.preferredUnit}` : ''}`,
      aliases: [item.en, ...item.aliases],
      onItemClick: () => editor.insertInlineContent([`｜${item.zh}: `])
    }));

  return (
    <div
      data-testid='scientific-composer'
      data-scientific-composer
      className='scientific-editor-surface relative bg-background'
    >
      <BlockNoteView editor={editor} editable={editable}>
        <SuggestionMenuController triggerCharacter='@' getItems={searchReferences} />
        <SuggestionMenuController triggerCharacter='|' getItems={properties} />
        <SuggestionMenuController triggerCharacter='｜' getItems={properties} />
      </BlockNoteView>
      {validationError && (
        <p role='alert' className='border-t px-4 py-3 text-sm text-destructive'>
          {validationError}。请修复或删除失去父级引用的子 bullet 后再保存。
        </p>
      )}
    </div>
  );
}

export { propertyDictionary };
