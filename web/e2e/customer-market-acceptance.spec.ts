import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Page, type TestInfo} from '@playwright/test';
import path from 'node:path';
import {installApiMocks} from './helpers';

const apiRoot = 'http://localhost:8000/api/v1';
const store = {id: 'store-nearby', merchant_id: 'merchant-approved', village_id: 'village-niphad', name: 'Niphad Daily Needs', slug: 'niphad-daily-needs', description: 'Everyday essentials near the bus stand.', landmark: 'Niphad Bus Stand', opens_at: '08:00:00', closes_at: '21:00:00', delivery_enabled: true, pickup_enabled: true, is_active: true, is_open_now: true};
const nearbyStore = {...store, distance_km: 0.8};
const product = {id: 'listing-rice', store_id: store.id, product_id: 'product-rice', price: '72.50', stock_quantity: 8, is_available: true, product: {id: 'product-rice', category_id: 'category-rice', name: 'Kolam Rice', brand: 'Gaon Fresh', unit: '1 kg', description: 'Everyday rice'}};
const cart = {id: 'cart-market', store_id: store.id, subtotal: '0.00', items: []};

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

async function mockMarketplace(page: Page, stores = [store]) {
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores`, route => route.fulfill({json: stores}));
}

async function mockStorefront(page: Page, products = [product]) {
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/${store.id}`, route => route.fulfill({json: store}));
  await page.route(`${apiRoot}/stores/${store.id}/products`, route => route.fulfill({json: products}));
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: cart}));
}

const surfaces = [
  {name: 'marketplace', route: '/market', heading: 'What’s available around you?', ready: store.name, mock: mockMarketplace},
  {name: 'storefront', route: `/market/${store.id}`, heading: store.name, ready: product.product.name, mock: mockStorefront},
];

for (const width of [320, 390, 1280]) {
  for (const surface of surfaces) {
    test(`@a11y customer ${surface.name} remains usable at ${width}px`, async ({page}, testInfo) => {
      await page.setViewportSize({width, height: 844});
      await surface.mock(page);
      await page.goto(surface.route);
      await expect(page.getByRole('heading', {name: surface.heading, exact: true})).toBeVisible();
      await expect(page.getByText(surface.ready, {exact: true}).first()).toBeVisible();
      await expectNoSeriousAxeFindings(page);
      await expectUsableControls(page);
      await expectNoPageOverflow(page);
      await capture(page, testInfo, `customer-market-${surface.name}-${width}px`);
    });
  }
}

for (const width of [320, 390, 1280]) {
  test(`@a11y customer nearby marketplace actions remain usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await installApiMocks(page);
    await page.route(`${apiRoot}/stores/nearby**`, route => route.fulfill({json: [nearbyStore]}));
    await page.goto('/market?lat=20.0778&lng=74.1118&location=Niphad%20Local&serviceable=1&service_area=Niphad%20Local');
    await expect(page.getByText(store.name, {exact: true}).first()).toBeVisible();
    await expect(page.getByRole('button', {name: 'Clear location filter'})).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `customer-market-nearby-${width}px`);
  });
}

test('customer marketplace distinguishes initial loading, failure, retry, and confirmed empty state', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Marketplace is temporarily unavailable'}});
    }
    return route.fulfill({json: []});
  });
  await page.goto('/market');
  await expect(page.locator('main [role="status"]')).toContainText('Loading marketplace availability…');
  await expect(page.getByText('No live availability found here yet')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Marketplace is temporarily unavailable');
  await expect(page.getByText('No live availability found here yet')).toHaveCount(0);
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry stores'}).click();
  await expect(page.getByText('No live availability found here yet')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});

test('customer marketplace retains confirmed stores when refresh fails', async ({page}) => {
  let failRefresh = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores`, route => failRefresh
    ? route.fulfill({status: 503, json: {detail: 'Marketplace refresh is temporarily unavailable'}})
    : route.fulfill({json: [store]}));
  await page.goto('/market');
  await expect(page.getByText(store.name, {exact: true}).first()).toBeVisible();
  failRefresh = true;
  await page.getByRole('button', {name: 'Refresh availability'}).click();
  await expect(page.locator('main [role="alert"]')).toContainText('Showing the last confirmed availability.');
  await expect(page.getByText(store.name, {exact: true}).first()).toBeVisible();
});

test('customer nearby discovery distinguishes pending, failure, retry, and a confirmed empty result', async ({page}) => {
  const pending = barrier();
  let searchStarted!: () => void;
  const started = new Promise<void>(resolve => { searchStarted = resolve; });
  let allowSuccess = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/nearby**`, route => route.fulfill({json: [nearbyStore]}));
  await page.route('**/api/v1/discovery/search**', async route => {
    if (!allowSuccess) {
      searchStarted();
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Nearby inventory is temporarily unavailable'}});
    }
    return route.fulfill({json: {query: 'Rice', latitude: 20.0778, longitude: 74.1118, radius_km: 20, stores: [], categories: [], products: []}});
  });
  await page.goto('/market?lat=20.0778&lng=74.1118&location=Niphad%20Local&serviceable=1&service_area=Niphad%20Local');
  await expect(page.getByText(store.name, {exact: true}).first()).toBeVisible();
  await page.getByLabel('Search marketplace availability').fill('Rice');
  await expect(page.getByRole('status')).toContainText('Searching nearby inventory…');
  await started;
  await expect(page.getByText('0 available products matched')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Nearby inventory is temporarily unavailable');
  await expect(page.getByText('0 available products matched')).toHaveCount(0);
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry nearby search'}).click();
  await expect(page.getByText('0 available products matched')).toBeVisible();
});

test('customer nearby discovery invalidates a previous same-query result before retrying it', async ({page}) => {
  const pending = barrier();
  let searchStarted!: () => void;
  const started = new Promise<void>(resolve => { searchStarted = resolve; });
  let reads = 0;
  let allowEmptyRetry = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/nearby**`, route => route.fulfill({json: [nearbyStore]}));
  await page.route('**/api/v1/discovery/search**', async route => {
    reads += 1;
    if (reads === 1) return route.fulfill({json: {query: 'Rice', latitude: 20.0778, longitude: 74.1118, radius_km: 20, stores: [{id: store.id, name: store.name, delivery_enabled: true, distance_km: 0.8, match_score: 1}], categories: [], products: [{listing_id: product.id, product_id: product.product_id, store_id: store.id, store_name: store.name, name: product.product.name, unit: product.product.unit, price: product.price, distance_km: 0.8, match_score: 1}]}});
    if (!allowEmptyRetry) {
      searchStarted();
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Nearby inventory is temporarily unavailable'}});
    }
    return route.fulfill({json: {query: 'Rice', latitude: 20.0778, longitude: 74.1118, radius_km: 20, stores: [], categories: [], products: []}});
  });
  await page.goto('/market?lat=20.0778&lng=74.1118&location=Niphad%20Local&serviceable=1&service_area=Niphad%20Local');
  await expect(page.getByText(store.name, {exact: true}).first()).toBeVisible();
  const input = page.getByLabel('Search marketplace availability');
  await input.fill('Rice');
  await expect(page.getByText('1 available product matched')).toBeVisible();
  await input.fill('');
  await input.fill('Rice');
  await expect(page.getByRole('status')).toContainText('Searching nearby inventory…');
  await started;
  await expect(page.getByText('0 available products matched')).toHaveCount(0);
  await expect(page.getByText('No live availability found here yet')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Nearby inventory is temporarily unavailable');
  await expect(page.getByText('0 available products matched')).toHaveCount(0);
  allowEmptyRetry = true;
  await page.getByRole('button', {name: 'Retry nearby search'}).click();
  await expect(page.getByText('0 available products matched')).toBeVisible();
  await expect(page.getByText('No live availability found here yet')).toBeVisible();
});

test('customer storefront distinguishes atomic initial loading, failure, retry, and confirmed empty catalogue', async ({page}) => {
  const pending = barrier();
  let productReads = 0;
  let allowSuccess = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/${store.id}`, route => route.fulfill({json: store}));
  await page.route(`${apiRoot}/stores/${store.id}/products`, async route => {
    productReads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Catalogue is temporarily unavailable'}});
    }
    return route.fulfill({json: []});
  });
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: cart}));
  await page.goto(`/market/${store.id}`);
  await expect(page.locator('main [role="status"]')).toContainText('Loading store catalogue…');
  await expect(page.getByText('No matching products')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Catalogue is temporarily unavailable');
  await expect(page.getByText('No matching products')).toHaveCount(0);
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry storefront'}).click();
  await expect(page.getByRole('heading', {name: store.name, exact: true})).toBeVisible();
  await expect(page.getByText('No matching products')).toBeVisible();
  expect(productReads).toBeGreaterThanOrEqual(2);
});

test('customer storefront retains confirmed catalogue when refresh fails', async ({page}) => {
  let failRefresh = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/${store.id}`, route => route.fulfill({json: store}));
  await page.route(`${apiRoot}/stores/${store.id}/products`, route => failRefresh
    ? route.fulfill({status: 503, json: {detail: 'Catalogue refresh is temporarily unavailable'}})
    : route.fulfill({json: [product]}));
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: cart}));
  await page.goto(`/market/${store.id}`);
  await expect(page.getByText(product.product.name, {exact: true})).toBeVisible();
  failRefresh = true;
  await page.getByRole('button', {name: 'Refresh storefront'}).click();
  await expect(page.locator('main [role="alert"]')).toContainText('Showing the last confirmed catalogue.');
  await expect(page.getByText(product.product.name, {exact: true})).toBeVisible();
});

test('expired storefront mutation clears the GaonOne session and preserves a safe return', async ({page}) => {
  await installApiMocks(page);
  await page.addInitScript(() => {
    const removeItem = Storage.prototype.removeItem;
    Storage.prototype.removeItem = function (key) {
      if (key === 'gaonone_token') sessionStorage.setItem('gaonone_e2e_token_cleared', 'true');
      return removeItem.call(this, key);
    };
  });
  await page.route(`${apiRoot}/stores/${store.id}`, route => route.fulfill({json: store}));
  await page.route(`${apiRoot}/stores/${store.id}/products`, route => route.fulfill({json: [product]}));
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: cart}));
  await page.route(`${apiRoot}/cart/items`, route => route.fulfill({status: 401, json: {detail: 'Not authenticated'}}));
  await page.goto(`/market/${store.id}`);
  await expect(page.getByText(product.product.name, {exact: true})).toBeVisible();
  await Promise.all([
    page.waitForURL(/\/login\?next=%2Fmarket%2Fstore-nearby$/),
    page.getByRole('button', {name: 'Add'}).click(),
  ]);
  expect(await page.evaluate(() => sessionStorage.getItem('gaonone_e2e_token_cleared'))).toBe('true');
  await expect(page.getByRole('button', {name: 'Continue with Google'})).toBeVisible();
});

test('customer storefront serializes a forced duplicate cart write and retains its authoritative badge', async ({page}) => {
  const initialCart = barrier();
  const mutation = barrier();
  let writes = 0;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/${store.id}`, route => route.fulfill({json: store}));
  await page.route(`${apiRoot}/stores/${store.id}/products`, route => route.fulfill({json: [product]}));
  await page.route(`${apiRoot}/cart`, async route => {
    await initialCart.promise;
    return route.fulfill({json: cart});
  });
  await page.route(`${apiRoot}/cart/items`, async route => {
    writes += 1;
    await mutation.promise;
    return route.fulfill({json: {...cart, items: [{id: 'cart-item-rice', store_product_id: product.id, quantity: 1, store_product: product}]}});
  });
  const cartRead = page.waitForRequest(`${apiRoot}/cart`);
  await page.goto(`/market/${store.id}`);
  await cartRead;
  await expect(page.getByText(product.product.name, {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'Add'}).evaluate(button => {
    button.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
    button.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  });
  await expect.poll(() => writes).toBe(1);
  await expect(page.locator('main')).toHaveAttribute('aria-busy', 'true');
  await expect(page.getByRole('button', {name: 'Add'})).toBeDisabled();
  mutation.release();
  await expect(page.getByRole('link', {name: 'Cart (1)'})).toBeVisible();
  initialCart.release();
  await expect(page.getByRole('link', {name: 'Cart (1)'})).toBeVisible();
});

test('customer storefront routes alternative choices through the same cart mutation guard', async ({page}) => {
  const mutation = barrier();
  const scarceProduct = {...product, stock_quantity: 2};
  let writes = 0;
  await installApiMocks(page);
  await page.route(`${apiRoot}/stores/${store.id}`, route => route.fulfill({json: store}));
  await page.route(`${apiRoot}/stores/${store.id}/products`, route => route.fulfill({json: [scarceProduct]}));
  await page.route(`${apiRoot}/store-products/${product.id}/substitutions`, route => route.fulfill({json: [{listing_id: 'listing-basmati', product_id: 'product-basmati', name: 'Basmati Rice', unit: '1 kg', price: '80.00', price_delta: '7.50', score: 0.9}]}));
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: cart}));
  await page.route(`${apiRoot}/cart/items`, async route => {
    writes += 1;
    await mutation.promise;
    return route.fulfill({json: {...cart, items: [{id: 'cart-item-rice', store_product_id: product.id, quantity: 1, store_product: scarceProduct}]}});
  });
  await page.goto(`/market/${store.id}`);
  await page.getByRole('button', {name: 'Alternatives'}).click();
  await expect(page.getByRole('button', {name: 'Choose'})).toBeVisible();
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const add = buttons.find(button => button.textContent?.trim() === 'Add');
    const choose = buttons.find(button => button.textContent?.trim() === 'Choose');
    if (!(add instanceof HTMLButtonElement) || !(choose instanceof HTMLButtonElement)) throw new Error('Storefront cart actions were unavailable');
    add.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
    choose.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  });
  await expect.poll(() => writes).toBe(1);
  await expect(page.locator('main')).toHaveAttribute('aria-busy', 'true');
  await expect(page.getByRole('button', {name: 'Add'})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Choose'})).toBeDisabled();
  mutation.release();
  await expect(page.getByRole('link', {name: 'Cart (1)'})).toBeVisible();
});
