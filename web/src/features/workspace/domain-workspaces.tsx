'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { api, ApiError } from '@/lib/api-client';
import type {
  ChangeSet,
  ClaimRecord,
  DataRecord,
  ExperimentRecord,
  ProjectRecord,
  ResearchObject,
  ViewRecord
} from '@/lib/domain';
import { Button } from '@/components/ui/button';
import { useProjectScope } from './project-scope/project-scope-context';
import { objectPath } from './components/workspace-app';

const card = 'rounded-2xl border bg-card/80 p-5 shadow-xs';
function message(error: unknown) {
  return error instanceof ApiError || error instanceof Error ? error.message : 'Request failed';
}
function State({ loading, error }: { loading: boolean; error: string | null }) {
  if (loading) return <p className='py-10 text-center text-sm text-muted-foreground'>Loading…</p>;
  return error ? (
    <p className='rounded-xl border border-destructive/30 p-4 text-sm text-destructive'>{error}</p>
  ) : null;
}
function ObjectLink({ object }: { object: ResearchObject }) {
  return (
    <Link
      href={objectPath(object)}
      className='flex items-center justify-between gap-3 rounded-xl border px-3 py-3 hover:border-primary'
    >
      <span>
        <span className='font-mono text-[10px] text-muted-foreground'>{object.code}</span>
        <span className='ml-2 text-sm font-medium'>{object.title}</span>
      </span>
      <span className='text-xs text-muted-foreground'>{object.kind}</span>
    </Link>
  );
}

function ClaimCreator({
  source,
  sourceKind,
  viewRevisionId
}: {
  source: ResearchObject;
  sourceKind: 'experiment' | 'data' | 'view';
  viewRevisionId?: string | null;
}) {
  const [statement, setStatement] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!source.project_scope_id || !statement.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const revisionId =
        sourceKind === 'view' ? viewRevisionId : (await api.listRevisions(source.id)).at(-1)?.id;
      if (!revisionId) throw new Error('The source has no revision to pin.');
      const result = await api.createClaim({
        project_scope_id: source.project_scope_id,
        statement: statement.trim(),
        author_provenance: { kind: 'human' },
        primary_source: {
          kind: sourceKind,
          object_id: source.id,
          revision_id: revisionId
        },
        evidence: []
      });
      window.location.assign(objectPath(result.claim));
    } catch (cause) {
      setError(message(cause));
      setSaving(false);
    }
  }
  return (
    <form onSubmit={submit} className={`${card} mt-6`}>
      <h2 className='font-semibold'>Create Claim from this revision</h2>
      <div className='mt-3 flex gap-2'>
        <input
          className='h-9 flex-1 rounded-md border bg-background px-3 text-sm'
          value={statement}
          onChange={(event) => setStatement(event.target.value)}
          placeholder='Claim statement'
        />
        <Button type='submit' disabled={saving || !statement.trim()}>
          {saving ? 'Saving…' : 'Create Claim'}
        </Button>
      </div>
      {error && <p className='mt-2 text-sm text-destructive'>{error}</p>}
    </form>
  );
}

function ViewCreator({ record }: { record: DataRecord }) {
  const [title, setTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!record.data.project_scope_id || !title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const revisionId = (await api.listRevisions(record.data.id)).at(-1)?.id;
      if (!revisionId) throw new Error('The Data record has no revision to pin.');
      const result = await api.createView({
        project_scope_id: record.data.project_scope_id,
        title: title.trim(),
        data_refs: [
          {
            data_id: record.data.id,
            data_revision_id: revisionId,
            representation_ids: record.representations.map((item) => item.id)
          }
        ],
        config: {}
      });
      window.location.assign(objectPath(result.view));
    } catch (cause) {
      setError(message(cause));
      setSaving(false);
    }
  }
  return (
    <form onSubmit={submit} className={`${card} mt-6`}>
      <h2 className='font-semibold'>Create pinned View</h2>
      <div className='mt-3 flex gap-2'>
        <input
          className='h-9 flex-1 rounded-md border bg-background px-3 text-sm'
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder='View title'
        />
        <Button type='submit' disabled={saving || !title.trim()}>
          {saving ? 'Saving…' : 'Create View'}
        </Button>
      </div>
      {error && <p className='mt-2 text-sm text-destructive'>{error}</p>}
    </form>
  );
}

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [record, setRecord] = useState<ProjectRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .getProjectRecord(projectId)
      .then(setRecord)
      .catch((cause) => setError(message(cause)));
  }, [projectId]);
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <State loading={!record && !error} error={error} />
      {record && (
        <>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Project record
          </p>
          <h1 className='mt-2 text-3xl font-semibold'>{record.project.title}</h1>
          <p className='mt-2 font-mono text-xs text-muted-foreground'>{record.project.code}</p>
          <div className='mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
            {Object.entries(record.context.counts).map(([key, value]) => (
              <div key={key} className={card}>
                <p className='text-xs text-muted-foreground'>{key}</p>
                <p className='mt-2 text-3xl font-semibold'>{value}</p>
              </div>
            ))}
          </div>
          <section className='mt-6 space-y-2'>
            <h2 className='font-semibold'>Recent research objects</h2>
            {record.context.recent_research_objects.map((object) => (
              <ObjectLink key={object.id} object={object} />
            ))}
          </section>
        </>
      )}
    </main>
  );
}

export function ExperimentWorkspace({
  experimentId,
  projectId,
  create = false
}: {
  experimentId?: string;
  projectId?: string;
  create?: boolean;
}) {
  const { activeProjectId } = useProjectScope();
  const searchParams = useSearchParams();
  const scope = projectId ?? activeProjectId;
  const [items, setItems] = useState<ResearchObject[]>([]);
  const [record, setRecord] = useState<ExperimentRecord | null>(null);
  const [title, setTitle] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(create);
  const [sampleCandidates, setSampleCandidates] = useState<ResearchObject[]>([]);
  const [sampleQuery, setSampleQuery] = useState('');
  const [samplePage, setSamplePage] = useState(1);
  const [sampleTotal, setSampleTotal] = useState(0);
  const [selectedSamples, setSelectedSamples] = useState<string[]>(() => {
    const selected = searchParams.get('selectedSample');
    return selected ? [selected] : [];
  });
  useEffect(() => {
    if (experimentId)
      api
        .getExperimentRecord(experimentId)
        .then(setRecord)
        .catch((cause) => setError(message(cause)));
    else if (scope)
      api
        .listObjects({ kind: 'experiment', project_scope_id: scope })
        .then(setItems)
        .catch((cause) => setError(message(cause)));
  }, [experimentId, scope]);
  useEffect(() => {
    if (!creating || !scope) return;
    api
      .queryRecordTable({
        project_scope_id: scope,
        record_kind: 'sample',
        q: sampleQuery || null,
        required_refs: [],
        display_columns: [],
        limit: 50,
        offset: (samplePage - 1) * 50
      })
      .then((result) => {
        setSampleCandidates(result.rows.map((row) => row.record));
        setSampleTotal(result.total);
      })
      .catch((cause) => setError(message(cause)));
  }, [creating, samplePage, sampleQuery, scope]);
  async function createExperiment(event: React.FormEvent) {
    event.preventDefault();
    if (!scope || !title.trim()) return;
    try {
      const next = await api.createExperimentRecord({
        project_scope_id: scope,
        experiment: { title: title.trim(), status: 'draft' },
        references: selectedSamples.map((targetId, orderIndex) => ({
          target_id: targetId,
          target_kind: 'research_object',
          role: 'sample',
          order_index: orderIndex
        }))
      });
      window.location.assign(objectPath(next.experiment));
    } catch (cause) {
      setError(message(cause));
    }
  }
  if (record)
    return (
      <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
        <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
          Experiment record
        </p>
        <h1 className='mt-2 text-3xl font-semibold'>{record.experiment.title}</h1>
        <p className='mt-2 text-sm text-muted-foreground'>
          This experiment is a reference context; it does not own process, sample, or data
          provenance.
        </p>
        <section className='mt-6 space-y-2'>
          <h2 className='font-semibold'>References</h2>
          {Object.values(record.references)
            .flat()
            .map((reference) => (
              <ObjectLink key={reference.relation_id} object={reference.object} />
            ))}
        </section>
        <ClaimCreator source={record.experiment} sourceKind='experiment' />
      </main>
    );
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <div className='mb-6 flex items-start justify-between gap-3'>
        <div>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Experiment references
          </p>
          <h1 className='mt-2 text-3xl font-semibold'>Experiments</h1>
        </div>
        <Button onClick={() => setCreating((value) => !value)}>Create</Button>
      </div>
      {creating && (
        <form onSubmit={createExperiment} className={`${card} mb-5 space-y-4`}>
          <div className='flex gap-2'>
            <input
              className='h-9 flex-1 rounded-md border bg-background px-3 text-sm'
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder='Experiment title'
            />
            <Button type='submit' disabled={!title.trim()}>
              Save with {selectedSamples.length} Sample{selectedSamples.length === 1 ? '' : 's'}
            </Button>
          </div>
          <div>
            <div className='flex items-center justify-between'>
              <h2 className='text-sm font-semibold'>Sample Picker</h2>
              {scope && (
                <Link
                  className='text-sm text-primary underline-offset-4 hover:underline'
                  href={`/dashboard/samples/new?project=${encodeURIComponent(scope)}&returnTo=${encodeURIComponent(`/dashboard/projects/${scope}/experiments/new`)}`}
                >
                  Create Sample and return
                </Link>
              )}
            </div>
            <input
              className='mt-3 h-9 w-full rounded-md border bg-background px-3 text-sm'
              value={sampleQuery}
              onChange={(event) => {
                setSampleQuery(event.target.value);
                setSamplePage(1);
              }}
              placeholder='Search Samples by title or code…'
            />
            <div className='mt-2 grid gap-2 md:grid-cols-2'>
              {sampleCandidates.map((sample) => (
                <label
                  key={sample.id}
                  className='flex items-center gap-2 rounded-lg border p-3 text-sm'
                >
                  <input
                    type='checkbox'
                    checked={selectedSamples.includes(sample.id)}
                    onChange={() =>
                      setSelectedSamples((current) =>
                        current.includes(sample.id)
                          ? current.filter((id) => id !== sample.id)
                          : [...current, sample.id]
                      )
                    }
                  />
                  <span>{sample.title}</span>
                </label>
              ))}
            </div>
            {!sampleCandidates.length && (
              <p className='mt-2 text-sm text-muted-foreground'>No Samples in this project yet.</p>
            )}
            {sampleTotal > 50 && (
              <div className='mt-3 flex items-center justify-between text-sm'>
                <span className='text-muted-foreground'>
                  第 {samplePage}/{Math.max(1, Math.ceil(sampleTotal / 50))} 页 · 共 {sampleTotal}{' '}
                  条
                </span>
                <span className='flex gap-2'>
                  <Button
                    type='button'
                    variant='outline'
                    size='sm'
                    disabled={samplePage <= 1}
                    onClick={() => setSamplePage((page) => page - 1)}
                  >
                    上一页
                  </Button>
                  <Button
                    type='button'
                    variant='outline'
                    size='sm'
                    disabled={samplePage >= Math.ceil(sampleTotal / 50)}
                    onClick={() => setSamplePage((page) => page + 1)}
                  >
                    下一页
                  </Button>
                </span>
              </div>
            )}
          </div>
        </form>
      )}
      <State loading={!items.length && !error && !creating} error={error} />
      <div className='grid gap-3 md:grid-cols-2'>
        {items.map((object) => (
          <ObjectLink key={object.id} object={object} />
        ))}
      </div>
    </main>
  );
}

export function DataWorkspace({ dataId }: { dataId: string }) {
  const [record, setRecord] = useState<DataRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .getDataRecord(dataId)
      .then(setRecord)
      .catch((cause) => setError(message(cause)));
  }, [dataId]);
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <State loading={!record && !error} error={error} />
      {record && (
        <>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Data record
          </p>
          <h1 className='mt-2 text-3xl font-semibold'>{record.data.title}</h1>
          <p className='mt-2 text-sm text-muted-foreground'>
            {record.description ?? 'Multiple representations share one Data identity.'}
          </p>
          <p className='mt-2 font-mono text-xs text-muted-foreground'>
            Origin representation: {record.origin_representation_id ?? 'not set'}
          </p>
          <div className='mt-6 grid gap-3 md:grid-cols-2'>
            {record.representations.map((representation) => (
              <article key={representation.id} className={card}>
                <div className='flex items-center justify-between'>
                  <h2 className='font-semibold'>{representation.name}</h2>
                  <span className='rounded-full bg-muted px-2 py-1 text-xs'>
                    {representation.kind}
                  </span>
                </div>
                <p className='mt-2 font-mono text-[10px] text-muted-foreground'>
                  {representation.representation_sha256.slice(0, 16)}…
                </p>
              </article>
            ))}
          </div>
          {!!record.occurrences.length && (
            <section className={`${card} mt-6`}>
              <h2 className='font-semibold'>获取正文 · {record.occurrences.length} Ref</h2>
              <div className='mt-3 space-y-2'>
                {record.occurrences.map((occurrence) => (
                  <div key={occurrence.occurrence_id} className='rounded-lg border p-3 text-sm'>
                    <div className='flex items-center justify-between gap-2'>
                      <span className='font-medium'>
                        {occurrence.kind === 'process' ? '/' : '@'}
                        {occurrence.label_snapshot ?? occurrence.target_id}
                      </span>
                      <span className='text-xs text-muted-foreground'>{occurrence.status}</span>
                    </div>
                    <pre className='mt-2 overflow-auto text-xs'>
                      {JSON.stringify(occurrence.values, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </section>
          )}
          <section className='mt-6 grid gap-3 md:grid-cols-2'>
            <div className={card}>
              <h2 className='font-semibold'>Subjects</h2>
              {record.subjects.map((object) => (
                <ObjectLink key={object.id} object={object} />
              ))}
            </div>
            <div className={card}>
              <h2 className='font-semibold'>Derived from</h2>
              {record.derived_from.map((object) => (
                <ObjectLink key={object.id} object={object} />
              ))}
            </div>
          </section>
          <ClaimCreator source={record.data} sourceKind='data' />
          <ViewCreator record={record} />
        </>
      )}
    </main>
  );
}

export function ViewWorkspace({ viewId }: { viewId: string }) {
  const [record, setRecord] = useState<ViewRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  useEffect(() => {
    api
      .getView(viewId)
      .then(setRecord)
      .catch((cause) => setError(message(cause)));
  }, [viewId]);
  const dropzone = useDropzone({
    multiple: false,
    accept: {
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'application/pdf': ['.pdf'],
      'image/svg+xml': ['.svg']
    },
    disabled: !record || uploading,
    onDrop: async (files) => {
      const file = files[0];
      if (!file || !record) return;
      setUploading(true);
      setError(null);
      try {
        const asset = await api.uploadAsset(record.view.id, file);
        const updated = await api.updateView(
          record.view.id,
          { artifact_asset_id: asset.id, change_note: 'replace Artifact' },
          record.record_sha256
        );
        setRecord(updated);
      } catch (cause) {
        setError(message(cause));
      } finally {
        setUploading(false);
      }
    }
  });
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <State loading={!record && !error} error={error} />
      {record && (
        <>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            View record
          </p>
          <h1 className='mt-2 text-3xl font-semibold'>{record.view.title}</h1>
          <p className='mt-2 text-sm text-muted-foreground'>
            {record.description ?? 'A versioned, data-only scientific view.'}
          </p>
          <section className='mt-6 grid gap-3 md:grid-cols-2'>
            <div className={card}>
              <h2 className='font-semibold'>Data references</h2>
              <div className='mt-3 space-y-2'>
                {record.data.map((item) => (
                  <ObjectLink key={item.id} object={item} />
                ))}
              </div>
            </div>
            <div className={card}>
              <h2 className='font-semibold'>Current revision</h2>
              <p className='mt-2 font-mono text-xs'>
                {record.current_revision_id ?? 'No revision'}
              </p>
              <h3 className='mt-5 font-semibold'>Configuration</h3>
              <pre className='mt-2 overflow-auto rounded-lg bg-muted/40 p-3 text-xs'>
                {JSON.stringify(record.config, null, 2)}
              </pre>
            </div>
          </section>
          <section className={`${card} mt-6`}>
            <h2 className='font-semibold'>Revision history</h2>
            <div className='mt-3 space-y-2'>
              {record.revisions.map((revision) => (
                <div key={revision.id} className='rounded-lg border px-3 py-2 text-sm'>
                  Revision {revision.revision_number} · {revision.snapshot_sha256.slice(0, 12)}…
                </div>
              ))}
            </div>
          </section>
          <section className={`${card} mt-6`}>
            <h2 className='font-semibold'>Artifact</h2>
            <div
              {...dropzone.getRootProps()}
              className='mt-3 cursor-pointer rounded-xl border border-dashed p-5 text-sm text-muted-foreground'
            >
              <input {...dropzone.getInputProps()} />
              {uploading
                ? 'Uploading…'
                : 'Drop or choose a PNG, JPEG, PDF, or SVG. The asset hash is pinned in a new View revision.'}
            </div>
            {record.artifact_sha256 && (
              <p className='mt-2 font-mono text-xs'>{record.artifact_sha256}</p>
            )}
          </section>
          <ClaimCreator
            source={record.view}
            sourceKind='view'
            viewRevisionId={record.current_revision_id}
          />
        </>
      )}
    </main>
  );
}

export function ClaimWorkspace({ claimId }: { claimId: string }) {
  const [record, setRecord] = useState<ClaimRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<ResearchObject[]>([]);
  const [evidenceKind, setEvidenceKind] = useState<'data' | 'view' | 'claim' | 'external'>('data');
  const [evidenceId, setEvidenceId] = useState('');
  const [externalRef, setExternalRef] = useState('');
  const [polarity, setPolarity] = useState<'support' | 'counter'>('support');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api
      .getClaim(claimId)
      .then((next) => {
        setRecord(next);
        return next;
      })
      .catch((cause) => setError(message(cause)));
  }, [claimId]);
  useEffect(() => {
    if (!record?.claim.project_scope_id) return;
    api
      .listObjects({
        project_scope_id: record.claim.project_scope_id,
        kinds: ['data', 'view', 'claim'],
        limit: 200
      })
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, [record?.claim.project_scope_id]);
  async function updateEvidence(nextEvidence: ClaimRecord['evidence']) {
    if (!record) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateClaim(
        record.claim.id,
        {
          evidence: nextEvidence.map((item, index) => ({
            evidence_kind: item.evidence_kind,
            evidence_id: item.evidence_id,
            external_ref: item.external_ref,
            polarity: item.polarity,
            note: item.note,
            order_index: index
          })),
          change_note: 'update claim evidence'
        },
        record.record_sha256
      );
      setRecord(updated);
      setEvidenceId('');
      setExternalRef('');
      setNote('');
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }
  async function addEvidence(event: React.FormEvent) {
    event.preventDefault();
    if (
      !record ||
      (evidenceKind !== 'external' && !evidenceId) ||
      (evidenceKind === 'external' && !externalRef.trim())
    )
      return;
    const object =
      evidenceKind === 'external'
        ? null
        : (candidates.find((item) => item.id === evidenceId) ?? null);
    await updateEvidence([
      ...record.evidence,
      {
        id: crypto.randomUUID(),
        evidence_kind: evidenceKind,
        evidence_id: object?.id ?? null,
        external_ref: evidenceKind === 'external' ? externalRef.trim() : null,
        polarity,
        note: note.trim() || null,
        order_index: record.evidence.length,
        object
      }
    ]);
  }
  async function archiveClaim() {
    if (!record) return;
    setSaving(true);
    setError(null);
    try {
      setRecord(
        await api.updateClaim(
          record.claim.id,
          { status: 'archived', change_note: 'archive claim' },
          record.record_sha256
        )
      );
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <State loading={!record && !error} error={error} />
      {record && (
        <>
          <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
            Claim record
          </p>
          <h1 className='mt-2 text-3xl font-semibold'>{record.claim.title}</h1>
          <p className={`${card} mt-5 text-base`}>{record.statement}</p>
          <div className='mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground'>
            <span className='rounded-full border px-2 py-1'>
              Source: {record.primary_source.kind} · {record.primary_source_object.title}
            </span>
            <span className='rounded-full border px-2 py-1'>
              Confidence: {record.confidence ?? 'not set'}
            </span>
            <span className='rounded-full border px-2 py-1'>Status: {record.claim.status}</span>
            {record.claim.status !== 'archived' && (
              <Button
                type='button'
                size='sm'
                variant='outline'
                onClick={archiveClaim}
                disabled={saving}
              >
                Archive Claim
              </Button>
            )}
          </div>
          <section className={`${card} mt-6`}>
            <h2 className='font-semibold'>Evidence</h2>
            <div className='mt-3 space-y-2'>
              {record.evidence.map((evidence) => (
                <div key={evidence.id} className='rounded-lg border px-3 py-2 text-sm'>
                  <span className='font-medium'>{evidence.polarity}</span> ·{' '}
                  {evidence.evidence_kind}
                  {evidence.object
                    ? ` · ${evidence.object.title}`
                    : evidence.external_ref
                      ? ` · ${evidence.external_ref}`
                      : ''}
                  {evidence.note ? ` · ${evidence.note}` : ''}
                  <button
                    type='button'
                    className='ml-3 text-destructive underline-offset-4 hover:underline'
                    disabled={saving}
                    onClick={() =>
                      void updateEvidence(record.evidence.filter((item) => item.id !== evidence.id))
                    }
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
            <form
              onSubmit={addEvidence}
              className='mt-4 grid gap-2 rounded-lg border bg-muted/20 p-3 md:grid-cols-5'
            >
              <select
                className='h-9 rounded border bg-background px-2 text-sm'
                value={evidenceKind}
                onChange={(event) => setEvidenceKind(event.target.value as typeof evidenceKind)}
              >
                <option value='data'>Data</option>
                <option value='view'>View</option>
                <option value='claim'>Claim</option>
                <option value='external'>External</option>
              </select>
              {evidenceKind === 'external' ? (
                <input
                  className='h-9 rounded border bg-background px-2 text-sm md:col-span-2'
                  value={externalRef}
                  onChange={(event) => setExternalRef(event.target.value)}
                  placeholder='External source URL or citation'
                />
              ) : (
                <select
                  className='h-9 rounded border bg-background px-2 text-sm md:col-span-2'
                  value={evidenceId}
                  onChange={(event) => setEvidenceId(event.target.value)}
                >
                  <option value=''>Select evidence</option>
                  {candidates
                    .filter((item) => item.kind === evidenceKind)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title}
                      </option>
                    ))}
                </select>
              )}
              <select
                className='h-9 rounded border bg-background px-2 text-sm'
                value={polarity}
                onChange={(event) => setPolarity(event.target.value as typeof polarity)}
              >
                <option value='support'>Support</option>
                <option value='counter'>Counter</option>
              </select>
              <input
                className='h-9 rounded border bg-background px-2 text-sm'
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder='Note'
              />
              <Button
                type='submit'
                disabled={
                  saving || (evidenceKind === 'external' ? !externalRef.trim() : !evidenceId)
                }
                className='md:col-span-5 md:justify-self-start'
              >
                {saving ? 'Saving…' : 'Add evidence'}
              </Button>
            </form>
          </section>
          <section className={`${card} mt-6`}>
            <h2 className='font-semibold'>Fixed context</h2>
            <pre className='mt-3 max-h-72 overflow-auto rounded-lg bg-muted/40 p-3 text-xs'>
              {JSON.stringify(record.context_snapshot, null, 2)}
            </pre>
          </section>
          <section className={`${card} mt-6`}>
            <h2 className='font-semibold'>Revision history</h2>
            <div className='mt-3 space-y-2'>
              {record.revisions.map((revision) => (
                <details key={String(revision.id)} className='rounded-lg border px-3 py-2 text-sm'>
                  <summary className='cursor-pointer'>
                    Revision {String(revision.revision_number)} ·{' '}
                    {String(revision.snapshot_sha256).slice(0, 12)}…
                  </summary>
                  <pre className='mt-2 overflow-auto rounded bg-muted/40 p-2 text-xs'>
                    {JSON.stringify(revision.snapshot_jsonb, null, 2)}
                  </pre>
                </details>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export function ChangeSetWorkspace({ changeSetId }: { changeSetId?: string }) {
  const { activeProjectId } = useProjectScope();
  const [items, setItems] = useState<ChangeSet[]>([]);
  const [detail, setDetail] = useState<ChangeSet | null>(null);
  useEffect(() => {
    if (changeSetId)
      api
        .getChangeSet(changeSetId)
        .then(setDetail)
        .catch(() => setDetail(null));
    else
      api
        .listChangeSets(activeProjectId ?? undefined)
        .then(setItems)
        .catch(() => setItems([]));
  }, [activeProjectId, changeSetId]);
  if (changeSetId)
    return (
      <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
        <Link href='/dashboard/changes' className='text-sm text-muted-foreground'>
          ← Change Sets
        </Link>
        {detail && (
          <section className={`${card} mt-5`}>
            <p className='font-mono text-xs'>{detail.operation_kind}</p>
            <h1 className='mt-2 text-2xl font-semibold'>{detail.status}</h1>
            <pre className='mt-5 overflow-auto rounded-lg bg-muted/40 p-3 text-xs'>
              {JSON.stringify(detail.preview_jsonb, null, 2)}
            </pre>
          </section>
        )}
      </main>
    );
  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
        Review workflow
      </p>
      <h1 className='mt-2 text-3xl font-semibold'>Change Sets</h1>
      <div className='mt-6 space-y-2'>
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/dashboard/changes/${item.id}`}
            className={`${card} flex items-center justify-between`}
          >
            <span className='font-mono text-xs'>{item.operation_kind}</span>
            <span className='text-xs text-muted-foreground'>{item.status}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
