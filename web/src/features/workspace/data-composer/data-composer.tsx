'use client';

import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api-client';
import type { DataDraft, JsonObject } from '@/lib/domain';
import { useProjectScope } from '../project-scope/project-scope-context';
import { canonicalizeDocument, enrichScientificDocument } from '../scientific-document/model';

const ScientificComposer = dynamic(
  () =>
    import('../scientific-composer/scientific-composer').then(
      (module) => module.ScientificComposer
    ),
  {
    ssr: false,
    loading: () => <p className='p-6 text-sm text-muted-foreground'>Loading editor…</p>
  }
);

const emptyBlocks: JsonObject[] = [{ type: 'paragraph', content: [] }];

function message(cause: unknown) {
  return cause instanceof Error ? cause.message : 'Request failed';
}

export function DataComposer() {
  const router = useRouter();
  const params = useSearchParams();
  const { activeProjectId } = useProjectScope();
  const draftId = params.get('draft');
  const sourceSampleId = params.get('sample');
  const [sourceId, setSourceId] = useState<string | null>(sourceSampleId);
  const [draft, setDraft] = useState<DataDraft | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scientificType, setScientificType] = useState('table');
  const [tags, setTags] = useState('measurement');
  const [blocks, setBlocks] = useState<JsonObject[]>(emptyBlocks);
  const [originId, setOriginId] = useState<string | null>(null);
  const [editorGeneration, setEditorGeneration] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const beginKey = useRef(crypto.randomUUID());
  const finalizeKey = useRef(crypto.randomUUID());
  const generation = useRef(0);
  const dirtyRef = useRef(false);

  const markDirty = useCallback(() => {
    generation.current += 1;
    dirtyRef.current = true;
  }, []);

  const loadDraft = useCallback((loaded: DataDraft) => {
    const preserveLocalEdits = dirtyRef.current;
    setDraft(loaded);
    setOriginId(loaded.content.origin_client_attachment_id);
    setSourceId(loaded.content.source_sample_id);
    if (!preserveLocalEdits) {
      setTitle(loaded.content.title);
      setDescription(loaded.content.description ?? '');
      setScientificType(loaded.content.scientific_type ?? 'table');
      setTags(loaded.content.tags.join(','));
      setBlocks(enrichScientificDocument(loaded.content.document, loaded.content.occurrences));
      setEditorGeneration((value) => value + 1);
      generation.current = 0;
      dirtyRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!draftId) return;
    api
      .getDataDraft(draftId)
      .then(loadDraft)
      .catch((cause) => setError(message(cause)));
  }, [draftId, loadDraft]);

  function content() {
    const canonical = canonicalizeDocument(blocks);
    return {
      title: title.trim(),
      tags: tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
      scientific_type: scientificType || null,
      description: description.trim() || null,
      ...canonical,
      subject_ids: [],
      source_sample_id: sourceId,
      origin_client_attachment_id: originId
    };
  }

  async function begin() {
    if (!activeProjectId || !title.trim()) return null;
    const begun = await api.beginDataDraft(
      { project_scope_id: activeProjectId, content: content() },
      beginKey.current
    );
    loadDraft(begun);
    router.replace(`/dashboard/data/new?draft=${begun.id}`);
    return begun;
  }

  async function saveDraft() {
    if (!draft) return begin();
    if (draft.status === 'finalized') return draft;
    const submittedGeneration = generation.current;
    const payload = content();
    const saved = await api.updateDataDraft(draft.id, {
      base_record_sha256: draft.record_sha256,
      content: payload
    });
    setDraft(saved);
    if (submittedGeneration === generation.current) dirtyRef.current = false;
    return saved;
  }

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!draft) {
        setError('请先开始草稿，再上传附件。');
        return;
      }
      setBusy(true);
      setUploadErrors([]);
      let current = draft;
      const failures: string[] = [];
      for (const file of files) {
        try {
          const clientId = crypto.randomUUID();
          const asset = await api.uploadAsset(current.data_id, file);
          current = await api.attachDataDraftAsset(current.id, clientId, asset.id);
        } catch (cause) {
          failures.push(`${file.name}: ${message(cause)}`);
        }
      }
      setDraft(current);
      setUploadErrors(failures);
      setBusy(false);
    },
    [draft]
  );
  const dropzone = useDropzone({ onDrop, disabled: busy || !draft, multiple: true });

  async function handleSave() {
    setBusy(true);
    setError(null);
    try {
      await saveDraft();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalize() {
    setBusy(true);
    setError(null);
    try {
      // Re-read before writing because a previous finalize request may have
      // committed successfully while its response was lost. A finalized draft
      // carries the durable result and must be replayed instead of PUTing an
      // already-closed draft.
      const fresh = draft ? await api.getDataDraft(draft.id) : null;
      if (fresh?.status === 'finalized' && fresh.finalized_result) {
        setDraft(fresh);
        router.push(`/dashboard/data/${fresh.finalized_result.data.id}`);
        return;
      }
      const submittedGeneration = generation.current;
      const saved = fresh
        ? await api.updateDataDraft(fresh.id, {
            base_record_sha256: fresh.record_sha256,
            content: content()
          })
        : await begin();
      if (fresh) {
        setDraft(saved);
        if (submittedGeneration === generation.current) dirtyRef.current = false;
      }
      if (!saved) return;
      if (saved.status === 'finalized' && saved.finalized_result) {
        router.push(`/dashboard/data/${saved.finalized_result.data.id}`);
        return;
      }
      const result = await api.finalizeDataDraft(
        saved.id,
        saved.record_sha256,
        finalizeKey.current
      );
      router.push(`/dashboard/data/${result.data.id}`);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  if (!activeProjectId && !draftId) {
    return <p className='p-10 text-sm text-muted-foreground'>请先选择项目。</p>;
  }
  return (
    <main className='mx-auto w-full max-w-[1320px] space-y-5 px-4 py-7 md:px-8 md:py-10'>
      <header className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Recoverable Data Composer
          </p>
          <h1 className='mt-2 text-3xl font-semibold'>记录 Data</h1>
          <p className='mt-2 text-sm text-muted-foreground'>获取过程与观察内容分开保存。</p>
        </div>
        <div className='flex gap-2'>
          <Button variant='outline' disabled={busy || !title.trim()} onClick={handleSave}>
            {draft ? '保存草稿' : '开始草稿'}
          </Button>
          <Button disabled={busy || !draft || !title.trim()} onClick={handleFinalize}>
            Finalize
          </Button>
        </div>
      </header>
      <section className='grid gap-3 rounded-xl border bg-card/70 p-4 md:grid-cols-3'>
        <label className='space-y-1 text-sm md:col-span-2'>
          <span>名称</span>
          <input
            className='h-9 w-full rounded border bg-background px-3'
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
              markDirty();
            }}
          />
        </label>
        <label className='space-y-1 text-sm'>
          <span>科学类型</span>
          <input
            className='h-9 w-full rounded border bg-background px-3'
            value={scientificType}
            onChange={(event) => {
              setScientificType(event.target.value);
              markDirty();
            }}
          />
        </label>
        <label className='space-y-1 text-sm md:col-span-3'>
          <span>标签</span>
          <input
            className='h-9 w-full rounded border bg-background px-3'
            value={tags}
            onChange={(event) => {
              setTags(event.target.value);
              markDirty();
            }}
          />
        </label>
      </section>
      <section>
        <h2 className='mb-2 font-medium'>获取正文</h2>
        <ScientificComposer
          key={editorGeneration}
          initialBlocks={blocks}
          searchProcesses={(query, options) =>
            api.listProcessDefinitions({
              project_scope_id: activeProjectId ?? draft?.project_scope_id,
              q: query || undefined,
              limit: options?.limit ?? 21,
              offset: options?.offset ?? 0,
              signal: options?.signal
            })
          }
          searchObjects={(query, options) =>
            api.listObjects({
              kind: 'research_object',
              project_scope_id: activeProjectId ?? draft?.project_scope_id,
              include_global: true,
              q: query || undefined,
              limit: options?.limit ?? 21,
              offset: options?.offset ?? 0,
              signal: options?.signal
            })
          }
          createProcess={(value, commandId) =>
            api.createProcessDefinition(
              {
                ...value,
                project_scope_id: activeProjectId ?? draft?.project_scope_id
              },
              commandId
            )
          }
          createObject={(value, commandId) =>
            api.createObject(
              {
                ...value,
                kind: 'research_object',
                project_scope_id: activeProjectId ?? draft?.project_scope_id
              },
              commandId
            )
          }
          onChange={(next) => {
            setBlocks(next);
            markDirty();
          }}
        />
      </section>
      <label className='block space-y-2'>
        <span className='font-medium'>观察内容</span>
        <textarea
          className='min-h-28 w-full rounded-xl border bg-background p-3 text-sm'
          value={description}
          onChange={(event) => {
            setDescription(event.target.value);
            markDirty();
          }}
          placeholder='观察将保存为 description Representation'
        />
      </label>
      <section className='space-y-3 rounded-xl border p-4'>
        <h2 className='font-medium'>Representations</h2>
        <div
          {...dropzone.getRootProps()}
          className='cursor-pointer rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground'
        >
          <input {...dropzone.getInputProps()} />
          {draft ? '拖入 CSV、XLSX、图片或其他原始文件' : '开始草稿后可上传文件'}
        </div>
        {draft?.attachments.map((attachment) => (
          <div key={attachment.client_attachment_id} className='flex items-center gap-3 text-sm'>
            <input
              type='radio'
              name='origin'
              aria-label={`${attachment.name} 设为主 origin`}
              checked={originId === attachment.client_attachment_id}
              onChange={() => {
                setOriginId(attachment.client_attachment_id);
                markDirty();
              }}
            />
            <span className='min-w-0 flex-1 truncate'>{attachment.name}</span>
            <span className='font-mono text-xs text-muted-foreground'>
              {attachment.sha256.slice(0, 12)}
            </span>
            <Button
              size='sm'
              variant='ghost'
              onClick={async () => {
                const next = await api.removeDataDraftAsset(
                  draft.id,
                  attachment.client_attachment_id
                );
                setDraft(next);
                if (originId === attachment.client_attachment_id) setOriginId(null);
                await api.deleteAsset(attachment.asset_id);
              }}
            >
              移除
            </Button>
          </div>
        ))}
        {uploadErrors.map((item) => (
          <p key={item} className='text-sm text-destructive'>
            {item}
          </p>
        ))}
      </section>
      {sourceSampleId && (
        <p className='text-xs text-muted-foreground'>Subject source Sample: {sourceSampleId}</p>
      )}
      {error && (
        <p
          role='alert'
          className='rounded-lg border border-destructive/30 p-3 text-sm text-destructive'
        >
          {error}
        </p>
      )}
    </main>
  );
}
