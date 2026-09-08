import { expect, test } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

test('composer creates an object with fields and inserts it at the @ position', async ({
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
  await page.locator('[data-testid="scientific-composer"] .bn-editor').click();
  await page.keyboard.type('@Novel solvent');
  await page.getByRole('button', { name: /新建对象“Novel solvent”/ }).click();
  await page.getByRole('button', { name: '新增自身属性' }).click();
  await page.getByPlaceholder('属性 key').fill('CAS');
  await page.getByPlaceholder('属性值').fill('64-17-5');
  await page.getByRole('button', { name: '新增使用属性' }).click();
  const composer = page.getByTestId('scientific-composer');
  await composer.getByRole('textbox', { name: '名称' }).last().fill('Amount');
  await composer.getByRole('textbox', { name: '稳定 key' }).fill('amount');
  await composer.getByRole('button', { name: '创建并插入' }).click();
  await expect(page.getByRole('button', { name: '选择对象 Novel solvent' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Novel solvent Amount' }).fill('2 ml');
  const saved = page.waitForResponse(
    (item) => item.url().endsWith('/api/v1/sample-records') && item.request().method() === 'POST'
  );
  await page.getByTestId('save-sample-record').click();
  const body = await (await saved).json();
  expect(body.occurrences[0].values).toMatchObject({ amount: { value: '2 ml' } });
  const createdObject = await request.get(`${apiUrl}/objects/${body.occurrences[0].target_id}`);
  expect(createdObject.ok(), await createdObject.text()).toBeTruthy();
  expect((await createdObject.json()).properties_jsonb).toMatchObject({ CAS: '64-17-5' });
  assertBrowserHealthy();
});
