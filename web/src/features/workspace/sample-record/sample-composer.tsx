'use client';

import { useEffect, useMemo, useState } from 'react';
import { api, ApiError } from '@/lib/api-client';
import type {
  JsonObject,
  ProcessDefinition,
  ProcessExecutionObjectBindingDraft,
  ResearchObject,
  SampleRecord,
  UsageFieldDefinition
} from '@/lib/domain';
import {
  buildNewDraft,
  draftToCreatePayload,
  draftToPutPayload,
  recordToDraft,
  type SampleRecordDraft
} from './model';

type ResolverState = { step: number; query: string } | null;

const bindingRoles = ['subject', 'reagent', 'equipment', 'substrate', 'solution', 'product'];

function definitionLabel(definition: ProcessDefinition) {
  return `${definition.process_definition.title} · v${definition.current_version.version}`;
}

function fieldDefinitions(definitions: JsonObject): UsageFieldDefinition[] {
  const fields = definitions.fields;
  if (Array.isArray(fields)) {
    return fields.filter(
      (field): field is UsageFieldDefinition =>
        typeof field === 'object' && field !== null && typeof field.key === 'string'
    );
  }
  return Object.entries(definitions)
    .filter(([, definition]) => typeof definition === 'object' && definition !== null)
    .map(([key, definition]) => ({
      key,
      ...(definition as Omit<UsageFieldDefinition, 'key'>)
    }));
}

function defaultBinding(object: ResearchObject): ProcessExecutionObjectBindingDraft {
  const tags = new Set(object.tags.map((tag) => tag.toLowerCase()));
  const includes = (...terms: string[]) =>
    terms.some((term) => [...tags].some((tag) => tag.includes(term)));
  if (includes('设备', 'equipment', '仪器')) {
    return { research_object_id: object.id, direction: 'context', role: 'equipment', values: {} };
  }
  if (includes('基材', 'substrate', 'base')) {
    return { research_object_id: object.id, direction: 'input', role: 'substrate', values: {} };
  }
  if (includes('原料', '试剂', 'material', 'reagent')) {
    return { research_object_id: object.id, direction: 'input', role: 'reagent', values: {} };
  }
  return { research_object_id: object.id, direction: 'input', role: 'subject', values: {} };
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
    if (!projectId) {
      setDefinitions([]);
      setObjects([]);
      return;
    }
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
      setDraft(updateStep(draft, index, { object_bindings: [...current, defaultBinding(object)] }));
    }
    setResolver(null);
  }

  function selectFirstResolverResult(index: number) {
    if (!resolver || resolverResults.length === 0) return;
    if (resolver.query.startsWith('/')) {
      chooseDefinition(index, resolverResults[0] as ProcessDefinition);
      return;
    }
    chooseObject(index, resolverResults[0] as ResearchObject);
  }

  function addStep() {
    const definition = definitions[0];
    if (!definition) return;
    setDraft({
      ...draft,
      steps: [
        ...draft.steps,
        {
          process_definition_id: definition.process_definition.id,
          process_definition_version_id: definition.current_version.id,
          project_scope_id: projectId,
          title_snapshot: definition.process_definition.title,
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

  function updateBinding(
    stepIndex: number,
    bindingIndex: number,
    patch: Partial<ProcessExecutionObjectBindingDraft>
  ) {
    const bindings = draft.steps[stepIndex].object_bindings ?? [];
    setDraft(
      updateStep(draft, stepIndex, {
        object_bindings: bindings.map((binding, index) =>
          index === bindingIndex ? { ...binding, ...patch } : binding
        )
      })
    );
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

  const canAddStep = Boolean(projectId && definitions.length);

  return (
    <form onSubmit={submit} className='space-y-5' data-testid='sample-composer'>
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
              data-testid='sample-title'
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
              data-testid='sample-tags'
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
            data-testid='add-sample-step'
            disabled={!canAddStep}
            onClick={addStep}
            className='rounded-md border px-3 py-2 text-sm hover:border-primary disabled:cursor-not-allowed disabled:opacity-50'
          >
            Add step
          </button>
        </div>

        {!projectId && (
          <div className='rounded-2xl border border-dashed p-6 text-sm text-muted-foreground'>
            Select a project before creating a Sample Record.
          </div>
        )}
        {projectId && definitions.length === 0 && (
          <div
            className='rounded-2xl border border-dashed p-6 text-sm text-muted-foreground'
            data-testid='sample-definition-prerequisite'
          >
            No Process Definitions are available in this project. Create a definition before adding
            a Sample step.
          </div>
        )}
        {draft.steps.length === 0 && canAddStep && (
          <div className='rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground'>
            Add the first Process Execution step.
          </div>
        )}

        {draft.steps.map((step, index) => {
          const definition = definitions.find(
            (item) => item.process_definition.id === step.process_definition_id
          );
          const executionFields = fieldDefinitions(
            definition?.current_version.execution_field_definitions ?? {}
          );
          const bindings = step.object_bindings ?? [];
          return (
            <article
              key={step.execution_id ?? `new-${index}`}
              data-testid={`sample-step-${index}`}
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
                    data-testid={`move-step-up-${index}`}
                    onClick={() => moveStep(index, -1)}
                    className='rounded border px-2 py-1 text-xs'
                  >
                    ↑
                  </button>
                  <button
                    type='button'
                    aria-label='Move step down'
                    data-testid={`move-step-down-${index}`}
                    onClick={() => moveStep(index, 1)}
                    className='rounded border px-2 py-1 text-xs'
                  >
                    ↓
                  </button>
                  <button
                    type='button'
                    aria-label='Remove step'
                    data-testid={`remove-step-${index}`}
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
                    data-testid={`definition-resolver-${index}`}
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
                        query: `/${event.target.value.replace(/^\/+/, '')}`
                      })
                    }
                    onFocus={() => setResolver({ step: index, query: '/' })}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        selectFirstResolverResult(index);
                      }
                      if (event.key === 'Escape') setResolver(null);
                    }}
                  />
                  {resolver?.step === index && resolver.query.startsWith('/') && (
                    <div className='max-h-44 overflow-auto rounded-lg border bg-background p-1 shadow-sm'>
                      {resolverResults.map((candidate) => {
                        const item = candidate as ProcessDefinition;
                        return (
                          <button
                            type='button'
                            key={item.process_definition.id}
                            data-testid={`definition-option-${item.process_definition.id}`}
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
                    data-testid={`step-status-${index}`}
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
                    data-testid={`step-note-${index}`}
                    className='h-9 rounded-md border bg-background px-3'
                    value={step.note ?? ''}
                    onChange={(event) =>
                      setDraft(updateStep(draft, index, { note: event.target.value }))
                    }
                  />
                </label>

                {executionFields.map((field) => (
                  <label key={field.key} className='grid gap-1 text-sm'>
                    {field.label || field.key}
                    <input
                      data-testid={`execution-field-${index}-${field.key}`}
                      className='h-9 rounded-md border bg-background px-3'
                      value={String(step.values?.[field.key] ?? field.default_value ?? '')}
                      type={field.value_type === 'number' ? 'number' : 'text'}
                      onChange={(event) =>
                        setDraft(
                          updateStep(draft, index, {
                            values: {
                              ...step.values,
                              [field.key]: event.target.value
                            } as JsonObject
                          })
                        )
                      }
                    />
                  </label>
                ))}
              </div>

              <div className='mt-4 rounded-xl border border-dashed p-3'>
                <div className='flex items-center justify-between gap-3'>
                  <div>
                    <p className='text-sm font-medium'>Objects and tags</p>
                    <p className='text-xs text-muted-foreground'>
                      Resolve with @. Defaults follow tags; direction and role remain editable.
                    </p>
                  </div>
                  <input
                    data-testid={`object-resolver-${index}`}
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
                        query: `@${event.target.value.replace(/^@+/, '')}`
                      })
                    }
                    onFocus={() => setResolver({ step: index, query: '@' })}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        selectFirstResolverResult(index);
                      }
                      if (event.key === 'Escape') setResolver(null);
                    }}
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
                          data-testid={`object-option-${item.id}`}
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
                <div className='mt-3 grid gap-3'>
                  {bindings.map((binding, bindingIndex) => {
                    const object = objects.find((item) => item.id === binding.research_object_id);
                    const fields = fieldDefinitions(object?.process_field_definitions ?? {});
                    return (
                      <div
                        key={binding.research_object_id}
                        data-testid={`object-binding-${index}-${binding.research_object_id}`}
                        className='rounded-lg border bg-background p-3'
                      >
                        <div className='flex flex-wrap items-center justify-between gap-2'>
                          <p className='text-sm font-medium'>
                            {object?.title ?? binding.research_object_id}
                          </p>
                          <button
                            type='button'
                            data-testid={`remove-binding-${index}-${binding.research_object_id}`}
                            onClick={() =>
                              setDraft(
                                updateStep(draft, index, {
                                  object_bindings: bindings.filter(
                                    (_, candidateIndex) => candidateIndex !== bindingIndex
                                  )
                                })
                              )
                            }
                            className='text-xs text-destructive'
                          >
                            Remove binding
                          </button>
                        </div>
                        <div className='mt-3 grid gap-3 sm:grid-cols-2'>
                          <label className='grid gap-1 text-xs'>
                            Direction
                            <select
                              data-testid={`binding-direction-${index}-${binding.research_object_id}`}
                              className='h-8 rounded-md border bg-card px-2 text-sm'
                              value={binding.direction}
                              onChange={(event) =>
                                updateBinding(index, bindingIndex, {
                                  direction: event.target
                                    .value as ProcessExecutionObjectBindingDraft['direction']
                                })
                              }
                            >
                              <option value='input'>Input</option>
                              <option value='context'>Context</option>
                              <option value='output'>Output</option>
                            </select>
                          </label>
                          <label className='grid gap-1 text-xs'>
                            Role
                            <input
                              list={`binding-roles-${index}-${bindingIndex}`}
                              data-testid={`binding-role-${index}-${binding.research_object_id}`}
                              className='h-8 rounded-md border bg-card px-2 text-sm'
                              value={binding.role ?? ''}
                              onChange={(event) =>
                                updateBinding(index, bindingIndex, { role: event.target.value })
                              }
                            />
                            <datalist id={`binding-roles-${index}-${bindingIndex}`}>
                              {bindingRoles.map((role) => (
                                <option key={role} value={role}>
                                  {role}
                                </option>
                              ))}
                            </datalist>
                          </label>
                          {fields.map((field) => {
                            const value = binding.values?.[field.key];
                            return (
                              <label key={field.key} className='grid gap-1 text-xs'>
                                {field.label || field.key}
                                <div className='flex gap-2'>
                                  <input
                                    data-testid={`binding-field-${index}-${binding.research_object_id}-${field.key}`}
                                    className='h-8 min-w-0 flex-1 rounded-md border bg-card px-2 text-sm'
                                    type={field.value_type === 'number' ? 'number' : 'text'}
                                    value={String(value?.value ?? field.default_value ?? '')}
                                    onChange={(event) =>
                                      updateBinding(index, bindingIndex, {
                                        values: {
                                          ...binding.values,
                                          [field.key]: {
                                            ...value,
                                            value: event.target.value,
                                            ...(value?.unit || field.default_unit
                                              ? { unit: value?.unit ?? field.default_unit }
                                              : {})
                                          }
                                        }
                                      })
                                    }
                                  />
                                  {(value?.unit || field.default_unit) && (
                                    <input
                                      aria-label={`${field.label || field.key} unit`}
                                      className='h-8 w-16 rounded-md border bg-card px-2 text-sm'
                                      value={value?.unit ?? field.default_unit ?? ''}
                                      onChange={(event) =>
                                        updateBinding(index, bindingIndex, {
                                          values: {
                                            ...binding.values,
                                            [field.key]: {
                                              value: value?.value ?? field.default_value ?? '',
                                              unit: event.target.value
                                            }
                                          }
                                        })
                                      }
                                    />
                                  )}
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </article>
          );
        })}
      </section>

      {error && (
        <p
          role='alert'
          className='rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'
        >
          {error}
        </p>
      )}
      <button
        type='submit'
        data-testid='save-sample-record'
        disabled={saving || !draft.sample.title.trim() || draft.steps.length === 0}
        className='rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50'
      >
        {saving ? 'Saving…' : 'Save aggregate record'}
      </button>
    </form>
  );
}
