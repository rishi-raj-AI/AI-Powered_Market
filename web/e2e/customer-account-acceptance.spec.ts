import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Page, type TestInfo} from '@playwright/test';
import path from 'node:path';
import {customer, installApiMocks} from './helpers';

const apiRoot = 'http://localhost:8000/api/v1';
const address = {id: 'address-niphad', village_id: 'village-niphad', label: 'Home', landmark: 'Niphad Bus Stand', house_details: 'House 10', directions: 'Blue gate', is_default: true};
const devices = [{id: 'device-android', platform: 'android', app_version: '1.0.0'}];

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
  const minimumTouchTarget = 44 - 0.01;
  for (const control of await page.locator('main button, main select, main a.btn').all()) {
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(minimumTouchTarget);
    expect(box!.width).toBeGreaterThanOrEqual(minimumTouchTarget);
  }
}

async function expectNoPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
}

async function mockProfile(page: Page) {
  await installApiMocks(page, customer);
}

async function mockAddresses(page: Page) {
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/addresses/me`, route => route.fulfill({json: [address]}));
}

async function mockDevices(page: Page) {
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/notifications/config`, route => route.fulfill({json: {enabled: true}}));
  await page.route(`${apiRoot}/notifications/devices`, route => route.fulfill({json: devices}));
}

const surfaces = [
  {name: 'profile', route: '/account', heading: 'Profile & business', ready: customer.phone, mock: mockProfile},
  {name: 'addresses', route: '/account/addresses', heading: 'Your address book', ready: 'Home • Default', mock: mockAddresses},
  {name: 'devices', route: '/account/devices', heading: 'Registered devices', ready: 'Configured', mock: mockDevices},
];

for (const width of [320, 390, 1280]) {
  for (const surface of surfaces) {
    test(`@a11y customer ${surface.name} controls remain usable at ${width}px`, async ({page}, testInfo) => {
      await page.setViewportSize({width, height: 844});
      await surface.mock(page);
      await page.goto(surface.route);
      await expect(page.getByRole('heading', {name: surface.heading, exact: true})).toBeVisible();
      await expect(page.getByText(surface.ready, {exact: true}).first()).toBeVisible();
      await expectNoSeriousAxeFindings(page);
      await expectUsableControls(page);
      await expectNoPageOverflow(page);
      await capture(page, testInfo, `customer-account-${surface.name}-${width}px`);
    });
  }
}

test('customer profile distinguishes initial loading, failure, retry, and confirmed account', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/users/me`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Account is temporarily unavailable'}});
    }
    return route.fulfill({json: customer});
  });
  await page.goto('/account');
  await expect(page.locator('main [role="status"]')).toContainText('Loading account…');
  await expect(page.getByText('Not linked')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Account is temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry account'}).click();
  await expect(page.getByRole('textbox', {name: 'Name', exact: true})).toHaveValue('Kiran');
  expect(reads).toBeGreaterThanOrEqual(2);
});

test('customer address book distinguishes initial loading, failure, retry, and confirmed empty state', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/addresses/me`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Addresses are temporarily unavailable'}});
    }
    return route.fulfill({json: []});
  });
  await page.goto('/account/addresses');
  await expect(page.locator('main [role="status"]')).toContainText('Loading saved addresses…');
  await expect(page.getByText('No saved addresses yet.')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Addresses are temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry addresses'}).click();
  await expect(page.getByText('No saved addresses yet.')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});

test('customer notification devices distinguish initial loading, failure, retry, and confirmed empty state', async ({page}) => {
  const pending = barrier();
  let configReads = 0;
  let allowSuccess = false;
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/notifications/config`, async route => {
    configReads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Device settings are temporarily unavailable'}});
    }
    return route.fulfill({json: {enabled: true}});
  });
  await page.route(`${apiRoot}/notifications/devices`, route => route.fulfill({json: []}));
  await page.goto('/account/devices');
  await expect(page.locator('main [role="status"]')).toContainText('Loading notification devices…');
  await expect(page.getByText('No active registered devices.')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Device settings are temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry devices'}).click();
  await expect(page.getByText('No active registered devices.')).toBeVisible();
  expect(configReads).toBeGreaterThanOrEqual(2);
});

test('customer address book retains a confirmed removal when its refresh fails', async ({page}) => {
  let failRefresh = false;
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/addresses/me`, route => {
    return failRefresh
      ? route.fulfill({status: 503, json: {detail: 'Addresses are temporarily unavailable'}})
      : route.fulfill({json: [address]});
  });
  await page.route(`${apiRoot}/addresses/me/${address.id}`, route => route.fulfill({status: 204}));
  await page.goto('/account/addresses');
  await expect(page.getByText('Home • Default')).toBeVisible();
  failRefresh = true;
  await page.getByRole('button', {name: 'Remove'}).click();
  await expect(page.locator('main [role="alert"]')).toContainText('Showing the last confirmed addresses.');
  await expect(page.getByText('Home • Default')).toHaveCount(0);
});

test('customer device list retains a confirmed removal when its refresh fails', async ({page}) => {
  let failRefresh = false;
  await installApiMocks(page, customer);
  await page.route(`${apiRoot}/notifications/config`, route => route.fulfill({json: {enabled: true}}));
  await page.route(`${apiRoot}/notifications/devices`, route => {
    return failRefresh
      ? route.fulfill({status: 503, json: {detail: 'Device settings are temporarily unavailable'}})
      : route.fulfill({json: devices});
  });
  await page.route(`${apiRoot}/notifications/devices/${devices[0].id}`, route => route.fulfill({status: 204}));
  await page.goto('/account/devices');
  await expect(page.getByText('android', {exact: true})).toBeVisible();
  failRefresh = true;
  await page.getByRole('button', {name: 'Unregister'}).click();
  await expect(page.locator('main [role="alert"]')).toContainText('Showing the last confirmed devices.');
  await expect(page.getByText('android', {exact: true})).toHaveCount(0);
});
