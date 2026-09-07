import { expect, test, type APIRequestContext } from '@playwright/test';
import { expectNoHorizontalOverflow, installBrowserGuards } from './browser-guards';

const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000/api/v1';

async function post(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

async function get(request: APIRequestContext, path: string) {
  const response = await request.get(`${apiUrl}${path}`);
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

test('golden scientific records remain visible and shared references survive experiment deletion', async ({
  page,
  request
}, testInfo) => {
  const assertBrowserHealthy = installBrowserGuards(page, testInfo);
  const suffix = `${Date.now()}`;
  const project = await post(request, '/project-records', {
    project: { code: `PRJ-GOLDEN-${suffix}`, title: 'Golden Cl₂ browser project' }
  });
  const projectId = project.project.id as string;
  const definition = await post(request, '/process-definitions', {
    code: `PFD-GOLDEN-${suffix}`,
    title: 'Cl₂ response measurement',
    project_scope_id: projectId
  });
  const sample = await post(request, '/objects', {
    kind: 'research_object',
    code: `ROO-GOLDEN-${suffix}`,
    title: 'Golden sensor strip',
    project_scope_id: projectId,
    tags: ['样品']
  });
  const responseData = await post(request, '/data-records', {
    project_scope_id: projectId,
    data: { code: `DAT-RESPONSE-${suffix}`, title: 'Cl₂ response curve' },
    scientific_type: 'xy_series',
    description: 'Synthetic golden response'
  });
  const derivedData = await post(request, '/data-records', {
    project_scope_id: projectId,
    data: { code: `DAT-DERIVED-${suffix}`, title: 'Cl₂ response rate' },
    scientific_type: 'scalar'
  });
  const representation = await post(request, `/data/${responseData.data.id}/representations`, {
    kind: 'table',
    name: 'Response table',
    format: 'tabular',
    inline_payload_jsonb: {
      rows: [
        { minute: 0, response: 0.05 },
        { minute: 5, response: 0.31 }
      ]
    }
  });
  const responseDataRevisions = await get(request, `/objects/${responseData.data.id}/revisions`);
  const derivedDataRevisions = await get(request, `/objects/${derivedData.data.id}/revisions`);
  await post(request, '/process-executions', {
    process_definition_id: definition.process_definition.id,
    project_scope_id: projectId,
    status: 'completed',
    object_bindings: [{ research_object_id: sample.id, direction: 'input', role: 'subject' }],
    data_bindings: [{ data_id: responseData.data.id, direction: 'output', role: 'response' }]
  });
  await post(request, '/process-executions', {
    process_definition_id: definition.process_definition.id,
    project_scope_id: projectId,
    status: 'completed',
    data_bindings: [
      { data_id: responseData.data.id, direction: 'input', role: 'baseline' },
      { data_id: derivedData.data.id, direction: 'output', role: 'rate' }
    ]
  });
  const view = await post(request, '/views', {
    project_scope_id: projectId,
    title: 'Golden response overview',
    description: 'Line view over response and rate',
    config: { chart: 'line', x: 'minute', y: 'response' },
    data_refs: [
      {
        data_id: responseData.data.id,
        data_revision_id: responseDataRevisions.at(-1).id,
        representation_ids: [representation.id]
      },
      {
        data_id: derivedData.data.id,
        data_revision_id: derivedDataRevisions.at(-1).id,
        representation_ids: []
      }
    ]
  });
  const claim = await post(request, '/claims', {
    project_scope_id: projectId,
    title: 'Golden sensor responds to Cl₂',
    statement: 'The golden sensor has a measurable response.',
    author_provenance: { kind: 'human', workflow: 'golden-browser-test' },
    primary_source: {
      kind: 'view',
      object_id: view.view.id,
      revision_id: view.current_revision_id
    },
    confidence: 'medium',
    evidence: [
      { evidence_kind: 'data', evidence_id: responseData.data.id, polarity: 'support' },
      { evidence_kind: 'view', evidence_id: view.view.id, polarity: 'support' }
    ]
  });
  const experimentA = await post(request, '/experiment-records', {
    project_scope_id: projectId,
    experiment: { code: `EXP-A-${suffix}`, title: 'Golden experiment A' },
    references: [
      { target_id: sample.id, role: 'sample' },
      { target_id: responseData.data.id, role: 'response' },
      { target_id: definition.process_definition.id, role: 'method' }
    ]
  });
  const experimentB = await post(request, '/experiment-records', {
    project_scope_id: projectId,
    experiment: { code: `EXP-B-${suffix}`, title: 'Golden experiment B' },
    references: [{ target_id: sample.id, role: 'shared sample' }]
  });

  await page.goto(`/dashboard/data/${responseData.data.id}?project=${projectId}`);
  await expect(page.getByText('Cl₂ response curve')).toBeVisible();
  await expect(page.getByText('Response table')).toBeVisible();
  await expect(page.getByText('Golden sensor strip')).toBeVisible();
  await expect(page.getByText(`Origin representation: ${representation.id}`)).toBeVisible();

  await page.goto(`/dashboard/views/${view.view.id}?project=${projectId}`);
  await expect(page.getByText('Data references')).toBeVisible();
  await expect(page.getByText('Golden response overview')).toBeVisible();
  await expect(page.getByText('"chart": "line"')).toBeVisible();
  await expect(page.getByText('Current revision')).toBeVisible();

  await page.goto(`/dashboard/claims/${claim.claim.id}?project=${projectId}`);
  await expect(
    page.getByText('The golden sensor has a measurable response.', { exact: true })
  ).toBeVisible();
  await expect(page.getByText('Confidence: medium')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Evidence' })).toBeVisible();

  await page.goto(`/dashboard/experiments/${experimentA.experiment.id}?project=${projectId}`);
  await expect(page.getByText('Golden experiment A')).toBeVisible();
  await expect(page.getByText('Cl₂ response curve')).toBeVisible();
  await expect(page.getByText('Cl₂ response measurement')).toBeVisible();

  const deleted = await request.delete(`${apiUrl}/objects/${experimentA.experiment.id}`);
  expect(deleted.ok(), await deleted.text()).toBeTruthy();
  const remaining = await get(request, `/experiments/${experimentB.experiment.id}/record`);
  expect(remaining.references.research_object[0].object.id).toBe(sample.id);
  expect((await get(request, `/data/${responseData.data.id}/record`)).data.id).toBe(
    responseData.data.id
  );
  await expectNoHorizontalOverflow(page);
  assertBrowserHealthy();
});
