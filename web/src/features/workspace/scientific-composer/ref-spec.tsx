'use client';

import { createExtension, type DefaultStyleSchema } from '@blocknote/core';
import { EditorState, Plugin, NodeSelection, TextSelection } from '@tiptap/pm/state';
import { closeHistory } from '@tiptap/pm/history';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import {
  createReactInlineContentSpec,
  type ReactCustomInlineContentRenderProps
} from '@blocknote/react';
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FocusEvent as ReactFocusEvent,
  type KeyboardEvent as ReactKeyboardEvent
} from 'react';
import { useTranslations } from 'next-intl';
import type { JsonObject, ScientificOccurrenceDraft, UsageFieldDefinition } from '@/lib/domain';
import { parseOccurrencePayload, remapLocalFieldIdentities } from '../scientific-document/model';

const refProps = {
  occurrenceId: { default: '' },
  targetId: { default: '' },
  label: { default: '' },
  payload: { default: '' }
} as const;
type RefConfig = { type: string; readonly propSchema: typeof refProps; content: 'none' };
type RefRenderProps = ReactCustomInlineContentRenderProps<RefConfig, DefaultStyleSchema>;

function isRefNode(name: string) {
  return ['processRef', 'objectRef'].includes(name);
}

function fields(value: JsonObject): UsageFieldDefinition[] {
  const nested = value.fields;
  if (Array.isArray(nested)) {
    return nested.filter((item): item is UsageFieldDefinition =>
      Boolean(item && typeof item === 'object' && typeof item.key === 'string')
    );
  }
  return Object.entries(value)
    .filter(([, item]) => Boolean(item && typeof item === 'object'))
    .map(([key, item]) => ({ key, ...(item as Omit<UsageFieldDefinition, 'key'>) }))
    .toSorted((left, right) => (left.order ?? 0) - (right.order ?? 0));
}

function displayValue(occurrence: ScientificOccurrenceDraft, field: UsageFieldDefinition) {
  const stored = occurrence.values[field.key];
  if (stored && typeof stored === 'object' && 'value' in stored) {
    return String((stored as { value: unknown }).value ?? '');
  }
  return stored == null ? '' : String(stored);
}

function writeValue(
  occurrence: ScientificOccurrenceDraft,
  field: UsageFieldDefinition,
  value: unknown
): ScientificOccurrenceDraft {
  const next = structuredClone(occurrence);
  if (value === '' || value === null || value === undefined) {
    delete next.values[field.key];
    return next;
  }
  if (occurrence.kind === 'object') {
    next.values[field.key] = {
      value,
      ...(field.default_unit ? { unit: field.default_unit } : {})
    };
  } else {
    next.values[field.key] = value;
  }
  return next;
}

function focusSibling(current: HTMLElement, backwards: boolean) {
  // Scope Tab navigation to the composer that owns this Ref.  A page can
  // render more than one editor (for example in a Peek drawer); querying the
  // whole document would move focus into an unrelated editor.
  const scope = current.closest<HTMLElement>('[data-scientific-composer]') ?? current.ownerDocument;
  const slots = Array.from(scope.querySelectorAll<HTMLElement>('[data-scientific-slot="true"]'));
  const index = slots.indexOf(current);
  const target = slots[index + (backwards ? -1 : 1)];
  if (!target) return false;
  target.focus();
  if (target instanceof HTMLInputElement) target.select();
  return true;
}

function PropertySlot({
  occurrence,
  field,
  label,
  commit,
  editor,
  getPos,
  onLeave
}: {
  occurrence: ScientificOccurrenceDraft;
  field: UsageFieldDefinition;
  label: string;
  commit: (value: unknown) => void;
  editor: RefRenderProps['editor'];
  getPos: () => number | undefined;
  onLeave?: (event: ReactFocusEvent<HTMLElement>) => void;
}) {
  const t = useTranslations('ProductCompletion.composer');
  const committed = displayValue(occurrence, field);
  const [draft, setDraft] = useState(committed);
  const [isComposing, setIsComposing] = useState(false);
  useEffect(() => {
    if (!isComposing) setDraft(committed);
  }, [committed, isComposing]);
  const common = {
    'data-scientific-slot': 'true',
    'data-occurrence-id': occurrence.occurrence_id,
    'data-field-key': field.key,
    'aria-label': `${label} ${field.label}`,
    disabled: !editor.isEditable,
    className:
      'h-7 min-w-16 max-w-[22rem] rounded border border-transparent bg-transparent px-1 text-sm outline-none focus:border-ring focus:bg-background focus:ring-2 focus:ring-ring',
    onFocus: () => editor.transact((tr) => closeHistory(tr)),
    onBlur: onLeave,
    onKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => {
      if ((event.nativeEvent as KeyboardEvent).isComposing) return;
      if (event.key === 'Tab') {
        if (focusSibling(event.currentTarget, event.shiftKey)) event.preventDefault();
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        event.currentTarget.blur();
        const pos = getPos();
        if (typeof pos === 'number') {
          editor.transact((tr) => closeHistory(tr.setSelection(NodeSelection.create(tr.doc, pos))));
          editor.prosemirrorView.focus();
        }
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        if (event.shiftKey) editor.redo();
        else editor.undo();
        return;
      }
      if (event.ctrlKey && event.key.toLowerCase() === 'y') {
        event.preventDefault();
        editor.redo();
      }
    }
  } as const;
  if (field.value_type === 'boolean') {
    return (
      <label className='inline-flex items-baseline gap-0.5 text-xs'>
        <span className='text-muted-foreground'>{field.label}</span>
        <select
          {...common}
          value={committed === '' ? '' : committed === 'true' ? 'true' : 'false'}
          onChange={(event) =>
            commit(event.target.value === '' ? '' : event.target.value === 'true')
          }
        >
          <option value=''>—</option>
          <option value='true'>{t('yes')}</option>
          <option value='false'>{t('no')}</option>
        </select>
      </label>
    );
  }
  if (field.value_type === 'select') {
    return (
      <label className='inline-flex items-baseline gap-0.5 text-xs'>
        <span className='text-muted-foreground'>{field.label}</span>
        <select {...common} value={draft} onChange={(event) => commit(event.target.value)}>
          <option value=''>—</option>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className='inline-flex items-baseline gap-0.5 text-xs'>
      <span className='text-muted-foreground'>{field.label}</span>
      <input
        data-scientific-slot='true'
        data-occurrence-id={occurrence.occurrence_id}
        data-field-key={field.key}
        aria-label={`${label} ${field.label}`}
        disabled={!editor.isEditable}
        className='h-7 min-w-16 max-w-[22rem] rounded border border-transparent bg-transparent px-1 text-sm outline-none focus:border-ring focus:bg-background focus:ring-2 focus:ring-ring'
        value={draft}
        inputMode={field.value_type === 'number' ? 'decimal' : undefined}
        placeholder={field.required ? t('required') : '—'}
        onFocus={() => editor.transact((tr) => closeHistory(tr))}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={(event) => {
          setIsComposing(false);
          setDraft(event.currentTarget.value);
          commit(event.currentTarget.value);
        }}
        onChange={(event) => {
          setDraft(event.currentTarget.value);
          if (!(event.nativeEvent as InputEvent).isComposing && !isComposing) {
            commit(event.currentTarget.value);
          }
        }}
        onBlur={onLeave}
        onKeyDown={(event) => {
          if ((event.nativeEvent as KeyboardEvent).isComposing) return;
          if (event.key === 'Tab') {
            if (focusSibling(event.currentTarget, event.shiftKey)) event.preventDefault();
            return;
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            event.currentTarget.blur();
            const pos = getPos();
            if (typeof pos === 'number') {
              editor.transact((tr) =>
                closeHistory(tr.setSelection(NodeSelection.create(tr.doc, pos)))
              );
              editor.prosemirrorView.focus();
            }
            return;
          }
          if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
            event.preventDefault();
            if (event.shiftKey) editor.redo();
            else editor.undo();
            return;
          }
          if (event.ctrlKey && event.key.toLowerCase() === 'y') {
            event.preventDefault();
            editor.redo();
            return;
          }
          const atStart = event.currentTarget.selectionStart === 0;
          const atEnd = event.currentTarget.selectionEnd === event.currentTarget.value.length;
          if ((event.key === 'ArrowLeft' && atStart) || (event.key === 'ArrowRight' && atEnd)) {
            // Arrow keys leave the atomic Ref at its boundary.  They must not
            // jump directly to another Ref's slot; the intervening document
            // text remains part of the editor's normal selection model.
            const pos = getPos();
            if (typeof pos === 'number') {
              event.preventDefault();
              const target = event.key === 'ArrowLeft' ? pos : pos + 1;
              editor.transact((tr) =>
                tr.setSelection(
                  TextSelection.near(tr.doc.resolve(target), event.key === 'ArrowLeft' ? -1 : 1)
                )
              );
              editor.prosemirrorView.focus();
            }
          }
        }}
      />
      {field.default_unit && <span>{field.default_unit}</span>}
    </label>
  );
}

function RefView({ inlineContent, updateInlineContent, editor, getPos }: RefRenderProps) {
  const t = useTranslations('ProductCompletion.composer');
  const occurrence = useMemo(
    () => parseOccurrencePayload(inlineContent.props.payload),
    [inlineContent.props.payload]
  );
  const activeField = useRef<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [fieldMenuKey, setFieldMenuKey] = useState<string | null>(null);
  const [newLabel, setNewLabel] = useState('');
  const [newType, setNewType] = useState<UsageFieldDefinition['value_type']>('text');
  const [newUnit, setNewUnit] = useState('');
  const [newOptions, setNewOptions] = useState('');
  const newLabelRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (adding) newLabelRef.current?.focus();
  }, [adding]);
  useEffect(() => {
    if (!activeField.current) return;
    const selector = `[data-occurrence-id="${CSS.escape(inlineContent.props.occurrenceId)}"][data-field-key="${CSS.escape(activeField.current)}"]`;
    const scope =
      editor.prosemirrorView.dom.closest<HTMLElement>('[data-scientific-composer]') ?? document;
    const element = scope.querySelector<HTMLInputElement>(selector);
    if (element && document.activeElement !== element) element.focus({ preventScroll: true });
  }, [editor.prosemirrorView, inlineContent.props.occurrenceId]);
  useEffect(() => {
    const root = editor.prosemirrorView.dom;
    const closeWhenAnotherRefActivates = (event: Event) => {
      const occurrenceId = (event as CustomEvent<{ occurrenceId: string }>).detail?.occurrenceId;
      if (occurrenceId && occurrenceId !== inlineContent.props.occurrenceId) {
        setEditing(false);
        setAdding(false);
        setFieldMenuKey(null);
      }
    };
    root.addEventListener('scientific-ref-focus', closeWhenAnotherRefActivates);
    return () => root.removeEventListener('scientific-ref-focus', closeWhenAnotherRefActivates);
  }, [editor.prosemirrorView, inlineContent.props.occurrenceId]);
  if (!occurrence) {
    return (
      <span className='rounded bg-destructive/10 px-1 text-destructive'>{t('invalidRef')}</span>
    );
  }
  const definitions = fields(occurrence.field_definitions);
  const visibleDefinitions = editing
    ? definitions
    : definitions.filter((field) => displayValue(occurrence, field) !== '');
  const updateOccurrence = (next: ScientificOccurrenceDraft) => {
    const pos = getPos();
    const props = { ...inlineContent.props, payload: JSON.stringify(next) };
    if (typeof pos === 'number') {
      // Updating attrs in place keeps the atomic Ref node and its mapped
      // selection stable while a Slot is being edited.  Falling back to the
      // public helper is only needed during initial NodeView mounting.
      editor.transact((transaction) => {
        transaction.setNodeMarkup(pos, undefined, props);
      });
      return;
    }
    updateInlineContent({ type: inlineContent.type, props });
  };
  const updateField = (field: UsageFieldDefinition, value: unknown) => {
    const next = writeValue(occurrence, field, value);
    updateOccurrence(next);
  };
  const selectOccurrence = () => {
    // Bubble through the editor root so two composers on the same page never
    // steal each other's active Ref.  The old document-level event made a Peek
    // editor and the main editor race each other for focus state.
    editor.prosemirrorView.dom.dispatchEvent(
      new CustomEvent('scientific-ref-focus', {
        bubbles: true,
        detail: { occurrenceId: occurrence.occurrence_id }
      })
    );
    setEditing(true);
  };
  const localFields = definitions.filter((field) => field.source === 'local');
  const updateLocalField = (field: UsageFieldDefinition, patch: Partial<UsageFieldDefinition>) => {
    const next = structuredClone(occurrence);
    next.field_definitions = {
      fields: definitions.map((item) => (item.key === field.key ? { ...item, ...patch } : item))
    };
    updateOccurrence(next);
  };
  const moveLocalField = (field: UsageFieldDefinition, delta: -1 | 1) => {
    const index = localFields.findIndex((item) => item.key === field.key);
    const nextIndex = index + delta;
    if (index < 0 || nextIndex < 0 || nextIndex >= localFields.length) return;
    const reordered = [...localFields];
    [reordered[index], reordered[nextIndex]] = [reordered[nextIndex], reordered[index]];
    const template = definitions.filter((item) => item.source !== 'local');
    const next = structuredClone(occurrence);
    next.field_definitions = {
      fields: [...template, ...reordered].map((item, order) => ({ ...item, order }))
    };
    updateOccurrence(next);
  };
  const removeLocalField = (field: UsageFieldDefinition) => {
    if (
      displayValue(occurrence, field) !== '' &&
      !window.confirm(t('deleteConfirm', { label: field.label }))
    )
      return;
    const next = structuredClone(occurrence);
    next.field_definitions = { fields: definitions.filter((item) => item.key !== field.key) };
    delete next.values[field.key];
    updateOccurrence(next);
  };
  const addLocalField = () => {
    const label = newLabel.trim();
    if (!label || (newType === 'select' && !newOptions.split(',').some((item) => item.trim())))
      return;
    const fieldId = crypto.randomUUID();
    const next = structuredClone(occurrence);
    next.field_definitions = {
      fields: [
        ...definitions,
        {
          key: `local_${fieldId}`,
          label,
          value_type: newType,
          source: 'local',
          owner_id: null,
          field_id: fieldId,
          default_unit: newUnit.trim() || null,
          options:
            newType === 'select'
              ? newOptions
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean)
              : [],
          required: false,
          order: definitions.length
        }
      ]
    };
    updateOccurrence(next);
    setNewLabel('');
    setNewUnit('');
    setNewOptions('');
    setAdding(false);
  };
  const handleLeave = (event: ReactFocusEvent<HTMLElement>) => {
    if (
      !event.currentTarget.closest('.scientific-ref')?.contains(event.relatedTarget as Node | null)
    ) {
      setEditing(false);
      setAdding(false);
      setFieldMenuKey(null);
    }
  };
  return (
    <span
      contentEditable={false}
      data-scientific-ref={occurrence.kind}
      data-occurrence-id={occurrence.occurrence_id}
      role='group'
      tabIndex={-1}
      className={`scientific-ref relative mx-0.5 inline-flex max-w-full flex-wrap items-baseline gap-1 rounded-md px-1 py-0.5 align-baseline transition-colors motion-reduce:transition-none ${editing ? 'bg-primary/5 ring-1 ring-primary/35' : 'hover:bg-muted/50'}`}
    >
      <button
        type='button'
        disabled={!editor.isEditable}
        className='font-medium text-primary'
        aria-label={`选择${occurrence.kind === 'process' ? '过程' : '对象'} ${inlineContent.props.label}`}
        onMouseDown={selectOccurrence}
        onFocus={selectOccurrence}
      >
        {occurrence.kind === 'process' ? '/' : '@'}
        {inlineContent.props.label}
      </button>
      {visibleDefinitions.map((field) => (
        <span
          key={field.key}
          onFocus={() => {
            activeField.current = field.key;
          }}
        >
          <PropertySlot
            occurrence={occurrence}
            field={field}
            label={inlineContent.props.label}
            commit={(value) => updateField(field, value)}
            editor={editor}
            getPos={getPos}
            onLeave={handleLeave}
          />
          {editing && field.source === 'local' && fieldMenuKey === field.key && (
            <span
              className='absolute z-20 mt-7 inline-flex items-center gap-1 rounded-lg border bg-popover p-1 text-xs shadow-lg'
              data-ref-menu='true'
              role='menu'
              tabIndex={-1}
              onMouseDown={(event) => event.preventDefault()}
              onBlur={handleLeave}
            >
              <input
                aria-label={t('rename', { label: field.label })}
                className='h-7 w-28 rounded border bg-background px-1.5'
                value={field.label}
                onChange={(event) => updateLocalField(field, { label: event.target.value })}
              />
              <button
                type='button'
                className='rounded px-1.5 py-1 hover:bg-accent disabled:opacity-40'
                disabled={localFields[0]?.key === field.key}
                onClick={() => moveLocalField(field, -1)}
              >
                ↑
              </button>
              <button
                type='button'
                className='rounded px-1.5 py-1 hover:bg-accent disabled:opacity-40'
                disabled={localFields.at(-1)?.key === field.key}
                onClick={() => moveLocalField(field, 1)}
              >
                ↓
              </button>
              <button
                type='button'
                className='rounded px-1.5 py-1 text-destructive hover:bg-destructive/10'
                aria-label={t('delete', { label: field.label })}
                onClick={() => removeLocalField(field)}
              >
                ×
              </button>
            </span>
          )}
          {editing && field.source === 'local' && (
            <button
              type='button'
              className='rounded px-1 text-muted-foreground hover:bg-accent'
              aria-label={t('fieldMenu', { label: field.label })}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() =>
                setFieldMenuKey((current) => (current === field.key ? null : field.key))
              }
            >
              ···
            </button>
          )}
        </span>
      ))}
      {editing &&
        editor.isEditable &&
        (adding ? (
          <span
            className='absolute z-20 mt-7 inline-flex max-w-[min(24rem,90vw)] flex-wrap items-center gap-1 rounded-lg border bg-popover p-2 shadow-lg'
            data-ref-menu='true'
            role='menu'
            tabIndex={-1}
            onBlur={handleLeave}
            onMouseDown={(event) => event.preventDefault()}
          >
            <input
              ref={newLabelRef}
              aria-label={t('localName')}
              className='h-6 w-24 px-1 text-xs'
              value={newLabel}
              onChange={(event) => setNewLabel(event.target.value)}
              placeholder={t('localName')}
            />
            <select
              aria-label={t('localType')}
              className='h-6 text-xs'
              value={newType}
              onChange={(event) =>
                setNewType(event.target.value as UsageFieldDefinition['value_type'])
              }
            >
              <option value='text'>文本</option>
              <option value='number'>数字</option>
              <option value='boolean'>布尔值</option>
              <option value='select'>选项</option>
            </select>
            {newType !== 'boolean' && newType !== 'select' && (
              <input
                aria-label={t('localUnit')}
                className='h-6 w-16 px-1 text-xs'
                value={newUnit}
                onChange={(event) => setNewUnit(event.target.value)}
                placeholder={t('localUnit')}
              />
            )}
            {newType === 'select' && (
              <input
                aria-label={t('localOptions')}
                className='h-6 w-36 px-1 text-xs'
                value={newOptions}
                onChange={(event) => setNewOptions(event.target.value)}
                placeholder={t('localOptions')}
              />
            )}
            <button
              type='button'
              disabled={
                !newLabel.trim() ||
                (newType === 'select' && !newOptions.split(',').some((item) => item.trim()))
              }
              onClick={addLocalField}
            >
              {t('add')}
            </button>
            <button type='button' onClick={() => setAdding(false)}>
              {t('cancel')}
            </button>
          </span>
        ) : (
          <button
            type='button'
            className='rounded px-1.5 py-0.5 text-xs text-primary hover:bg-primary/10'
            onClick={() => setAdding(true)}
          >
            {t('addLocal')}
          </button>
        ))}
    </span>
  );
}

function externalRef({ inlineContent }: RefRenderProps) {
  const occurrence = parseOccurrencePayload(inlineContent.props.payload);
  const rendered = fields(occurrence?.field_definitions ?? {})
    .map((field) => {
      const value = occurrence ? displayValue(occurrence, field) : '';
      return value ? `${field.label} ${value}${field.default_unit ?? ''}` : '';
    })
    .filter(Boolean)
    .join(' · ');
  return (
    <span>
      {inlineContent.type === 'processRef' ? '/' : '@'}
      {inlineContent.props.label}
      {rendered ? ` ${rendered}` : ''}
    </span>
  );
}

export const ProcessRef = createReactInlineContentSpec(
  { type: 'processRef', propSchema: refProps, content: 'none' } as const,
  { render: RefView, toExternalHTML: externalRef }
);

export const ObjectRef = createReactInlineContentSpec(
  { type: 'objectRef', propSchema: refProps, content: 'none' } as const,
  { render: RefView, toExternalHTML: externalRef }
);

function ghostDecorations(state: EditorState) {
  const { $from, empty } = state.selection;
  if (!empty || !$from.parent.isTextblock) return DecorationSet.empty;
  const before = $from.parent.textBetween(0, $from.parentOffset, '\0', '\0');
  const match = before.match(/(?:^|\s)([@/])([^\s]*)$/);
  if (!match) return DecorationSet.empty;
  const node = document.createElement('span');
  node.className = 'scientific-composer-ghost';
  node.setAttribute('aria-hidden', 'true');
  node.textContent = match[1] === '@' ? '  对象 · 选择或新建' : '  过程 · 选择或新建';
  return DecorationSet.create(state.doc, [
    Decoration.widget($from.pos, node, { side: 1, ignoreSelection: true })
  ]);
}

export const createRefIdentityExtension = createExtension(() => ({
  key: 'scientificRefIdentity',
  prosemirrorPlugins: [
    new Plugin({
      state: {
        init: (_config, state) => ghostDecorations(state),
        apply(transaction, value, _oldState, newState) {
          return transaction.docChanged || transaction.selectionSet
            ? ghostDecorations(newState)
            : value;
        }
      },
      props: {
        decorations(state) {
          return this.getState(state) ?? DecorationSet.empty;
        },
        handleClickOn(view, pos, node, nodePos) {
          if (!isRefNode(node.type.name)) return false;
          view.dispatch(
            closeHistory(view.state.tr.setSelection(NodeSelection.create(view.state.doc, nodePos)))
          );
          view.focus();
          return true;
        },
        handleKeyDown(view, event) {
          if (event.key !== 'Backspace' && event.key !== 'Delete') return false;
          const { selection } = view.state;
          let from: number | null = null;
          let to: number | null = null;
          if (selection instanceof NodeSelection && isRefNode(selection.node.type.name)) {
            from = selection.from;
            to = selection.to;
          } else if (selection.empty && event.key === 'Delete' && selection.$from.nodeAfter) {
            const node = selection.$from.nodeAfter;
            if (isRefNode(node.type.name)) {
              from = selection.from;
              to = selection.from + node.nodeSize;
            }
          } else if (selection.empty && event.key === 'Backspace' && selection.$from.nodeBefore) {
            const node = selection.$from.nodeBefore;
            if (isRefNode(node.type.name)) {
              from = selection.from - node.nodeSize;
              to = selection.from;
            }
          }
          if (from === null || to === null) return false;
          event.preventDefault();
          view.dispatch(closeHistory(view.state.tr.delete(from, to)).scrollIntoView());
          return true;
        }
      },
      appendTransaction(transactions, _oldState, newState) {
        if (!transactions.some((transaction) => transaction.docChanged)) return null;
        const pastedRanges: Array<{ from: number; to: number }> = [];
        for (const transaction of transactions) {
          if (transaction.getMeta('uiEvent') !== 'paste') continue;
          for (const stepMap of transaction.mapping.maps) {
            stepMap.forEach((_oldFrom, _oldTo, from, to) => pastedRanges.push({ from, to }));
          }
        }
        const seen = new Set<string>();
        const remapped = new Map<string, string>();
        const updates: Array<{ pos: number; attrs: Record<string, unknown> }> = [];
        newState.doc.descendants((node, pos) => {
          if (node.type.name !== 'processRef' && node.type.name !== 'objectRef') return;
          const oldId = String(node.attrs.occurrenceId ?? '');
          const pasted = pastedRanges.some((range) => pos >= range.from && pos <= range.to);
          if (!pasted && !seen.has(oldId)) {
            seen.add(oldId);
            return;
          }
          let occurrence = parseOccurrencePayload(node.attrs.payload);
          if (!occurrence) return;
          occurrence = remapLocalFieldIdentities(occurrence);
          const nextId = crypto.randomUUID();
          remapped.set(oldId, nextId);
          occurrence.occurrence_id = nextId;
          occurrence.execution_id = null;
          if (occurrence.binding) occurrence.binding.binding_id = null;
          updates.push({
            pos,
            attrs: { ...node.attrs, occurrenceId: nextId, payload: JSON.stringify(occurrence) }
          });
          seen.add(nextId);
        });
        if (!updates.length) return null;
        const tr = newState.tr;
        for (const update of updates) {
          const node = tr.doc.nodeAt(update.pos);
          if (!node) continue;
          const occurrence = parseOccurrencePayload(update.attrs.payload);
          if (occurrence?.binding) {
            const processOccurrenceId = remapped.get(occurrence.binding.process_occurrence_id);
            if (!processOccurrenceId) occurrence.binding = null;
            else occurrence.binding.process_occurrence_id = processOccurrenceId;
            update.attrs.payload = JSON.stringify(occurrence);
          }
          tr.setNodeMarkup(update.pos, undefined, update.attrs);
        }
        return tr;
      }
    })
  ]
}));
