import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Page, type TestInfo} from '@playwright/test';
import path from 'node:path';
import {installApiMocks, normalAdmin} from './helpers';

const apiRoot = 'http://localhost:8000/api/v1';
const overview = {users: 7, villages: 1, active_stores: 1, merchants: {pending: 1, approved: 1, suspended: 0}, orders: {total: 2, by_status: {ready: 1, cancelled: 1}}, operations: {low_stock_listings: 0, ready_unassigned_deliveries: 1, active_delivery_partners: 2}, paid_gmv: null, gross_order_value: null};
const failedDelivery = {id: 'operations-failed', order_id: 'order-failed', status: 'failed'};
const refundedOrder = {id: 'operations-refund', order_number: 'GO260925000001', status: 'cancelled', payment_status: 'refunded'};
const performance = {window_days: 30, total_records: 3, delivered: 2, failed: 1, active: 0, median_assignment_to_pickup_seconds: 600, median_pickup_to_delivery_seconds: 1200, basis: 'recorded_delivery_timestamps'};
const noPerformance = {...performance, total_records: 0, delivered: 0, failed: 0, active: 0, median_assignment_to_pickup_seconds: null, median_pickup_to_delivery_seconds: null};

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

async function expectNoSeriousAxeFindings(page: Page) {
  const results = await new AxeBuilder({page}).include('main').withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.filter(item => ['serious', 'critical'].includes(item.impact || ''))).toEqual([]);
}

async function expectUsableControls(page: Page) {
  for (const control of await page.locator('main button, main select').all()) {
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
  }
}

async function expectNoPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
}

async function mockOperations(page: Page) {
  await installApiMocks(page, normalAdmin);
  await page.route(`${apiRoot}/merchant/orders`, route => route.fulfill({json: [refundedOrder]}));
  await page.route(`${apiRoot}/delivery/me`, route => route.fulfill({json: [failedDelivery]}));
  await page.route(`${apiRoot}/admin/overview`, route => route.fulfill({json: overview}));
}

async function mockPerformance(page: Page, data = performance) {
  await installApiMocks(page, normalAdmin);
  await page.route(`${apiRoot}/admin/delivery-performance`, route => route.fulfill({json: data}));
}

for (const width of [320, 390, 1280]) {
  test(`@a11y admin operations observability remains usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await mockOperations(page);
    await page.goto('/admin/operations');
    await expect(page.getByRole('heading', {name: 'Operations & exceptions'})).toBeVisible();
    await expect(page.getByText('GO260925000001')).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `admin-operations-${width}px`);
  });

  test(`@a11y delivery performance remains usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await mockPerformance(page);
    await page.goto('/admin/delivery-performance');
    await expect(page.getByRole('heading', {name: 'Delivery performance'})).toBeVisible();
    await expect(page.getByText('10 min median')).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `admin-delivery-performance-${width}px`);
  });
}

test('admin operations distinguishes initial loading, failure, retry, and confirmed empty state', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page, normalAdmin);
  await page.route(`${apiRoot}/merchant/orders`, route => route.fulfill({json: []}));
  await page.route(`${apiRoot}/delivery/me`, route => route.fulfill({json: []}));
  await page.route(`${apiRoot}/admin/overview`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Operations overview temporarily unavailable'}});
    }
    return route.fulfill({json: overview});
  });
  await page.goto('/admin/operations');
  await expect(page.locator('main [role="status"]')).toContainText('Loading operations…');
  await expect(page.getByText('No failed deliveries.')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Operations overview temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry operations'}).click();
  await expect(page.getByText('No failed deliveries.')).toBeVisible();
  await expect(page.getByText('No cancellation or refund exceptions.')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});

test('delivery performance distinguishes initial loading, failure, retry, and no-data state', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page, normalAdmin);
  await page.route(`${apiRoot}/admin/delivery-performance`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Delivery performance temporarily unavailable'}});
    }
    return route.fulfill({json: noPerformance});
  });
  await page.goto('/admin/delivery-performance');
  await expect(page.locator('main [role="status"]')).toContainText('Loading delivery performance…');
  await expect(page.getByText('No delivery records are available for this window.')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Delivery performance temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry delivery performance'}).click();
  await expect(page.getByText('No delivery records are available for this window.')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});
