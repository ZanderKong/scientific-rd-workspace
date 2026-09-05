import { expect, test, type APIRequestContext } from '@playwright/test';
import { expectNoHorizontalOverflow, installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

type Fixture = {
  projectId: string;
  preparationId: string;
  exposureId: string;
  material: { id: string };
  mixer: { id: string };
  substrate: { id: string };
};

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

async function createComposerFixture(request: APIRequestContext): Promise<Fixture> {
  const suffix = `${Date.now()}`;
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-E2E-${suffix}`, title: 'Composer browser project' }
  });
  const projectId = project.project.id as string;
  const preparation = await post(request, '/process-definitions', {
    code: `PFD-PREP-${suffix}`,
    title: 'Preparation',
    project_scope_id: projectId,
    execution_field_definitions: {
      fields: [
        { key: 'temperature', label: 'Temperature', value_type: 'number', default_unit: '°C' }
      ]
    }
  });
  const exposure = await post(request, '/process-definitions', {
    code: `PFD-EXPOSURE-${suffix}`,
    title: 'Exposure',
    project_scope_id: projectId,
    execution_field_definitions: {
      fields: [{ key: 'duration', label: 'Duration', value_type: 'number', default_unit: 'min' }]
    }
  });
  const material = await post(request, '/objects', {
    kind: 'research_object',
    code: `ROO-MATERIAL-${suffix}`,
    title: 'Resolver material',
    project_scope_id: projectId,
    tags: ['原料', '试剂'],
    process_field_definitions: {
      fields: [{ key: 'quantity', label: 'Quantity', value_type: 'number', default_unit: 'g' }]
    }
  });
  const mixer = await post(request, '/objects', {
    kind: 'research_object',
    code: `ROO-MIXER-${suffix}`,
    title: 'Resolver mixer',
    project_scope_id: projectId,
    tags: ['设备'],
    process_field_definitions: {
      fields: [{ key: 'rpm', label: 'RPM', value_type: 'number', default_unit: 'rpm' }]
    }
  });
  const substrate = await post(request, '/objects', {
    kind: 'research_object',
    code: `ROO-SUBSTRATE-${suffix}`,
    title: 'Resolver substrate',
    project_scope_id: projectId,
    tags: ['基材']
  });
  return {
    projectId,
    preparationId: preparation.process_definition.id,
    exposureId: exposure.process_definition.id,
    material,
    mixer,
    substrate
  };
}

test('composer pins definitions, persists editable bindings, and preserves execution identity', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const fixture = await createComposerFixture(request);
  await page.goto(`/dashboard/samples/new?project=${fixture.projectId}`);
  await expect(page.getByTestId('add-sample-step')).toBeEnabled();
  await page.getByTestId('sample-title').fill('Browser aggregate sample');
  await page.getByTestId('add-sample-step').click();

  await page.getByTestId('definition-resolver-0').fill('/Exposure');
  await page.getByTestId(`definition-option-${fixture.exposureId}`).click();
  await page.getByTestId('execution-field-0-duration').fill('15');

  await page.getByTestId('object-resolver-0').fill('@Resolver material');
  await page.getByTestId(`object-option-${fixture.material.id}`).click();
  await expect(page.getByTestId(`binding-direction-0-${fixture.material.id}`)).toHaveValue('input');
  await expect(page.getByTestId(`binding-role-0-${fixture.material.id}`)).toHaveValue('reagent');
  await page.getByTestId(`binding-field-0-${fixture.material.id}-quantity`).fill('5');

  await page.getByTestId('object-resolver-0').fill('@Resolver mixer');
  await page.getByTestId(`object-option-${fixture.mixer.id}`).click();
  await expect(page.getByTestId(`binding-direction-0-${fixture.mixer.id}`)).toHaveValue('context');
  await expect(page.getByTestId(`binding-role-0-${fixture.mixer.id}`)).toHaveValue('equipment');
  await page.getByTestId(`binding-field-0-${fixture.mixer.id}-rpm`).fill('700');

  await page.getByTestId('object-resolver-0').fill('@Resolver substrate');
  await page.getByTestId(`object-option-${fixture.substrate.id}`).click();
  await expect(page.getByTestId(`binding-direction-0-${fixture.substrate.id}`)).toHaveValue(
    'input'
  );
  await expect(page.getByTestId(`binding-role-0-${fixture.substrate.id}`)).toHaveValue('substrate');

  await page.getByTestId('add-sample-step').click();
  await page.getByTestId('add-sample-step').click();
  await page.getByTestId('remove-step-2').click();
  await page.getByTestId('move-step-up-1').click();
  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/sample-records') && response.request().method() === 'POST'
  );
  await page.getByTestId('save-sample-record').click();
  const saved = await (await createResponse).json();
  expect(saved.steps).toHaveLength(2);
  const sampleId = saved.sample.id as string;
  const executionIds = saved.steps.map((step: { execution: { id: string } }) => step.execution.id);
  const boundExecution = saved.steps.find(
    (step: { execution: { object_bindings: Array<{ research_object_id: string }> } }) =>
      step.execution.object_bindings.some(
        (binding) => binding.research_object_id === fixture.material.id
      )
  );
  expect(boundExecution.execution.values.duration).toBe('15');
  expect(
    boundExecution.execution.object_bindings.find(
      (binding: { research_object_id: string }) =>
        binding.research_object_id === fixture.material.id
    ).values.quantity
  ).toMatchObject({ value: '5', unit: 'g' });

  await page.goto(`/dashboard/samples/new?project=${fixture.projectId}&from=${sampleId}`);
  const quantity = page.locator(`[data-testid$='-${fixture.material.id}-quantity']`);
  await expect(quantity).toHaveValue('5');
  await quantity.fill('6');
  const updateResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/samples/${sampleId}/record`) &&
      response.request().method() === 'PUT'
  );
  await page.getByTestId('save-sample-record').click();
  const updated = await (await updateResponse).json();
  expect(updated.steps.map((step: { execution: { id: string } }) => step.execution.id)).toEqual(
    executionIds
  );
  expect(
    updated.steps
      .flatMap(
        (step: {
          execution: { object_bindings: Array<{ research_object_id: string; values: object }> };
        }) => step.execution.object_bindings
      )
      .find(
        (binding: { research_object_id: string }) =>
          binding.research_object_id === fixture.material.id
      ).values
  ).toMatchObject({ quantity: { value: '6', unit: 'g' } });
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await expectNoHorizontalOverflow(page);
  assertBrowserHealthy();
});
