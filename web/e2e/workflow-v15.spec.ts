import { expect, test, type APIRequestContext } from '@playwright/test';
import { installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('Data, View, Claim and Experiment keep fixed revision context', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = `${Date.now()}`;
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-WF-${suffix}`, title: 'Workflow project' }
  });
  const projectId = project.project.id as string;
  const sampleResponse = await request.post(`${apiUrl}/sample-records`, {
    headers: { 'Idempotency-Key': `sample-wf-${suffix}` },
    data: {
      project_scope_id: projectId,
      sample: { code: `SMP-WF-${suffix}`, title: 'Workflow Sample', tags: ['sample'] },
      document: { schema_version: 1, blocks: [] },
      occurrences: []
    }
  });
  expect(sampleResponse.ok(), await sampleResponse.text()).toBeTruthy();
  const sample = await sampleResponse.json();
  const data = await post(request, '/data-records', {
    project_scope_id: projectId,
    data: { code: `DAT-WF-${suffix}`, title: 'Workflow Data' },
    subject_ids: [sample.sample.id]
  });
  const dataRevisions = await (
    await request.get(`${apiUrl}/objects/${data.data.id}/revisions`)
  ).json();
  const pinnedDataRevisionId = dataRevisions.at(-1).id as string;

  await page.goto(`/dashboard/data/${data.data.id}?project=${projectId}`);
  await page.getByPlaceholder('View title').fill('Pinned workflow View');
  await page.getByRole('button', { name: 'Create View' }).click();
  await expect(page).toHaveURL(/\/dashboard\/views\/[0-9a-f-]+/);
  const viewId = page.url().match(/views\/([0-9a-f-]+)/)?.[1];
  expect(viewId).toBeTruthy();

  const artifactResponse = page.waitForResponse(
    (response) =>
      response.url().includes(`/api/v1/views/${viewId}`) && response.request().method() === 'PUT'
  );
  await page.locator('input[type="file"]').setInputFiles({
    name: 'workflow.png',
    mimeType: 'image/png',
    buffer: Buffer.from('workflow-artifact')
  });
  const artifactView = await (await artifactResponse).json();
  expect(artifactView.artifact_sha256).toHaveLength(64);
  expect(artifactView.data_refs[0].data_revision_id).toBe(pinnedDataRevisionId);

  await page.getByPlaceholder('Claim statement').fill('The workflow result is reproducible.');
  await page.getByRole('button', { name: 'Create Claim' }).click();
  await expect(page).toHaveURL(/\/dashboard\/claims\/[0-9a-f-]+/);
  const claimId = page.url().match(/claims\/([0-9a-f-]+)/)?.[1];
  expect(claimId).toBeTruthy();
  await page.getByRole('combobox').first().selectOption('external');
  await page.getByPlaceholder('External source URL or citation').fill('doi:10.1000/workflow');
  await page.getByRole('button', { name: 'Add evidence' }).click();
  await expect(page.getByText(/support · external · doi:10\.1000\/workflow/)).toBeVisible();
  const claim = await (await request.get(`${apiUrl}/claims/${claimId}`)).json();
  expect(claim.primary_source).toEqual({
    kind: 'view',
    object_id: viewId,
    revision_id: artifactView.current_revision_id
  });
  expect(claim.context_snapshot.data_refs[0].data_revision_id).toBe(pinnedDataRevisionId);

  await page.goto(`/dashboard/projects/${projectId}/experiments/new`);
  await page.getByRole('link', { name: 'Create Sample and return' }).click();
  await page.getByTestId('sample-title').fill('Returned Sample');
  await page.getByTestId('save-sample-record').click();
  await expect(page).toHaveURL(/\/experiments\/new\?selectedSample=[0-9a-f-]+/);
  await expect(page.getByLabel('Returned Sample')).toBeChecked();
  await page.getByPlaceholder('Experiment title').fill('Picked Sample experiment');
  await page.getByRole('button', { name: 'Save with 1 Sample' }).click();
  await expect(page).toHaveURL(/\/dashboard\/experiments\/[0-9a-f-]+/);
  await expect(page.getByText('Returned Sample', { exact: true })).toBeVisible();
  assertBrowserHealthy();
});
