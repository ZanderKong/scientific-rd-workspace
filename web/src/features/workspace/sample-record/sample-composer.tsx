'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import { api, ApiError } from '@/lib/api-client';
import type { JsonObject, SampleRecord } from '@/lib/domain';
import {
  canonicalizeDocument,
  cloneDocumentForNewRecord,
  enrichDocument
} from '../scientific-document/model';
import {
  deleteScientificDraft,
  readScientificDraft,
  type ScientificLocalDraft,
  writeScientificDraft
} from '../scientific-document/draft-store';

const ScientificComposer = dynamic(
  () =>
    import('../scientific-composer/scientific-composer').then(
      (module) => module.ScientificComposer
    ),
  {
    ssr: false,
    loading: () => (
      <div className='rounded-xl border p-6 text-sm text-muted-foreground'>Loading editor…</div>
    )
  }
);

export function SampleComposer({
  projectId,
  initialRecord,
  editing = false,
  readOnly = false
}: {
  projectId: string;
  initialRecord?: SampleRecord | null;
  editing?: boolean;
  readOnly?: boolean;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const initialDraft = useMemo(
    () => (initialRecord ? enrichDocument(initialRecord) : null),
    [initialRecord]
  );
  const initialBlocks = useMemo(() => {
    if (!initialDraft)
      return [{ type: 'bulletListItem', content: [], children: [] }] as JsonObject[];
    return editing || readOnly
      ? initialDraft.document.blocks
      : cloneDocumentForNewRecord(initialDraft.document.blocks);
  }, [editing, initialDraft, readOnly]);
  const [title, setTitle] = useState(initialRecord?.sample.title ?? '');
  const [status, setStatus] = useState(initialRecord?.sample.status ?? 'draft');
  const [tags, setTags] = useState(initialRecord?.sample.tags.join(',') ?? '样品');
  const [blocks, setBlocks] = useState<JsonObject[]>(initialBlocks);
  const [producerProcessOccurrenceId, setProducerProcessOccurrenceId] = useState<string | null>(
    editing ? (initialRecord?.producer_process_occurrence_id ?? null) : null
  );
  const [baseRecordSha256, setBaseRecordSha256] = useState(
    editing ? (initialRecord?.record_sha256 ?? null) : null
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recoverableDraft, setRecoverableDraft] = useState<ScientificLocalDraft | null>(null);
  const [draftReady, setDraftReady] = useState(false);
  const [composerGeneration, setComposerGeneration] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [createdRecordId, setCreatedRecordId] = useState<string | null>(null);
  const createKey = useRef(crypto.randomUUID());
  const generation = useRef(0);
  const saveIntent = useRef<'save' | 'save-and-new' | 'save-and-batch'>('save');
  const recordId = initialRecord?.sample.id ?? createdRecordId;
  const isEditing = editing || Boolean(createdRecordId);
  const draftKey = recordId ? `sample:${recordId}` : `sample:new:${projectId}`;
  const processOccurrences = useMemo(() => {
    try {
      return canonicalizeDocument(blocks).occurrences.filter((item) => item.kind === 'process');
    } catch {
      return [];
    }
  }, [blocks]);

  function markDirty() {
    generation.current += 1;
    setDirty(true);
  }

  useEffect(() => {
    let active = true;
    readScientificDraft(draftKey)
      .then((draft) => {
        if (!active || !draft) return;
        setRecoverableDraft(draft);
      })
      .finally(() => {
        if (active) setDraftReady(true);
      });
    return () => {
      active = false;
    };
  }, [draftKey]);

  useEffect(() => {
    if (!draftReady || !dirty || readOnly || recoverableDraft) return;
    const timeout = window.setTimeout(() => {
      writeScientificDraft({
        format_version: 1,
        key: draftKey,
        record_id: recordId,
        project_id: projectId,
        base_record_sha256: baseRecordSha256,
        saved_at: new Date().toISOString(),
        title,
        status,
        tags,
        blocks,
        producer_process_occurrence_id: producerProcessOccurrenceId
      }).catch(() => undefined);
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [
    baseRecordSha256,
    blocks,
    draftKey,
    draftReady,
    dirty,
    projectId,
    producerProcessOccurrenceId,
    recordId,
    readOnly,
    recoverableDraft,
    status,
    tags,
    title
  ]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || !projectId) return;
    setSaving(true);
    setError(null);
    const savedGeneration = generation.current;
    const requestIntent = saveIntent.current;
    try {
      const canonical = canonicalizeDocument(blocks);
      const sample = {
        title: title.trim(),
        status,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      };
      const saved =
        isEditing && recordId && baseRecordSha256
          ? await api.updateSampleRecord(
              recordId,
              {
                sample,
                ...canonical,
                producer_process_occurrence_id: producerProcessOccurrenceId,
                base_record_sha256: baseRecordSha256,
                change_note: 'save scientific record'
              },
              baseRecordSha256
            )
          : await api.createSampleRecord(
              {
                project_scope_id: projectId,
                sample,
                ...canonical,
                producer_process_occurrence_id: producerProcessOccurrenceId,
                change_note: initialRecord ? 'create from sample draft' : 'create scientific record'
              },
              createKey.current
            );
      const hasNewerChanges = savedGeneration !== generation.current;
      if (isEditing) {
        setBaseRecordSha256(saved.record_sha256);
        if (!hasNewerChanges) setDirty(false);
      }
      if (!isEditing && saved.sample?.id) {
        setCreatedRecordId(saved.sample.id);
        setBaseRecordSha256(saved.record_sha256);
      }
      // A response may arrive after the user has typed more text. Keep the
      // local draft and current editor in that case; the autosave effect will
      // persist the newer generation instead of deleting it.
      if (!hasNewerChanges) await deleteScientificDraft(draftKey);
      if (requestIntent === 'save-and-new' && !hasNewerChanges) {
        router.push(
          `/dashboard/samples/new?project=${encodeURIComponent(projectId)}&from=${saved.sample.id}`
        );
      } else if (requestIntent === 'save-and-batch' && !hasNewerChanges) {
        router.push(`/dashboard/samples/${saved.sample.id}/batch`);
      } else if (!isEditing && !hasNewerChanges) {
        if (returnTo?.startsWith('/dashboard/')) {
          const separator = returnTo.includes('?') ? '&' : '?';
          router.push(`${returnTo}${separator}selectedSample=${saved.sample.id}`);
        } else {
          router.push(`/dashboard/samples/${saved.sample.id}`);
        }
      }
    } catch (cause) {
      setError(
        cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed'
      );
    } finally {
      saveIntent.current = 'save';
      setSaving(false);
    }
  }

  return (
    <main className='mx-auto w-full max-w-[960px] px-4 py-7 md:px-8 md:py-10'>
      <form onSubmit={save} className='space-y-5'>
        {recoverableDraft && (
          <section className='space-y-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm'>
            <p>
              发现 {new Date(recoverableDraft.saved_at).toLocaleString()} 保存的本地草稿。
              {recoverableDraft.base_record_sha256 !== baseRecordSha256
                ? ' 服务器版本已经变化，请先查看内容再决定。'
                : ''}
            </p>
            <details>
              <summary className='cursor-pointer font-medium'>查看本地草稿内容</summary>
              <pre className='mt-2 max-h-64 overflow-auto rounded bg-background/70 p-3 text-xs'>
                {JSON.stringify(
                  {
                    title: recoverableDraft.title,
                    status: recoverableDraft.status,
                    tags: recoverableDraft.tags,
                    blocks: recoverableDraft.blocks
                  },
                  null,
                  2
                )}
              </pre>
            </details>
            <span className='flex flex-wrap gap-2'>
              <Button
                type='button'
                variant='outline'
                onClick={() => {
                  setTitle(recoverableDraft.title);
                  setStatus(recoverableDraft.status);
                  setTags(recoverableDraft.tags);
                  setBlocks(recoverableDraft.blocks);
                  setProducerProcessOccurrenceId(
                    recoverableDraft.producer_process_occurrence_id ?? null
                  );
                  setComposerGeneration((current) => current + 1);
                  setRecoverableDraft(null);
                  setDirty(true);
                  markDirty();
                }}
              >
                恢复草稿
              </Button>
              <Button
                type='button'
                variant='outline'
                onClick={() => {
                  const blob = new Blob([JSON.stringify(recoverableDraft, null, 2)], {
                    type: 'application/json'
                  });
                  const url = URL.createObjectURL(blob);
                  const anchor = document.createElement('a');
                  anchor.href = url;
                  anchor.download = `sample-draft-${recoverableDraft.record_id ?? 'new'}.json`;
                  anchor.click();
                  URL.revokeObjectURL(url);
                }}
              >
                导出草稿
              </Button>
              <Button
                type='button'
                variant='ghost'
                onClick={() => {
                  deleteScientificDraft(draftKey).catch(() => undefined);
                  setRecoverableDraft(null);
                }}
              >
                丢弃
              </Button>
            </span>
          </section>
        )}
        <header className='flex flex-wrap items-start justify-between gap-4'>
          <div className='min-w-0 flex-1'>
            <input
              data-testid='sample-title'
              className='h-12 w-full rounded-md border-transparent bg-transparent px-0 text-3xl font-semibold tracking-tight outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-border focus:bg-background focus:px-2'
              required
              disabled={readOnly}
              value={title}
              placeholder={readOnly ? 'Sample 历史版本' : '未命名 Sample'}
              onChange={(event) => {
                setTitle(event.target.value);
                markDirty();
              }}
            />
            <p className='mt-1 text-sm text-muted-foreground'>
              {readOnly
                ? 'Sample 历史版本'
                : '一级 bullet 记录自然语言；输入 @ 添加对象或过程，Tab 创建二级属性 bullet。'}
            </p>
          </div>
          {!readOnly && (
            <div className='flex items-center gap-2'>
              <Button
                type='submit'
                data-testid='save-sample-record'
                disabled={saving || !title.trim() || !projectId}
                onClick={() => {
                  saveIntent.current = 'save';
                }}
              >
                {saving ? '保存中…' : '保存实际记录'}
              </Button>
              <details className='relative'>
                <summary className='cursor-pointer list-none rounded-md border px-3 py-2 text-sm hover:bg-accent'>
                  更多
                </summary>
                <div className='absolute right-0 top-11 z-20 grid min-w-48 gap-1 rounded-lg border bg-popover p-1 shadow-lg'>
                  <button
                    type='submit'
                    className='rounded px-3 py-2 text-left text-sm hover:bg-accent'
                    data-testid='save-and-new-sample-record'
                    disabled={saving || !title.trim() || !projectId}
                    onClick={() => {
                      saveIntent.current = 'save-and-new';
                    }}
                  >
                    保存并再建一份
                  </button>
                  <button
                    type='submit'
                    className='rounded px-3 py-2 text-left text-sm hover:bg-accent'
                    data-testid='save-and-batch-sample-record'
                    disabled={saving || !title.trim() || !projectId}
                    onClick={() => {
                      saveIntent.current = 'save-and-batch';
                    }}
                  >
                    保存并批量创建类似样品
                  </button>
                </div>
              </details>
            </div>
          )}
        </header>

        <section className='flex flex-wrap items-center gap-x-4 gap-y-2 border-y py-2 text-sm'>
          <label className='flex items-center gap-2 text-sm'>
            <span>记录状态</span>
            <select
              className='h-9 w-full rounded border bg-background px-2'
              value={status}
              disabled={readOnly}
              onChange={(event) => {
                setStatus(event.target.value);
                markDirty();
              }}
            >
              <option value='draft'>草稿</option>
              <option value='active'>有效</option>
              <option value='archived'>归档</option>
            </select>
          </label>
          <label className='flex items-center gap-2 text-sm'>
            <span>标签</span>
            <input
              className='h-9 w-full rounded border bg-background px-3'
              value={tags}
              disabled={readOnly}
              onChange={(event) => {
                setTags(event.target.value);
                markDirty();
              }}
            />
          </label>
          <label className='flex items-center gap-2 text-sm'>
            <span>产出当前 Sample</span>
            <select
              className='h-9 w-full rounded border bg-background px-2'
              value={producerProcessOccurrenceId ?? ''}
              disabled={readOnly}
              onChange={(event) => {
                setProducerProcessOccurrenceId(event.target.value || null);
                markDirty();
              }}
            >
              <option value=''>不指定</option>
              {processOccurrences.map((occurrence, index) => (
                <option key={occurrence.occurrence_id} value={occurrence.occurrence_id}>
                  {occurrence.label_snapshot ?? `Process ${index + 1}`}
                </option>
              ))}
            </select>
          </label>
        </section>

        <ScientificComposer
          key={composerGeneration}
          initialBlocks={blocks}
          searchProcesses={(query, options) =>
            api.listProcessDefinitions({
              project_scope_id: projectId,
              q: query || undefined,
              limit: options?.limit ?? 21,
              offset: options?.offset ?? 0,
              signal: options?.signal
            })
          }
          searchObjects={(query, options) =>
            api.listObjects({
              kind: 'research_object',
              project_scope_id: projectId,
              include_global: true,
              q: query || undefined,
              limit: options?.limit ?? 21,
              offset: options?.offset ?? 0,
              signal: options?.signal
            })
          }
          createProcess={(draft, commandId) =>
            api.createProcessDefinition({ ...draft, project_scope_id: projectId }, commandId)
          }
          createObject={(draft, commandId) =>
            api.createObject(
              { ...draft, kind: 'research_object', project_scope_id: projectId },
              commandId
            )
          }
          onChange={(next) => {
            generation.current += 1;
            setBlocks(next);
            setDirty(true);
          }}
          editable={!readOnly}
        />
        {error && (
          <p
            role='alert'
            className='rounded-lg border border-destructive/30 p-3 text-sm text-destructive'
          >
            {error}
          </p>
        )}
      </form>
    </main>
  );
}
