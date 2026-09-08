import { expect, test } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

test('process template maintenance sends the strict versioned contract', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = Date.now();
  const projectResponse = await request.post(`${apiUrl}/project-records`, {
    data: { project: { code: `PRJ-TEMPLATE-${suffix}`, title: 'Template project' } }
  });
  expect(projectResponse.ok(), await projectResponse.text()).toBeTruthy();
  const projectId = (await projectResponse.json()).project.id;

  await page.goto(`/dashboard/processes?project=${projectId}`);
  await page.getByRole('button', { name: 'Create' }).click();
  const form = page.locator('form').filter({ has: page.getByPlaceholder('Title') });
  await form.getByPlaceholder('Title').fill('Chromatography');
  await form.getByRole('button', { name: 'Create' }).click();
  await expect(page.getByRole('heading', { name: 'Chromatography' })).toBeVisible();
  assertBrowserHealthy();
});
