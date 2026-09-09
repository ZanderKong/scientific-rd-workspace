'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { api, ApiError } from '@/lib/api-client';
import type {
  JsonObject,
  ObjectRevision,
  SampleRecord,
  SampleRecordCreatePayload
} from '@/lib/domain';
import {
  canonicalizeDocument,
  cloneDocumentForNewRecord,
  enrichDocument,
  parseOccurrencePayload
} from '../scientific-document/model';
import {
  deleteScientificDraft,
  readScientificBatchDraft,
  writeScientificBatchDraft
} from '../scientific-document/draft-store';

type Variable = {
  occurrenceIndex: number;
  occurrenceId: string;
  targetId: string;
  targetLabel: string;
  occurrenceLabel: string;
  fieldKey: string;
  fieldLabel: string;
  unit?: string | null;
  filled: boolean;
};

type BatchRow = {
  clientRowId: string;
  title: string;
  note: string;
  blocks: JsonObject[];
};

function visit(value: unknown, callback: (node: JsonObject) => void) {
  if (Array.isArray(value)) {
    value.forEach((item) => visit(item, callback));
    return;
  }
  if (!value || typeof value !== 'object') return;
  const node = value as JsonObject;
  callback(node);
  Object.values(node).forEach((item) => visit(item, callback));
}

function updateOccurrenceValue(
  blocks: JsonObject[],
  occurrenceIndex: number,
  fieldKey: string,
  value: string
) {
  const next = structuredClone(blocks);
  let index = -1;
  visit(next, (node) => {
    if (node.type !== 'processRef' && node.type !== 'objectRef') return;
    index += 1;
    const props = node.props as JsonObject | undefined;
    if (!props || index !== occurrenceIndex) return;
    const occurrence = parseOccurrencePayload(props.payload);
    if (!occurrence) return;
    const previous = occurrence.values[fieldKey];
    if (value === '') {
      const values = { ...occurrence.values };
      delete values[fieldKey];
      occurrence.values = values;
      props.payload = JSON.stringify(occurrence);
      return;
    }
    occurrence.values = {
      ...occurrence.values,
      [fieldKey]:
        occurrence.kind === 'object'
          ? {
              value,
              ...(previous && typeof previous === 'object' && 'unit' in previous
                ? { unit: previous.unit }
                : {})
            }
          : value
    };
    props.payload = JSON.stringify(occurrence);
  });
  return next;
}

function appendNote(blocks: JsonObject[], note: string) {
  if (!note.trim()) return blocks;
  return [
    ...blocks,
    {
      type: 'paragraph',
      content: [{ type: 'text', text: note.trim(), styles: {} }]
    }
  ];
}

function batchValue(value: unknown) {
  if (value && typeof value === 'object' && 'value' in value) {
    return String((value as { value: unknown }).value ?? '');
  }
  return value === null || value === undefined ? '' : String(value);
}

function createRow(source: SampleRecord, index: number): BatchRow {
  return {
    clientRowId: crypto.randomUUID(),
    title: `${source.sample.title} ${index + 1}`,
    note: '',
    blocks: cloneDocumentForNewRecord(enrichDocument(source).document.blocks)
  };
}

function variablesFor(record: SampleRecord): Variable[] {
  const targetCounts = new Map<string, number>();
  return record.occurrences.flatMap((occurrence, occurrenceIndex) => {
    const count = (targetCounts.get(occurrence.target_id) ?? 0) + 1;
    targetCounts.set(occurrence.target_id, count);
    const fields = Array.isArray(occurrence.field_definitions.fields)
      ? occurrence.field_definitions.fields
      : Object.entries(occurrence.field_definitions).map(([key, value]) => ({
          key,
          ...(typeof value === 'object' && value ? value : {})
        }));
    return fields.flatMap((raw) => {
      const field = raw as JsonObject;
      const key = String(field.key ?? '');
      const value = occurrence.values[key];
      if (!key) return [];
      return [
        {
          occurrenceIndex,
          occurrenceId: occurrence.occurrence_id,
          targetId: occurrence.target_id,
          targetLabel: occurrence.label_snapshot ?? 'Ref',
          occurrenceLabel: `${occurrence.label_snapshot ?? 'Ref'}${count > 1 ? ` ${count}` : ''}`,
          fieldKey: key,
          fieldLabel: String(field.label ?? key),
          unit: typeof field.default_unit === 'string' ? field.default_unit : null,
          filled: value !== null && value !== undefined && value !== ''
        }
      ];
    });
  });
}

export function SampleBatchEditor({ sampleId, revision }: { sampleId: string; revision?: number }) {
  const t = useTranslations('ProductCompletion.batch');
  const [source, setSource] = useState<SampleRecord | null>(null);
  const [sourceRevision, setSourceRevision] = useState<ObjectRevision | null>(null);
  const [rows, setRows] = useState<BatchRow[]>([]);
  const [selectedVariables, setSelectedVariables] = useState<string[]>([]);
  const [results, setResults] = useState<SampleRecord[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitKey = useRef(crypto.randomUUID());
  const draftKey = `sample-batch:${sampleId}:${revision ?? 'current'}`;

  useEffect(() => {
    Promise.all([api.listRevisions(sampleId), api.getSampleRecord(sampleId)])
      .then(async ([revisions, current]) => {
        const selected = revision
          ? revisions.find((item) => item.revision_number === revision)
          : revisions.at(-1);
        if (!selected) throw new Error(t('unavailable'));
        const record = revision ? await api.getSampleRecordRevision(sampleId, revision) : current;
        setSource(record);
        setSourceRevision(selected);
        const draft = await readScientificBatchDraft(draftKey);
        if (draft?.source_revision_id === selected.id) {
          submitKey.current = draft.submit_key;
          setRows(draft.rows);
        } else {
          setRows(Array.from({ length: 3 }, (_, index) => createRow(record, index)));
        }
        setSelectedVariables(
          variablesFor(record)
            .filter((item) => item.filled)
            .map((item) => `${item.occurrenceId}:${item.fieldKey}`)
        );
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : 'Request failed'));
  }, [draftKey, revision, sampleId, t]);

  useEffect(() => {
    if (!source?.sample.project_scope_id || !sourceRevision || rows.length === 0 || results.length)
      return;
    const timeout = window.setTimeout(() => {
      writeScientificBatchDraft({
        format_version: 1,
        key: draftKey,
        project_id: source.sample.project_scope_id!,
        source_sample_id: source.sample.id,
        source_revision_id: sourceRevision.id,
        saved_at: new Date().toISOString(),
        submit_key: submitKey.current,
        rows
      }).catch(() => undefined);
    }, 400);
    return () => window.clearTimeout(timeout);
  }, [draftKey, results.length, rows, source, sourceRevision]);

  const variables = useMemo(() => (source ? variablesFor(source) : []), [source]);
  const displayed = variables.filter((item) =>
    selectedVariables.includes(`${item.occurrenceId}:${item.fieldKey}`)
  );
  const rowOccurrences = useMemo(
    () =>
      new Map(
        rows.map((row) => [row.clientRowId, canonicalizeDocument(row.blocks).occurrences] as const)
      ),
    [rows]
  );

  function updateRow(id: string, update: (row: BatchRow) => BatchRow) {
    setRows((current) => current.map((row) => (row.clientRowId === id ? update(row) : row)));
  }

  function pasteGrid(startRow: number, startColumn: number, text: string) {
    const cells = text
      .replace(/\r/g, '')
      .split('\n')
      .filter((line, index, lines) => line.length > 0 || index < lines.length - 1)
      .map((line) => line.split('\t'));
    if (cells.length === 1 && cells[0].length === 1) return false;
    setRows((current) => {
      const next = [...current];
      for (const [rowOffset, values] of cells.entries()) {
        const index = startRow + rowOffset;
        if (!next[index]) break;
        let blocks = next[index].blocks;
        for (const [columnOffset, value] of values.entries()) {
          const variable = displayed[startColumn + columnOffset];
          if (!variable) break;
          blocks = updateOccurrenceValue(
            blocks,
            variable.occurrenceIndex,
            variable.fieldKey,
            value
          );
        }
        next[index] = { ...next[index], blocks };
      }
      return next;
    });
    return true;
  }

  async function submit() {
    if (!source || !sourceRevision || !source.sample.project_scope_id) return;
    setSaving(true);
    setError(null);
    try {
      const payloadRows = rows.map((row) => {
        const canonical = canonicalizeDocument(appendNote(row.blocks, row.note));
        const record: SampleRecordCreatePayload = {
          project_scope_id: source.sample.project_scope_id!,
          sample: {
            title: row.title.trim(),
            status: 'draft',
            tags: source.sample.tags
          },
          ...canonical,
          change_note: `create from Sample revision ${sourceRevision.revision_number}`
        };
        return { client_row_id: row.clientRowId, record };
      });
      const created = await api.createSampleBatch(
        {
          project_scope_id: source.sample.project_scope_id,
          source_sample_id: source.sample.id,
          source_revision_id: sourceRevision.id,
          rows: payloadRows
        },
        submitKey.current
      );
      setResults(created.rows.map((item) => item.record));
      await deleteScientificDraft(draftKey);
    } catch (cause) {
      setError(
        cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed'
      );
    } finally {
      setSaving(false);
    }
  }


  if (!source || !sourceRevision)
    return <main className='mx-auto max-w-[1480px] p-8'>{error ?? t('loading')}</main>;

  return (
    <main className='mx-auto w-full max-w-[1480px] space-y-5 px-4 py-8'>
      <header>
        <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
          {t('eyebrow')}
        </p>
        <h1 className='mt-2 text-2xl font-semibold'>
          {t('title', { title: source.sample.title })}
        </h1>
        <p className='mt-1 text-sm text-muted-foreground'>
          {t('description', { revision: sourceRevision.revision_number })}
        </p>
      </header>
      <details className='rounded-lg border p-3'>
        <summary className='cursor-pointer text-sm font-medium'>{t('columns')}</summary>
        <div className='mt-3 flex flex-wrap gap-3'>
          {variables.map((variable) => {
            const key = `${variable.occurrenceId}:${variable.fieldKey}`;
            return (
              <label key={key} className='flex items-center gap-2 text-sm'>
                <input
                  type='checkbox'
                  checked={selectedVariables.includes(key)}
                  onChange={(event) =>
                    setSelectedVariables((current) =>
                      event.target.checked
                        ? [...current, key]
                        : current.filter((item) => item !== key)
                    )
                  }
                />
                {variable.occurrenceLabel} · {variable.fieldLabel}
              </label>
            );
          })}
        </div>
      </details>
      <div className='overflow-x-auto rounded-xl border'>
        <table className='min-w-full border-collapse text-sm'>
          <thead>
            <tr className='bg-muted/40'>
              <th rowSpan={2} className='border-b border-r p-2 text-left'>
                {t('name')}
              </th>
              {displayed.map((variable) => (
                <th key={`${variable.occurrenceId}:group`} className='border-b border-r p-2'>
                  {variable.occurrenceLabel}
                </th>
              ))}
              <th rowSpan={2} className='border-b border-r p-2 text-left'>
                {t('note')}
              </th>
              <th rowSpan={2} aria-label='Actions' className='border-b p-2' />
            </tr>
            <tr className='bg-muted/20'>
              {displayed.map((variable) => (
                <th
                  key={`${variable.occurrenceId}:${variable.fieldKey}`}
                  className='border-b border-r p-2 font-normal'
                >
                  {variable.fieldLabel}
                  {variable.unit ? ` (${variable.unit})` : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={row.clientRowId}>
                <td className='border-b border-r p-1'>
                  <input
                    aria-label='Sample name'
                    className='h-9 min-w-48 rounded border bg-background px-2'
                    value={row.title}
                    onChange={(event) =>
                      updateRow(row.clientRowId, (current) => ({
                        ...current,
                        title: event.target.value
                      }))
                    }
                  />
                </td>
                {displayed.map((variable, columnIndex) => (
                  <td
                    key={`${row.clientRowId}:${variable.occurrenceId}:${variable.fieldKey}`}
                    className='border-b border-r p-1'
                  >
                    <input
                      aria-label={`${variable.occurrenceLabel} ${variable.fieldLabel}`}
                      className='h-9 min-w-28 rounded border bg-background px-2'
                      value={batchValue(
                        rowOccurrences.get(row.clientRowId)?.[variable.occurrenceIndex]?.values[
                          variable.fieldKey
                        ] ?? ''
                      )}
                      onChange={(event) =>
                        updateRow(row.clientRowId, (current) => ({
                          ...current,
                          blocks: updateOccurrenceValue(
                            current.blocks,
                            variable.occurrenceIndex,
                            variable.fieldKey,
                            event.target.value
                          )
                        }))
                      }
                      onPaste={(event) => {
                        if (pasteGrid(rowIndex, columnIndex, event.clipboardData.getData('text'))) {
                          event.preventDefault();
                        }
                      }}
                    />
                  </td>
                ))}
                <td className='border-b border-r p-1'>
                  <input
                    aria-label='Note'
                    className='h-9 min-w-48 rounded border bg-background px-2'
                    value={row.note}
                    onChange={(event) =>
                      updateRow(row.clientRowId, (current) => ({
                        ...current,
                        note: event.target.value
                      }))
                    }
                  />
                </td>
                <td className='border-b p-1'>
                  <Button
                    type='button'
                    variant='ghost'
                    disabled={rows.length >= 100}
                    onClick={() =>
                      setRows((current) => {
                        const index = current.findIndex(
                          (item) => item.clientRowId === row.clientRowId
                        );
                        const copy = {
                          ...row,
                          clientRowId: crypto.randomUUID(),
                          title: `${row.title} copy`,
                          blocks: cloneDocumentForNewRecord(row.blocks)
                        };
                        return [...current.slice(0, index + 1), copy, ...current.slice(index + 1)];
                      })
                    }
                  >
                    {t('copy')}
                  </Button>
                  <Button
                    type='button'
                    variant='ghost'
                    disabled={rows.length === 1}
                    onClick={() =>
                      setRows((current) =>
                        current.filter((item) => item.clientRowId !== row.clientRowId)
                      )
                    }
                  >
                    {t('delete')}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className='flex flex-wrap gap-2'>
        <Button
          type='button'
          variant='outline'
          disabled={rows.length >= 100}
          onClick={() => setRows((current) => [...current, createRow(source, current.length)])}
        >
          {t('addRow')}
        </Button>
        <Button
          type='button'
          disabled={saving || rows.some((row) => !row.title.trim())}
          onClick={submit}
        >
          {saving ? t('creating') : t('create', { count: rows.length })}
        </Button>
      </div>
      {error && (
        <p role='alert' className='text-sm text-destructive'>
          {error}
        </p>
      )}
      {results.length > 0 && (
        <section className='rounded-xl border p-4'>
          <h2 className='font-semibold'>{t('success')}</h2>
          <div className='mt-2 grid gap-2'>
            {results.map((record) => (
              <Link
                key={record.sample.id}
                className='text-sm text-primary hover:underline'
                href={`/dashboard/samples/${record.sample.id}`}
              >
                {record.sample.code} · {record.sample.title}
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
