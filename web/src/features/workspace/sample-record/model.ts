import type { ProcessExecutionDraft, SampleRecord } from '@/lib/domain';

export type SampleRecordDraft = {
  sample: { title: string; code?: string; status: string; tags: string };
  steps: ProcessExecutionDraft[];
};

export function buildNewDraft(): SampleRecordDraft {
  return { sample: { title: '', code: '', status: 'draft', tags: '样品' }, steps: [] };
}

export function recordToDraft(record: SampleRecord): SampleRecordDraft {
  return {
    sample: { title: record.sample.title, code: record.sample.code, status: record.sample.status, tags: record.sample.tags.join(',') },
    steps: record.steps.map(({ execution }) => ({
      process_definition_id: execution.process_definition_id,
      process_definition_version_id: execution.process_definition_version_id,
      project_scope_id: execution.project_scope_id,
      title_snapshot: execution.title_snapshot,
      status: execution.status as ProcessExecutionDraft['status'],
      values: execution.values,
      note: execution.note,
      object_bindings: execution.object_bindings.filter((binding) => binding.role !== 'sample_record').map((binding) => ({ research_object_id: binding.research_object_id, direction: binding.direction, role: binding.role, values: binding.values, order_index: binding.order_index })),
      data_bindings: execution.data_bindings.map((binding) => ({ data_id: binding.data_id, direction: binding.direction, role: binding.role, values: binding.values, order_index: binding.order_index }))
    }))
  };
}

export function draftToCreatePayload(projectId: string, draft: SampleRecordDraft) {
  return { project_scope_id: projectId, sample: { title: draft.sample.title, code: draft.sample.code?.trim() || undefined, status: draft.sample.status, tags: draft.sample.tags.split(',').map((tag) => tag.trim()).filter(Boolean) }, steps: draft.steps };
}

export function draftToPutPayload(draft: SampleRecordDraft) {
  return { sample: { title: draft.sample.title, status: draft.sample.status, tags: draft.sample.tags.split(',').map((tag) => tag.trim()).filter(Boolean) }, steps: draft.steps };
}
