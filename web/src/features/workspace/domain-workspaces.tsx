'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
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
  const scope = projectId ?? activeProjectId;
  const [items, setItems] = useState<ResearchObject[]>([]);
  const [record, setRecord] = useState<ExperimentRecord | null>(null);
  const [title, setTitle] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(create);
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
  async function createExperiment(event: React.FormEvent) {
    event.preventDefault();
    if (!scope || !title.trim()) return;
    try {
      const next = await api.createExperimentRecord({
        project_scope_id: scope,
        experiment: { title: title.trim(), status: 'draft' },
        references: []
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
        <form onSubmit={createExperiment} className={`${card} mb-5 flex gap-2`}>
          <input
            className='h-9 flex-1 rounded-md border bg-background px-3 text-sm'
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder='Experiment title'
          />
          <Button type='submit'>Save</Button>
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
        </>
      )}
    </main>
  );
}

export function ViewWorkspace({ viewId }: { viewId: string }) {
  const [record, setRecord] = useState<ViewRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .getView(viewId)
      .then(setRecord)
      .catch((cause) => setError(message(cause)));
  }, [viewId]);
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
        </>
      )}
    </main>
  );
}

export function ClaimWorkspace({ claimId }: { claimId: string }) {
  const [record, setRecord] = useState<ClaimRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .getClaim(claimId)
      .then(setRecord)
      .catch((cause) => setError(message(cause)));
  }, [claimId]);
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
            <span className='rounded-full border px-2 py-1'>Source: {record.source_type}</span>
            <span className='rounded-full border px-2 py-1'>
              Confidence: {record.confidence ?? 'not set'}
            </span>
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
                </div>
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
