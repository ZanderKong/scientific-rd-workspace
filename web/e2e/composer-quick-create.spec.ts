import { expect, test } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

test('composer creates an object from the @ menu and inserts its occurrence', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = Date.now();
  const response = await request.post(`${apiUrl}/project-records`, {
    data: { project: { code: `PRJ-QUICK-${suffix}`, title: 'Quick create project' } }
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const projectId = (await response.json()).project.id;

  await page.goto(`/dashboard/samples/new?project=${projectId}`);
  await page.getByTestId('sample-title').fill('Quick create sample');
  const editor = page.locator('[data-testid="scientific-composer"] .bn-editor');
  await editor.click();
  await page.keyboard.type('@Novel solvent');
  await page.getByText('新建对象「Novel solvent」', { exact: true }).click();
  await expect(editor).toContainText('@Novel solvent');

  const saved = page.waitForResponse(
    (item) => item.url().endsWith('/api/v1/sample-records') && item.request().method() === 'POST'
  );
  await page.getByTestId('save-sample-record').click();
  const body = await (await saved).json();
  expect(body.occurrences).toHaveLength(1);
  expect(body.occurrences[0].kind).toBe('object');
  const createdObject = await request.get(`${apiUrl}/objects/${body.occurrences[0].target_id}`);
  expect(createdObject.ok(), await createdObject.text()).toBeTruthy();
  expect((await createdObject.json()).title).toBe('Novel solvent');
  assertBrowserHealthy();
});
