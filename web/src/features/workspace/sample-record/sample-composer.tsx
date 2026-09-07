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
    if (!initialDraft) return [{ type: 'paragraph', content: [] }] as JsonObject[];
    return editing || readOnly
      ? initialDraft.document.blocks
      : cloneDocumentForNewRecord(initialDraft.document.blocks);
  }, [editing, initialDraft, readOnly]);
  const [title, setTitle] = useState(initialRecord?.sample.title ?? '');
  const [status, setStatus] = useState(initialRecord?.sample.status ?? 'draft');
  const [tags, setTags] = useState(initialRecord?.sample.tags.join(',') ?? '样品');
  const [blocks, setBlocks] = useState<JsonObject[]>(initialBlocks);
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
  const saveIntent = useRef<'save' | 'save-and-new'>('save');
  const recordId = initialRecord?.sample.id ?? createdRecordId;
  const isEditing = editing || Boolean(createdRecordId);
  const draftKey = recordId ? `sample:${recordId}` : `sample:new:${projectId}`;

  function markDirty() {
    generation.current += 1;
    setDirty(true);
  }

  useEffect(() => {
    let active = true;
    readScientificDraft(draftKey)
      .then((draft) => {
        if (!active || !draft) return;
        if (draft.base_record_sha256 === baseRecordSha256) setRecoverableDraft(draft);
        else deleteScientificDraft(draftKey).catch(() => undefined);
      })
      .finally(() => {
        if (active) setDraftReady(true);
      });
    return () => {
      active = false;
    };
  }, [baseRecordSha256, draftKey]);

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
        blocks
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
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <form onSubmit={save} className='space-y-5'>
        {recoverableDraft && (
          <section className='flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm'>
            <span>
              发现 {new Date(recoverableDraft.saved_at).toLocaleString()} 保存的本地草稿。
            </span>
            <span className='flex gap-2'>
              <Button
                type='button'
                variant='outline'
                onClick={() => {
                  setTitle(recoverableDraft.title);
                  setStatus(recoverableDraft.status);
                  setTags(recoverableDraft.tags);
                  setBlocks(recoverableDraft.blocks);
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
          <div>
            <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
              Scientific Composer
            </p>
            <h1 className='mt-2 text-2xl font-semibold'>
              {readOnly ? 'Sample 历史版本' : editing ? '编辑 Sample 记录' : '新建 Sample 记录'}
            </h1>
            <p className='mt-1 text-sm text-muted-foreground'>
              输入 / 添加实际过程，输入 @ 添加独立对象使用记录。
            </p>
          </div>
          {!readOnly && (
            <div className='flex flex-wrap gap-2'>
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
              <Button
                type='submit'
                variant='outline'
                data-testid='save-and-new-sample-record'
                disabled={saving || !title.trim() || !projectId}
                onClick={() => {
                  saveIntent.current = 'save-and-new';
                }}
              >
                保存并再建一份
              </Button>
            </div>
          )}
        </header>

        <section className='grid gap-3 rounded-xl border bg-card/70 p-4 md:grid-cols-[1fr_160px_1fr]'>
          <label className='space-y-1 text-sm'>
            <span>名称</span>
            <input
              data-testid='sample-title'
              className='h-9 w-full rounded border bg-background px-3'
              required
              disabled={readOnly}
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                markDirty();
              }}
            />
          </label>
          <label className='space-y-1 text-sm'>
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
          <label className='space-y-1 text-sm'>
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
        </section>

        <ScientificComposer
          key={composerGeneration}
          initialBlocks={blocks}
          searchProcesses={(query) =>
            api.listProcessDefinitions({
              project_scope_id: projectId,
              q: query || undefined,
              limit: 50
            })
          }
          searchObjects={(query) =>
            api.listObjects({
              kind: 'research_object',
              project_scope_id: projectId,
              include_global: true,
              q: query || undefined,
              limit: 50
            })
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
