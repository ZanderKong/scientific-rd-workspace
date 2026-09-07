import { expect, test, type APIRequestContext } from '@playwright/test';
import { expectNoHorizontalOverflow, installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('continuous composer saves inline slots and stable Ref identities', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], {
    origin: 'http://127.0.0.1:3000'
  });
  const suffix = `${Date.now()}`;
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-COMPOSER-${suffix}`, title: 'Composer project' }
  });
  const projectId = project.project.id as string;
  await post(request, '/process-definitions', {
    code: `PFD-EXPOSURE-${suffix}`,
    title: 'Exposure',
    project_scope_id: projectId,
    execution_field_definitions: {
      fields: [
        { key: 'duration', label: 'Duration', value_type: 'number', default_unit: 'min' },
        { key: 'note', label: 'Note', value_type: 'text' }
      ]
    }
  });
  await post(request, '/process-definitions', {
    code: `PFD-MIXING-${suffix}`,
    title: 'Mixing',
    project_scope_id: projectId,
    execution_field_definitions: {
      fields: [{ key: 'speed', label: 'Speed', value_type: 'number', default_unit: 'rpm' }]
    }
  });
  await post(request, '/objects', {
    kind: 'research_object',
    code: `ROO-MATERIAL-${suffix}`,
    title: 'Resolver material',
    project_scope_id: projectId,
    tags: ['原料'],
    process_field_definitions: {
      fields: [{ key: 'quantity', label: 'Quantity', value_type: 'number', default_unit: 'g' }]
    }
  });

  await page.goto(`/dashboard/samples/new?project=${projectId}`);
  await page.getByTestId('sample-title').fill('Continuous sample');
  const editor = page.locator('[data-testid="scientific-composer"] .bn-editor');
  await editor.click();
  await page.keyboard.type('/Expo');
  await expect(page.getByText(/v1 · Duration · Note/)).toBeVisible();
  await page.getByText('Exposure', { exact: true }).last().click();
  const duration = page.getByRole('textbox', { name: 'Exposure Duration' });
  const note = page.getByRole('textbox', { name: 'Exposure Note' });
  await duration.fill('15');
  await duration.press('Tab');
  await expect(note).toBeFocused();
  await note.fill('中文记录');
  await note.press('Shift+Tab');
  await expect(duration).toBeFocused();
  await duration.press('ArrowLeft');
  await duration.press('Escape');
  await page.keyboard.press('Backspace');
  await expect(page.getByRole('textbox', { name: 'Exposure Duration' })).toHaveCount(0);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByRole('textbox', { name: 'Exposure Duration' })).toHaveValue('15');
  await expect(page.getByRole('textbox', { name: 'Exposure Note' })).toHaveValue('中文记录');
  await page.keyboard.press('ControlOrMeta+Shift+z');
  await expect(page.getByRole('textbox', { name: 'Exposure Duration' })).toHaveCount(0);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByRole('textbox', { name: 'Exposure Duration' })).toHaveValue('15');
  await page.getByRole('textbox', { name: 'Exposure Duration' }).press('Escape');
  await page.keyboard.press('ControlOrMeta+c');
  const externalText = await page.evaluate(() => navigator.clipboard.readText());
  expect(externalText).toContain('/Exposure');
  expect(externalText).toContain('Duration 15min');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ControlOrMeta+v');
  await expect(page.getByRole('button', { name: '选择过程 Exposure' })).toHaveCount(2);
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('Delete');
  await expect(page.getByRole('button', { name: '选择过程 Exposure' })).toHaveCount(1);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByRole('button', { name: '选择过程 Exposure' })).toHaveCount(2);
  await page.keyboard.press('ControlOrMeta+Shift+z');
  await expect(page.getByRole('button', { name: '选择过程 Exposure' })).toHaveCount(1);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByRole('button', { name: '选择过程 Exposure' })).toHaveCount(2);

  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Enter');
  await page.evaluate(() => navigator.clipboard.writeText('外部纯文本'));
  await page.keyboard.press('ControlOrMeta+v');
  await expect(editor).toContainText('外部纯文本');
  await page.keyboard.type(' @Resolver');
  await page.getByText('Resolver material', { exact: true }).last().click();
  await page.getByRole('button', { name: '选择对象 Resolver material' }).click();
  await page
    .locator('section')
    .filter({ hasText: '关联过程' })
    .getByRole('combobox')
    .first()
    .selectOption({ index: 1 });
  await page.getByRole('textbox', { name: 'Resolver material Quantity' }).fill('5');

  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/sample-records') && response.request().method() === 'POST'
  );
  await page.getByTestId('save-sample-record').click();
  const created = await (await createResponse).json();
  expect(created.occurrences).toHaveLength(3);
  const processOccurrences = created.occurrences.filter(
    (occurrence: { kind: string }) => occurrence.kind === 'process'
  );
  const objectOccurrence = created.occurrences.find(
    (occurrence: { kind: string }) => occurrence.kind === 'object'
  );
  expect(processOccurrences[0].execution.values).toMatchObject({
    duration: '15',
    note: '中文记录'
  });
  expect(processOccurrences[0].execution_id).not.toBe(processOccurrences[1].execution_id);
  expect(objectOccurrence.values.quantity).toMatchObject({ value: '5', unit: 'g' });
  const executionId = processOccurrences[0].execution_id as string;
  const bindingId = objectOccurrence.binding.binding_id as string;

  await page.goto(`/dashboard/samples/${created.sample.id}?project=${projectId}`);
  await page.getByRole('button', { name: '选择过程 Exposure' }).first().click();
  await page.getByRole('textbox', { name: '替换 Ref 搜索' }).fill('Mixing');
  await page.getByRole('button', { name: '查找' }).click();
  await page.getByRole('button', { name: /Mixing PFD-MIXING/ }).click();
  await expect(page.getByRole('textbox', { name: 'Mixing Speed' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Resolver material Quantity' }).fill('6');
  const updateResponse = page.waitForResponse(
    (response) =>
      response.url().includes(`/api/v1/samples/${created.sample.id}/record`) &&
      response.request().method() === 'PUT'
  );
  await page.getByTestId('save-sample-record').click();
  const updated = await (await updateResponse).json();
  expect(updated.occurrences[0].execution_id).toBe(executionId);
  expect(updated.occurrences[0].label_snapshot).toBe('Mixing');
  expect(updated.occurrences[0].values).toEqual({});
  const updatedObject = updated.occurrences.find(
    (occurrence: { kind: string }) => occurrence.kind === 'object'
  );
  expect(updatedObject.binding.binding_id).toBe(bindingId);
  expect(updatedObject.values.quantity.value).toBe('6');

  await page.getByTestId('save-and-new-sample-record').click();
  await expect(page).toHaveURL(
    new RegExp(`/dashboard/samples/new\\?project=${projectId}&from=${created.sample.id}`)
  );
  await expect(page.getByTestId('sample-title')).toHaveValue('Continuous sample');
  await expect(page.getByRole('textbox', { name: 'Resolver material Quantity' })).toHaveValue('6');
  const clonedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/sample-records') && response.request().method() === 'POST'
  );
  await page.getByTestId('save-sample-record').click();
  const cloned = await (await clonedResponse).json();
  const clonedProcesses = cloned.occurrences.filter(
    (occurrence: { kind: string }) => occurrence.kind === 'process'
  );
  const clonedObject = cloned.occurrences.find(
    (occurrence: { kind: string }) => occurrence.kind === 'object'
  );
  expect(clonedProcesses[0].execution_id).not.toBe(executionId);
  expect(clonedObject.binding.binding_id).not.toBe(bindingId);
  await expectNoHorizontalOverflow(page);
  assertBrowserHealthy();
});
