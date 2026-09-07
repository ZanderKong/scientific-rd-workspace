'use client';

import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { ObjectRevision, SampleRecord } from '@/lib/domain';
import { SampleComposer } from './sample-composer';

export function SampleDetail({ sampleId }: { sampleId: string }) {
  const [record, setRecord] = useState<SampleRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revisions, setRevisions] = useState<ObjectRevision[]>([]);
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null);
  useEffect(() => {
    api
      .getSampleRecord(sampleId)
      .then(setRecord)
      .catch((cause) =>
        setError(
          cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed'
        )
      );
  }, [sampleId]);
  useEffect(() => {
    api
      .listRevisions(sampleId)
      .then(setRevisions)
      .catch(() => setRevisions([]));
  }, [sampleId]);
  async function showRevision(revision: number | null) {
    setError(null);
    setSelectedRevision(revision);
    try {
      setRecord(
        revision === null
          ? await api.getSampleRecord(sampleId)
          : await api.getSampleRecordRevision(sampleId, revision)
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed');
    }
  }
  if (error) return <main className='mx-auto max-w-[1320px] p-8 text-destructive'>{error}</main>;
  if (!record)
    return <main className='mx-auto max-w-[1320px] p-8 text-muted-foreground'>Loading…</main>;
  return (
    <>
      <nav className='mx-auto flex w-full max-w-[1320px] flex-wrap gap-2 px-4 pt-5 md:px-8'>
        <button
          type='button'
          className='rounded border px-3 py-1 text-sm'
          aria-pressed={selectedRevision === null}
          onClick={() => showRevision(null)}
        >
          当前版本
        </button>
        {revisions.map((revision) => (
          <button
            key={revision.id}
            type='button'
            className='rounded border px-3 py-1 text-sm'
            aria-pressed={selectedRevision === revision.revision_number}
            onClick={() => showRevision(revision.revision_number)}
          >
            v{revision.revision_number}
          </button>
        ))}
      </nav>
      <SampleComposer
        key={`${record.sample.id}:${record.record_sha256}`}
        projectId={record.sample.project_scope_id ?? ''}
        initialRecord={record}
        editing={selectedRevision === null}
        readOnly={selectedRevision !== null}
      />
    </>
  );
}
