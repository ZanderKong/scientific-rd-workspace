import { expect, test } from '@playwright/test';

test('save response advances the base while preserving newer editor input', async ({ page }) => {
  const projectId = '11111111-1111-4111-8111-111111111111';
  const sampleId = '22222222-2222-4222-8222-222222222222';
  const project = {
    id: projectId,
    kind: 'project',
    code: 'PRJ-RACE',
    title: 'Race Project',
    status: 'active',
    project_scope_id: null,
    tags: [],
    properties_jsonb: {},
    process_field_definitions: {},
    content_document: [],
    document_format_version: 1,
    created_at: '2026-09-06T00:00:00Z',
    updated_at: '2026-09-06T00:00:00Z'
  };
  const sample = {
    id: sampleId,
    kind: 'research_object',
    code: 'ROO-RACE',
    title: 'Race Sample',
    status: 'draft',
    project_scope_id: projectId,
    tags: ['sample'],
    properties_jsonb: {},
    process_field_definitions: {},
    content_document: [],
    document_format_version: 1,
    created_at: '2026-09-06T00:00:00Z',
    updated_at: '2026-09-06T00:00:00Z'
  };
  let record = {
    record_sha256: 'a'.repeat(64),
    sample,
    document: { schema_version: 1, blocks: [{ type: 'paragraph', content: [] }] },
    occurrences: [],
    data: [],
    editable: true,
    edit_blockers: []
  };
  const writes: Array<{ base_record_sha256: string }> = [];
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/api/v1/objects' && url.searchParams.get('kind') === 'project') {
      await route.fulfill({ json: [project] });
      return;
    }
    if (url.pathname === `/api/v1/samples/${sampleId}/record`) {
      if (request.method() === 'PUT') {
        const payload = request.postDataJSON() as { base_record_sha256: string };
        writes.push(payload);
        if (writes.length === 1) {
          await gate;
          record = { ...record, record_sha256: 'b'.repeat(64) };
        } else {
          record = { ...record, record_sha256: 'c'.repeat(64) };
        }
      }
      await route.fulfill({ json: record });
      return;
    }
    if (url.pathname === `/api/v1/objects/${sampleId}/revisions`) {
      await route.fulfill({ json: [] });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.goto(`http://127.0.0.1:3000/dashboard/samples/${sampleId}?project=${projectId}`);
  const editor = page.locator('[data-testid="scientific-composer"] .bn-editor');
  await editor.waitFor();
  await editor.click();
  await page.keyboard.type('before save');
  await page.getByTestId('save-sample-record').click();
  await page.waitForFunction(() =>
    document.querySelector('[data-testid="save-sample-record"]')?.hasAttribute('disabled')
  );
  await editor.click();
  await page.keyboard.type(' edited while saving');
  release();
  await expect(page.getByTestId('save-sample-record')).toBeEnabled();
  await page.getByTestId('save-sample-record').click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes[0].base_record_sha256).toBe('a'.repeat(64));
  expect(writes[1].base_record_sha256).toBe('b'.repeat(64));
  await expect(page.getByRole('alert')).toHaveText('');
});
