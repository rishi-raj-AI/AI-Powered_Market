import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Page, type TestInfo} from '@playwright/test';
import path from 'node:path';
import {installApiMocks, normalAdmin, superAdmin} from './helpers';

const apiRoot = 'http://localhost:8000/api/v1';
const failedDeliveriesPath = `${apiRoot}/admin/deliveries/failed`;
const prePickupFailure = {
  id: 'acceptance-pre-pickup', order_number: 'GO260925000001', status: 'failed',
  store_name: 'पिंपळगाव स्थानिक किराणा', customer_landmark: 'समुदाय भवन के पास, मुख्य चौक',
  picked_up_at: null, failure_reason: 'rider_unavailable',
};
const postPickupFailure = {
  id: 'acceptance-post-pickup', order_number: 'GO260925000002', status: 'failed',
  store_name: 'पिंपळगाव स्थानिक किराणा', customer_landmark: 'समुदाय भवन के पास, मुख्य चौक',
  picked_up_at: '2026-09-25T10:00:00Z', failure_reason: 'customer_unavailable',
  failure_notes: 'कॉल का उत्तर नहीं मिला',
};

function barrier() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return {promise, release};
}

async function capture(page: Page, testInfo: TestInfo, name: string) {
  const screenshot = process.env.GAONONE_VISUAL_OUTPUT_DIR
    ? path.join(process.env.GAONONE_VISUAL_OUTPUT_DIR, `${name}-${testInfo.project.name}.png`)
    : testInfo.outputPath(`${name}.png`);
  await page.screenshot({path: screenshot, fullPage: true});
  await testInfo.attach(name, {path: screenshot, contentType: 'image/png'});
}

async function expectUsableControls(page: Page) {
  for (const control of await page.locator('main button, main select').all()) {
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
  }
}

async function expectNoSeriousAxeFindings(page: Page) {
  const results = await new AxeBuilder({page}).include('main').withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.filter(item => ['serious', 'critical'].includes(item.impact || ''))).toEqual([]);
}

async function expectNoPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
}

for (const width of [320, 390, 1280]) {
  test(`@a11y elevated admin operations stay usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await installApiMocks(page, superAdmin);
    await page.route(failedDeliveriesPath, route => route.fulfill({json: [prePickupFailure, postPickupFailure]}));

    await page.goto('/admin');
    await expect(page.getByRole('heading', {name: 'Super Admin dashboard'})).toBeVisible();
    await expect(page.getByRole('button', {name: 'Make admin'}).first()).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `admin-dashboard-${width}px`);

    await page.goto('/admin/delivery-recovery');
    await expect(page.getByRole('button', {name: 'Review return to store'})).toBeVisible();
    await page.getByRole('button', {name: 'Review return to store'}).click();
    const confirmation = page.getByRole('region', {name: 'Return-to-store confirmation'});
    await expect(confirmation).toBeVisible();
    await expect(confirmation).toBeFocused();
    await expect(confirmation.getByText('This recovery cannot be undone here.')).toBeVisible();
    await expect(confirmation.getByRole('button', {name: 'Confirm return to store'})).toBeInViewport();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `admin-delivery-recovery-${width}px`);
    await confirmation.getByRole('button', {name: 'Cancel'}).click();
    await expect(page.getByRole('button', {name: 'Review return to store'})).toBeFocused();
  });
}

test('normal administrator retains pre-pickup recovery while financial return remains unavailable', async ({page}) => {
  await installApiMocks(page, normalAdmin);
  await page.route(failedDeliveriesPath, route => route.fulfill({json: [prePickupFailure, postPickupFailure]}));
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByRole('button', {name: 'Return to dispatch pool'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Review return to store'})).toHaveCount(0);
  await expect(page.getByText('Financial recovery requires elevated refund and settlement authority.')).toBeVisible();
});

test('delivery recovery distinguishes loading, queue failure, empty, and retry states', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  await installApiMocks(page, superAdmin);
  await page.route(failedDeliveriesPath, async route => {
    reads += 1;
    if (reads === 1) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Failed deliveries temporarily unavailable'}});
    }
    if (reads === 2) return route.fulfill({json: []});
    return route.fulfill({json: [prePickupFailure]});
  });
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByRole('status')).toContainText('Loading failed deliveries…');
  pending.release();
  await expect(page.locator('.notice[role="alert"]')).toContainText('Failed deliveries temporarily unavailable');
  await page.getByRole('button', {name: 'Retry queue'}).click();
  await expect(page.getByText('No failed deliveries require review.')).toBeVisible();
  await page.getByRole('button', {name: 'Refresh failed deliveries'}).click();
  await expect(page.getByRole('button', {name: 'Return to dispatch pool'})).toBeVisible();
  expect(reads).toBe(3);
});

test('delivery recovery fails closed for an account without recovery capability', async ({page}) => {
  let queueReads = 0;
  await installApiMocks(page, normalAdmin);
  await page.route(`${apiRoot}/users/me/capabilities`, route => route.fulfill({json: {is_super_admin: false, capabilities: []}}));
  page.on('request', request => {
    if (new URL(request.url()).pathname.endsWith('/admin/deliveries/failed')) queueReads += 1;
  });
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByText('Delivery recovery access is not available for this account.')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Refresh failed deliveries'})).toHaveCount(0);
  expect(queueReads).toBe(0);
});
