import { expect, test, type APIRequestContext } from '@playwright/test';
import { expectNoHorizontalOverflow, installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('two-level scientific bullets save properties without creating another occurrence', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = `${Date.now()}`;
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-COMPOSER-${suffix}`, title: 'Composer project' }
  });
  const projectId = project.project.id as string;
  await post(request, '/process-definitions', {
    code: `PFD-EXPOSURE-${suffix}`,
    title: 'Exposure',
    project_scope_id: projectId,
    execution_field_definitions: { fields: [] }
  });

  await page.goto(`/dashboard/samples/new?project=${projectId}`);
  await page.getByTestId('sample-title').fill('Two-level sample');
  const editor = page.locator('[data-testid="scientific-composer"] .bn-editor');
  await editor.click();
  await page.keyboard.type('record @Expo');
  await page.getByText('Exposure', { exact: true }).last().click();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  await page.keyboard.type('@Expo');
  await page
    .getByText(/Exposure · 第1次/)
    .last()
    .click();
  await page.keyboard.type('｜温度: 60 ℃｜添加量: 0');

  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/sample-records') && response.request().method() === 'POST'
  );
  await page.getByTestId('save-sample-record').click();
  const created = await (await createResponse).json();
  expect(created.occurrences).toHaveLength(1);
  expect(created.occurrences[0].execution_id).toBeTruthy();
  const propertyValues = Object.values(created.occurrences[0].values).filter(
    (value: unknown) =>
      Boolean(value) && typeof value === 'object' && 'raw_value' in (value as object)
  );
  expect(propertyValues).toEqual(
    expect.arrayContaining([
      { value: '60 ℃', raw_value: '60 ℃' },
      { value: '0', raw_value: '0' }
    ])
  );

  await page.goto(`/dashboard/samples/${created.sample.id}?project=${projectId}`);
  await expect(page.getByTestId('scientific-composer')).toContainText('@Exposure');
  await expectNoHorizontalOverflow(page);
  assertBrowserHealthy();
});
