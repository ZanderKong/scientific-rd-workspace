'use client';

import { useEffect, useMemo, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type { JsonObject, ProcessDefinition, ResearchObject, SampleRecord } from '@/lib/domain';
import {
  buildNewDraft,
  draftToCreatePayload,
  draftToPutPayload,
  recordToDraft,
  type SampleRecordDraft
} from './model';

type ResolverState = { step: number; query: string } | null;

function definitionLabel(definition: ProcessDefinition) {
  return `${definition.process_definition.title} · v${definition.current_version.version}`;
}

function updateStep(
  draft: SampleRecordDraft,
  index: number,
  patch: Partial<SampleRecordDraft['steps'][number]>
) {
  return {
    ...draft,
    steps: draft.steps.map((step, stepIndex) =>
      stepIndex === index ? { ...step, ...patch } : step
    )
  };
}

export function SampleComposer({
  projectId,
  initialRecord,
  onSaved
}: {
  projectId: string;
  initialRecord?: SampleRecord | null;
  onSaved?: (record: SampleRecord) => void;
}) {
  const [definitions, setDefinitions] = useState<ProcessDefinition[]>([]);
  const [objects, setObjects] = useState<ResearchObject[]>([]);
  const [draft, setDraft] = useState<SampleRecordDraft>(() =>
    initialRecord ? recordToDraft(initialRecord) : buildNewDraft()
  );
  const [resolver, setResolver] = useState<ResolverState>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(initialRecord ? recordToDraft(initialRecord) : buildNewDraft());
  }, [initialRecord]);

  useEffect(() => {
    api
      .listProcessDefinitions({ project_scope_id: projectId })
      .then(setDefinitions)
      .catch(() => setDefinitions([]));
    api
      .listObjects({
        kind: 'research_object',
        project_scope_id: projectId,
        include_global: true,
        limit: 100
      })
      .then(setObjects)
      .catch(() => setObjects([]));
  }, [projectId]);

  const resolverResults = useMemo(() => {
    if (!resolver) return [];
    const query = resolver.query.replace(/^[/@]/, '').trim().toLowerCase();
    if (resolver.query.startsWith('/')) {
      return definitions.filter((item) => {
        const haystack =
          `${item.process_definition.title} ${item.process_definition.code}`.toLowerCase();
        return !query || haystack.includes(query);
      });
    }
    return objects.filter((item) => {
      const haystack = `${item.title} ${item.code} ${item.tags.join(' ')}`.toLowerCase();
      return !query || haystack.includes(query);
    });
  }, [definitions, objects, resolver]);

  function chooseDefinition(index: number, definition: ProcessDefinition) {
    const step = draft.steps[index];
    setDraft(
      updateStep(draft, index, {
        process_definition_id: definition.process_definition.id,
        process_definition_version_id: definition.current_version.id,
        project_scope_id: projectId,
        title_snapshot: definition.process_definition.title,
        values: step.values ?? {}
      })
    );
    setResolver(null);
  }

  function chooseObject(index: number, object: ResearchObject) {
    const step = draft.steps[index];
    const current = step.object_bindings ?? [];
    if (!current.some((binding) => binding.research_object_id === object.id)) {
      setDraft(
        updateStep(draft, index, {
          object_bindings: [
            ...current,
            { research_object_id: object.id, direction: 'input', role: 'subject', values: {} }
          ]
        })
      );
    }
    setResolver(null);
  }

  function addStep() {
    const definition = definitions[0];
    setDraft({
      ...draft,
      steps: [
        ...draft.steps,
        {
          process_definition_id: definition?.process_definition.id ?? '',
          process_definition_version_id: definition?.current_version.id,
          project_scope_id: projectId,
          title_snapshot: definition?.process_definition.title,
          status: 'draft',
          values: {},
          object_bindings: [],
          data_bindings: []
        }
      ]
    });
  }

  function moveStep(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= draft.steps.length) return;
    const steps = [...draft.steps];
    [steps[index], steps[target]] = [steps[target], steps[index]];
    setDraft({ ...draft, steps });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (
      !draft.sample.title.trim() ||
      draft.steps.length === 0 ||
      draft.steps.some((step) => !step.process_definition_id)
    ) {
      setError('Add a title and choose a Process Definition for every step.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = initialRecord
        ? await api.updateSampleRecord(initialRecord.sample.id, draftToPutPayload(draft))
        : await api.createSampleRecord(draftToCreatePayload(projectId, draft));
      onSaved?.(saved);
    } catch (cause) {
      setError(
        cause instanceof ApiError || cause instanceof Error ? cause.message : 'Request failed'
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className='space-y-5'>
      <section className='rounded-2xl border bg-card/80 p-5'>
        <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
          Sample Composer
        </p>
        <h1 className='mt-2 text-xl font-semibold'>
          {initialRecord ? 'Edit sample record' : 'New sample record'}
        </h1>
        <p className='mt-1 text-sm text-muted-foreground'>
          Build an ordered aggregate. Each step keeps its execution identity and pinned definition
          version.
        </p>
        <div className='mt-5 grid gap-4 md:grid-cols-2'>
          <label className='grid gap-1 text-sm'>
            Title
            <input
              required
              className='h-9 rounded-md border bg-background px-3'
              value={draft.sample.title}
              onChange={(event) =>
                setDraft({ ...draft, sample: { ...draft.sample, title: event.target.value } })
              }
            />
          </label>
          <label className='grid gap-1 text-sm'>
            Tags
            <input
              className='h-9 rounded-md border bg-background px-3'
              value={draft.sample.tags}
              onChange={(event) =>
                setDraft({ ...draft, sample: { ...draft.sample, tags: event.target.value } })
              }
            />
          </label>
        </div>
      </section>

      <section className='space-y-3'>
        <div className='flex items-center justify-between gap-3'>
          <div>
            <h2 className='font-semibold'>Process steps</h2>
            <p className='text-sm text-muted-foreground'>
              Use “/” for definitions and “@” for scoped objects or tags.
            </p>
          </div>
          <button
            type='button'
            onClick={addStep}
            className='rounded-md border px-3 py-2 text-sm hover:border-primary'
          >
            Add step
          </button>
        </div>

        {draft.steps.length === 0 && (
          <div className='rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground'>
            Add the first Process Execution step.
          </div>
        )}

        {draft.steps.map((step, index) => {
          const definition = definitions.find(
            (item) => item.process_definition.id === step.process_definition_id
          );
          const fields = Object.entries(
            definition?.current_version.execution_field_definitions ?? {}
          );
          const bindings = step.object_bindings ?? [];
          return (
            <article
              key={step.execution_id ?? `new-${index}`}
              className='rounded-2xl border bg-card/80 p-5'
            >
              <div className='flex items-start justify-between gap-3'>
                <div>
                  <p className='font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground'>
                    Step {index + 1}
                  </p>
                  <p className='mt-1 text-xs text-muted-foreground'>
                    {step.execution_id
                      ? `Execution ${step.execution_id.slice(0, 8)}`
                      : 'New execution'}
                  </p>
                </div>
                <div className='flex gap-1'>
                  <button
                    type='button'
                    aria-label='Move step up'
                    onClick={() => moveStep(index, -1)}
                    className='rounded border px-2 py-1 text-xs'
                  >
                    ↑
                  </button>
                  <button
                    type='button'
                    aria-label='Move step down'
                    onClick={() => moveStep(index, 1)}
                    className='rounded border px-2 py-1 text-xs'
                  >
                    ↓
                  </button>
                  <button
                    type='button'
                    aria-label='Remove step'
                    onClick={() =>
                      setDraft({
                        ...draft,
                        steps: draft.steps.filter((_, stepIndex) => stepIndex !== index)
                      })
                    }
                    className='rounded border px-2 py-1 text-xs text-destructive'
                  >
                    Remove
                  </button>
                </div>
              </div>

              <div className='mt-4 grid gap-4 md:grid-cols-2'>
                <label className='grid gap-1 text-sm md:col-span-2'>
                  Process Definition
                  <input
                    className='h-9 rounded-md border bg-background px-3'
                    value={
                      resolver?.step === index && resolver.query.startsWith('/')
                        ? resolver.query
                        : definition
                          ? definitionLabel(definition)
                          : step.process_definition_id
                    }
                    placeholder='/ search definitions'
                    onChange={(event) =>
                      setResolver({
                        step: index,
                        query: event.target.value.startsWith('/')
                          ? event.target.value
                          : `/${event.target.value}`
                      })
                    }
                    onFocus={() => setResolver({ step: index, query: '/' })}
                  />
                  {resolver?.step === index && resolver.query.startsWith('/') && (
                    <div className='max-h-44 overflow-auto rounded-lg border bg-background p-1 shadow-sm'>
                      {resolverResults.map((candidate) => {
                        const item = candidate as ProcessDefinition;
                        return (
                          <button
                            type='button'
                            key={item.process_definition.id}
                            onClick={() => chooseDefinition(index, item)}
                            className='block w-full rounded px-3 py-2 text-left text-sm hover:bg-muted'
                          >
                            {definitionLabel(item)}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </label>

                <label className='grid gap-1 text-sm'>
                  Status
                  <select
                    className='h-9 rounded-md border bg-background px-3'
                    value={step.status ?? 'draft'}
                    onChange={(event) =>
                      setDraft(
                        updateStep(draft, index, {
                          status: event.target.value as SampleRecordDraft['steps'][number]['status']
                        })
                      )
                    }
                  >
                    <option value='draft'>Draft</option>
                    <option value='running'>Running</option>
                    <option value='completed'>Completed</option>
                    <option value='cancelled'>Cancelled</option>
                  </select>
                </label>
                <label className='grid gap-1 text-sm'>
                  Note
                  <input
                    className='h-9 rounded-md border bg-background px-3'
                    value={step.note ?? ''}
                    onChange={(event) =>
                      setDraft(updateStep(draft, index, { note: event.target.value }))
                    }
                  />
                </label>

                {fields.map(([key, definitionValue]) => {
                  const field =
                    typeof definitionValue === 'object' && definitionValue !== null
                      ? (definitionValue as { label?: string; value_type?: string })
                      : {};
                  return (
                    <label key={key} className='grid gap-1 text-sm'>
                      {field.label ?? key}
                      <input
                        className='h-9 rounded-md border bg-background px-3'
                        value={String(step.values?.[key] ?? '')}
                        type={field.value_type === 'number' ? 'number' : 'text'}
                        onChange={(event) =>
                          setDraft(
                            updateStep(draft, index, {
                              values: { ...step.values, [key]: event.target.value } as JsonObject
                            })
                          )
                        }
                      />
                    </label>
                  );
                })}
              </div>

              <div className='mt-4 rounded-xl border border-dashed p-3'>
                <div className='flex items-center justify-between gap-3'>
                  <div>
                    <p className='text-sm font-medium'>Objects and tags</p>
                    <p className='text-xs text-muted-foreground'>
                      Resolve with @, then bind the object as a subject input.
                    </p>
                  </div>
                  <input
                    className='h-8 w-48 rounded-md border bg-background px-2 text-sm'
                    placeholder='@ object or tag'
                    value={
                      resolver?.step === index && resolver.query.startsWith('@')
                        ? resolver.query
                        : ''
                    }
                    onChange={(event) =>
                      setResolver({
                        step: index,
                        query: event.target.value.startsWith('@')
                          ? event.target.value
                          : `@${event.target.value}`
                      })
                    }
                    onFocus={() => setResolver({ step: index, query: '@' })}
                  />
                </div>
                {resolver?.step === index && resolver.query.startsWith('@') && (
                  <div className='mt-2 max-h-36 overflow-auto rounded-lg border bg-background p-1'>
                    {resolverResults.map((candidate) => {
                      const item = candidate as ResearchObject;
                      return (
                        <button
                          type='button'
                          key={item.id}
                          onClick={() => chooseObject(index, item)}
                          className='block w-full rounded px-3 py-2 text-left text-sm hover:bg-muted'
                        >
                          <span className='font-medium'>{item.title}</span>
                          <span className='ml-2 text-xs text-muted-foreground'>
                            {item.tags.join(' · ') || item.kind}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
                <div className='mt-3 flex flex-wrap gap-2'>
                  {bindings
                    .filter(
                      (binding) => binding.role !== 'sample_record' && binding.role !== 'product'
                    )
                    .map((binding) => {
                      const object = objects.find((item) => item.id === binding.research_object_id);
                      return (
                        <button
                          type='button'
                          key={binding.research_object_id}
                          onClick={() =>
                            setDraft(
                              updateStep(draft, index, {
                                object_bindings: bindings.filter(
                                  (candidate) => candidate !== binding
                                )
                              })
                            )
                          }
                          className='rounded-full bg-muted px-3 py-1 text-xs hover:bg-destructive/10'
                        >
                          {object?.title ?? binding.research_object_id} ×
                        </button>
                      );
                    })}
                </div>
              </div>
            </article>
          );
        })}
      </section>

      {error && (
        <p className='rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>
          {error}
        </p>
      )}
      <button
        disabled={saving || !draft.sample.title.trim() || draft.steps.length === 0}
        className='rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50'
      >
        {saving ? 'Saving…' : 'Save aggregate record'}
      </button>
    </form>
  );
}
