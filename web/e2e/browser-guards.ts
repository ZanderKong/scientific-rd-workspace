import { expect, type Page, type TestInfo } from '@playwright/test';

export function installBrowserGuards(page: Page, testInfo: TestInfo) {
  const failures: string[] = [];
  page.on('pageerror', (error) => failures.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') failures.push(`console: ${message.text()}`);
  });
  page.on('requestfailed', (request) => {
    const errorText = request.failure()?.errorText;
    // Next aborts superseded RSC prefetches during deliberate route changes.
    if (errorText !== 'net::ERR_ABORTED') {
      failures.push(`requestfailed: ${request.method()} ${request.url()} ${errorText}`);
    }
  });
  page.on('response', (response) => {
    if (response.status() >= 500) failures.push(`http-${response.status()}: ${response.url()}`);
  });
  testInfo.attach('browser-guard-events', {
    body: Buffer.from('Browser guards are active; failures are asserted after the workflow.'),
    contentType: 'text/plain'
  });
  return () => expect(failures, failures.join('\n')).toEqual([]);
}

export async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBeTruthy();
}
