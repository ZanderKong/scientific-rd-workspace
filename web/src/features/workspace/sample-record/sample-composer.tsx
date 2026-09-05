'use client';

import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { ProcessDefinition, SampleRecord } from '@/lib/domain';
import { draftToCreatePayload, draftToPutPayload, type SampleRecordDraft } from './model';

export function SampleComposer({ projectId, initialRecord, onSaved }: { projectId: string; initialRecord?: SampleRecord | null; onSaved?: (record: SampleRecord) => void }) {
  const [definitions, setDefinitions] = useState<ProcessDefinition[]>([]);
  const [title, setTitle] = useState(initialRecord?.sample.title ?? '');
  const [tags, setTags] = useState(initialRecord?.sample.tags.join(',') ?? '样品');
  const [definitionId, setDefinitionId] = useState(initialRecord?.steps[0]?.execution.process_definition_id ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.listProcessDefinitions({ project_scope_id: projectId }).then(setDefinitions).catch(() => setDefinitions([])); }, [projectId]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || !definitionId) return;
    setSaving(true); setError(null);
    const definition = definitions.find((item) => item.process_definition.id === definitionId);
    const draft: SampleRecordDraft = { sample: { title: title.trim(), code: initialRecord?.sample.code, status: 'draft', tags }, steps: [{ process_definition_id: definitionId, process_definition_version_id: definition?.current_version.id, project_scope_id: projectId, title_snapshot: definition?.process_definition.title, status: 'draft', values: {}, object_bindings: [], data_bindings: [] }] };
    try {
      const saved = initialRecord ? await api.updateSampleRecord(initialRecord.sample.id, draftToPutPayload(draft)) : await api.createSampleRecord(draftToCreatePayload(projectId, draft));
      onSaved?.(saved);
    } catch (cause) { setError(cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed'); } finally { setSaving(false); }
  }
  return <form onSubmit={submit} className='space-y-5'><section className='rounded-2xl border bg-card/80 p-5'><h1 className='text-xl font-semibold'>{initialRecord ? 'Edit sample record' : 'New sample record'}</h1><p className='mt-1 text-sm text-muted-foreground'>Each step is saved as a Process Execution pinned to a Definition version.</p><div className='mt-5 grid gap-4 md:grid-cols-2'><label className='grid gap-1 text-sm'>Title<input required className='h-9 rounded-md border bg-background px-3' value={title} onChange={(event) => setTitle(event.target.value)} /></label><label className='grid gap-1 text-sm'>Tags<input className='h-9 rounded-md border bg-background px-3' value={tags} onChange={(event) => setTags(event.target.value)} /></label><label className='grid gap-1 text-sm md:col-span-2'>Process Definition<select required className='h-9 rounded-md border bg-background px-3' value={definitionId} onChange={(event) => setDefinitionId(event.target.value)}><option value=''>Select a definition</option>{definitions.map((item) => <option key={item.process_definition.id} value={item.process_definition.id}>{item.process_definition.title} · v{item.current_version.version}</option>)}</select></label></div></section>{error && <p className='rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>{error}</p>}<button disabled={saving || !title.trim() || !definitionId} className='rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50'>{saving ? 'Saving…' : 'Save aggregate record'}</button></form>;
}
