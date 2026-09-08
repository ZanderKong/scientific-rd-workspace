import { expect, test, type APIRequestContext } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown, key?: string) {
  const response = await request.post(`${apiUrl}${path}`, {
    data,
    headers: key ? { 'Idempotency-Key': key } : undefined
  });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('batch variable table creates independent Sample rows from a pinned revision', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = Date.now();
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-BATCH-UI-${suffix}`, title: 'Batch UI project' }
  });
  const definition = await post(request, '/process-definitions', {
    code: `PFD-BATCH-UI-${suffix}`,
    title: 'Batch mixing',
    project_scope_id: project.project.id,
    execution_field_definitions: {
      fields: [{ key: 'speed', label: 'Speed', value_type: 'number', default_unit: 'rpm' }]
    }
  });
  const occurrenceId = crypto.randomUUID();
  const source = await post(
    request,
    '/sample-records',
    {
      project_scope_id: project.project.id,
      sample: { title: 'Batch source', tags: ['sample'] },
      document: {
        schema_version: 1,
        blocks: [
          {
            type: 'paragraph',
            content: [{ type: 'processRef', props: { occurrenceId } }]
          }
        ]
      },
      occurrences: [
        {
          occurrence_id: occurrenceId,
          kind: 'process',
          target_id: definition.process_definition.id,
          process_definition_version_id: definition.current_version.id,
          label_snapshot: 'Batch mixing',
          field_definitions: definition.current_version.execution_field_definitions,
          values: { speed: 100 },
          status: 'recorded'
        }
      ]
    },
    `batch-ui-source-${suffix}`
  );

  await page.goto(`/dashboard/samples/${source.sample.id}/batch?project=${project.project.id}`);
  await expect(page.getByRole('heading', { name: /Batch source/ })).toBeVisible();
  await expect(page.getByLabel('Sample name')).toHaveCount(3);
  const speeds = page.getByLabel('Batch mixing Speed');
  await speeds.nth(0).fill('110');
  await speeds.nth(1).fill('120');
  await speeds.nth(2).fill('130');
  const response = page.waitForResponse(
    (item) =>
      item.url().endsWith('/api/v1/sample-records/batch') && item.request().method() === 'POST'
  );
  await page.getByRole('button', { name: '创建 3 个 Sample' }).click();
  const result = await (await response).json();
  expect(result.rows).toHaveLength(3);
  expect(
    result.rows.map(
      (row: { record: { occurrences: Array<{ values: { speed: string } }> } }) =>
        row.record.occurrences[0].values.speed
    )
  ).toEqual(['110', '120', '130']);
  await expect(page.getByRole('heading', { name: '创建成功' })).toBeVisible();
  assertBrowserHealthy();
});
