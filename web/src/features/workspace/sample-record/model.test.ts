import { describe, expect, it } from 'vitest';
import { buildNewDraft, draftToCreatePayload } from './model';

describe('v0.3 sample record model', () => {
  it('starts with a tag-based Research Object draft', () => {
    const draft = buildNewDraft();
    expect(draft.sample.tags).toBe('样品');
    expect(draft.steps).toEqual([]);
  });

  it('serializes a Process Execution draft without legacy resource kinds', () => {
    const draft = buildNewDraft();
    draft.sample.title = 'Sample A';
    draft.steps.push({
      process_definition_id: 'definition-1',
      process_definition_version_id: 'version-1',
      status: 'draft',
      object_bindings: [{ research_object_id: 'object-1', direction: 'input', role: 'source' }],
      data_bindings: []
    });
    expect(draftToCreatePayload('project-1', draft)).toMatchObject({
      project_scope_id: 'project-1',
      sample: { title: 'Sample A', tags: ['样品'] },
      steps: [{ process_definition_id: 'definition-1' }]
    });
  });
});
