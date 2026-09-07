import { expect, test, type APIRequestContext } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('Sample table keeps cross-page selection and closes URL Peek with Back', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = `${Date.now()}`;
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-TABLE-${suffix}`, title: 'Table project' }
  });
  const projectId = project.project.id as string;
  const definition = await post(request, '/process-definitions', {
    code: `PFD-TABLE-${suffix}`,
    title: 'Table Process',
    project_scope_id: projectId,
    execution_field_definitions: {
      fields: [
        { key: 'temperature', label: 'Temperature', value_type: 'number', default_unit: '°C' }
      ]
    }
  });
  const occurrenceId = crypto.randomUUID();
  const rows = Array.from({ length: 51 }, (_, index) => ({
    client_row_id: `row-${index}`,
    record: {
      project_scope_id: projectId,
      sample: {
        code: `TAB-${suffix}-${index.toString().padStart(2, '0')}`,
        title: `Table Sample ${index.toString().padStart(2, '0')}`,
        tags: ['sample']
      },
      document: {
        schema_version: 1,
        blocks:
          index === 0
            ? [
                {
                  type: 'paragraph',
                  content: [{ type: 'processRef', props: { occurrenceId } }]
                }
              ]
            : []
      },
      occurrences:
        index === 0
          ? [
              {
                occurrence_id: occurrenceId,
                kind: 'process',
                target_id: definition.process_definition.id,
                process_definition_version_id: definition.current_version.id,
                field_definitions: definition.current_version.execution_field_definitions,
                values: { temperature: 42 },
                status: 'recorded'
              }
            ]
          : []
    }
  }));
  const batch = await request.post(`${apiUrl}/sample-records/batch`, {
    headers: { 'Idempotency-Key': `table-batch-${suffix}` },
    data: { project_scope_id: projectId, rows }
  });
  expect(batch.ok(), await batch.text()).toBeTruthy();

  await page.goto(`/dashboard/samples?project=${projectId}`);
  await expect(page.getByText(/共 51 条/)).toBeVisible();
  await page.getByText('显示字段列').click();
  await page.getByRole('checkbox', { name: 'Table Process · temperature' }).check();
  await expect(page).toHaveURL(/columns=/);
  const search = page.getByPlaceholder('Search sample title or code…');
  await search.fill('Table Sample 00');
  await expect(page.getByText('42 °C')).toBeVisible();
  await search.fill('');
  await expect(page.getByText(/共 51 条/)).toBeVisible();
  await expect(page.getByText('未引用').first()).toBeVisible();
  await page.locator('label').filter({ hasText: '选择字段' }).locator('select').selectOption({
    label: 'Table Process · temperature'
  });
  await page.getByLabel('值').fill('9999');
  await page.getByRole('button', { name: '添加筛选' }).click();
  await expect(page.getByText(/共 0 条/)).toBeVisible();
  await expect(page.getByRole('button', { name: '清除筛选' })).toBeVisible();
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.getByText(/共 51 条/)).toBeVisible();
  await page
    .getByRole('checkbox', { name: /选择 Table Sample/ })
    .first()
    .check();
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page.getByText('已选择 1 条，其中 1 条在其他页')).toBeVisible();
  await page.getByRole('button', { name: '上一页' }).click();
  await page.getByRole('button', { name: '预览' }).first().click();
  await expect(page).toHaveURL(/peek=/);
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.goBack();
  await expect(page).not.toHaveURL(/peek=/);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  assertBrowserHealthy();
});
