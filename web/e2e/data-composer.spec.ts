import { expect, test, type APIRequestContext } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('Data Composer restores uploaded draft and finalizes fixed representations', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = Date.now();
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-DATA-UI-${suffix}`, title: 'Data UI project' }
  });
  const sample = await post(request, '/objects', {
    kind: 'research_object',
    code: `ROO-DATA-UI-${suffix}`,
    title: 'Browser subject',
    project_scope_id: project.project.id,
    tags: ['样品']
  });

  await page.goto(`/dashboard/data/new?sample=${sample.id}`);
  await page.getByLabel('名称').fill('Browser Data');
  await page.getByLabel('观察内容').fill('Stable browser observation');
  await page.getByRole('button', { name: '开始草稿' }).click();
  await expect(page).toHaveURL(/\/dashboard\/data\/new\?draft=/);

  await page.locator('input[type="file"]').setInputFiles({
    name: 'browser.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('time,value\n0,1\n')
  });
  await expect(page.getByText('browser.csv')).toBeVisible();
  await page.getByRole('radio', { name: 'browser.csv 设为主 origin' }).check();
  await page.getByRole('button', { name: '保存草稿' }).click();
  await page.reload();
  await expect(page.getByText('browser.csv')).toBeVisible();
  await expect(page.getByLabel('观察内容')).toHaveValue('Stable browser observation');

  await page.getByRole('button', { name: 'Finalize' }).click();
  await expect(page).toHaveURL(/\/dashboard\/data\/[0-9a-f-]+(?:\?|$)/);
  await expect(page.getByRole('heading', { name: 'Browser Data' })).toBeVisible();
  await expect(page.getByText('Stable browser observation')).toBeVisible();
  await expect(page.getByText('raw_file')).toBeVisible();
  assertBrowserHealthy();
});
