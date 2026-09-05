import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, installBrowserGuards } from './browser-guards';

test('fresh database supports project creation and no-seed navigation', async ({
  page
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const projectsLoaded = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === '/api/v1/objects' &&
      url.searchParams.get('kind') === 'project' &&
      response.request().method() === 'GET'
    );
  });
  await page.goto('/dashboard/samples');
  expect((await projectsLoaded).ok()).toBeTruthy();
  await expect(page.getByTestId('project-switcher-trigger')).toBeVisible();
  await page.getByTestId('project-switcher-trigger').click();
  await expect(page.getByTestId('create-project')).toBeVisible();
  await page.getByTestId('create-project').click();
  await page.getByTestId('project-title').fill('Fresh browser project');
  await page.getByTestId('project-code').fill(`PRJ-E2E-FRESH-${Date.now()}`);
  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/project-records') && response.request().method() === 'POST'
  );
  await page.getByTestId('submit-project').click();
  const projectResponse = await createResponse;
  expect(projectResponse.ok(), await projectResponse.text()).toBeTruthy();
  const project = (await projectResponse.json()).project as { id: string };

  await page.goto(`/dashboard/samples/new?project=${project.id}`);
  await expect(page.getByTestId('sample-definition-prerequisite')).toBeVisible();
  await expect(page.getByTestId('add-sample-step')).toBeDisabled();
  await page.reload();
  await expect(page.getByTestId('sample-definition-prerequisite')).toBeVisible();

  for (const path of [
    `/dashboard/samples?project=${project.id}`,
    `/dashboard/processes?project=${project.id}`,
    `/dashboard/data?project=${project.id}`,
    `/dashboard/views?project=${project.id}`,
    `/dashboard/claims?project=${project.id}`
  ]) {
    await page.goto(path);
    await expect(page.locator('#main-content')).toBeVisible();
  }
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.reload();
  await expectNoHorizontalOverflow(page);
  assertBrowserHealthy();
});
