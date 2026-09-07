// Run from web. All API requests are mocked; no scientific records are written.
const { chromium } = require(require.resolve('playwright', { paths: [process.cwd()] }));
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const projectId = '11111111-1111-4111-8111-111111111111';
    const sampleId = '22222222-2222-4222-8222-222222222222';
    const object = (id, kind, title) => ({id, kind, code: title, title, status: 'active',
      project_scope_id: kind === 'project' ? null : projectId, tags: ['sample'], properties_jsonb: {},
      process_field_definitions: {}, content_document: [], created_at: '2026-09-06T00:00:00Z', updated_at: '2026-09-06T00:00:00Z'});
    let record = {record_sha256: 'a'.repeat(64), sample: object(sampleId, 'research_object', 'Audit Sample'),
      document: {schema_version: 1, blocks: []}, occurrences: [], data: [], editable: true, edit_blockers: []};
    const writes = [];
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route('**/api/v1/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      let body = [];
      if (url.pathname === `/api/v1/samples/${sampleId}/record`) {
        if (request.method() === 'PUT') {
          writes.push(request.postDataJSON());
          if (writes.length === 1) {
            await gate;
            record = {...record, record_sha256: 'b'.repeat(64), document: writes[0].document};
          } else {
            await route.fulfill({status: 412, contentType: 'application/json', body: JSON.stringify({error: {message: 'stale_record', code: 'stale_record'}})});
            return;
          }
        }
        body = record;
      } else if (url.pathname === '/api/v1/objects' && url.searchParams.get('kind') === 'project') {
        body = [object(projectId, 'project', 'Audit Project')];
      }
      await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await page.goto(`http://127.0.0.1:3000/dashboard/samples/${sampleId}?project=${projectId}`);
    const editor = page.locator('[data-testid="scientific-composer"] .bn-editor');
    await editor.waitFor();
    await editor.click();
    await page.keyboard.type('before save');
    await page.getByTestId('save-sample-record').click();
    await page.waitForFunction(() => document.querySelector('[data-testid="save-sample-record"]').disabled);
    await editor.click();
    await page.keyboard.type(' edited while saving');
    release();
    await page.getByTestId('save-sample-record').waitFor({state: 'visible'});
    await page.waitForFunction(() => !document.querySelector('[data-testid="save-sample-record"]').disabled);
    await page.getByTestId('save-sample-record').click();
    await page.getByRole('alert').waitFor();
    assert.equal(writes.length, 2);
    assert.equal(writes[1].base_record_sha256, 'a'.repeat(64));
    console.log(JSON.stringify({finding: 'save during editing retains stale base revision', firstBase: writes[0].base_record_sha256,
      responseBase: record.record_sha256, secondBase: writes[1].base_record_sha256, browserAlert: await page.getByRole('alert').textContent()}));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
