import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Page, type TestInfo} from '@playwright/test';
import path from 'node:path';
import {installApiMocks} from './helpers';

const apiRoot = 'http://localhost:8000/api/v1';
const cart = {id: 'cart-purchase', store_id: 'store-nearby', subtotal: '145.00', items: [{id: 'cart-item', store_product_id: 'listing-rice', quantity: 2, store_product: {id: 'listing-rice', store_id: 'store-nearby', product_id: 'product-rice', price: '72.50', stock_quantity: 8, is_available: true, product: {id: 'product-rice', category_id: 'category-rice', name: 'Kolam Rice', unit: '1 kg'}}}]};
const address = {id: 'address-niphad', village_id: 'village-niphad', label: 'Home', landmark: 'Niphad Main Road', latitude: 20.0778, longitude: 74.1118, is_default: true};
const quote = {store_id: cart.store_id, address_id: address.id, subtotal: cart.subtotal, delivery_fee: '37.50', total: '182.50', serviceable: true, inventory_valid: true, store_open: true, checkout_ready: true, blockers: []};

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
    // Firefox can report a 44 CSS px layout box as 43.999996 device pixels.
    expect(box!.height).toBeGreaterThanOrEqual(minimumTouchTarget);
    expect(box!.width).toBeGreaterThanOrEqual(minimumTouchTarget);
  }
}

async function expectNoPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
}

async function mockCart(page: Page, nextCart = cart) {
  await installApiMocks(page);
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: nextCart}));
}

async function mockCheckout(page: Page) {
  await installApiMocks(page);
  await page.route(`${apiRoot}/cart`, route => route.fulfill({json: cart}));
  await page.route(`${apiRoot}/addresses/me`, route => route.fulfill({json: [address]}));
  await page.route(`${apiRoot}/payments/config`, route => route.fulfill({json: {enabled: false, provider: 'razorpay', currency: 'INR'}}));
  await page.route(`${apiRoot}/cart/quote**`, route => route.fulfill({json: quote}));
}

for (const width of [320, 390, 1280]) {
  test(`@a11y customer cart purchase controls remain usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await mockCart(page);
    await page.goto('/cart');
    await expect(page.getByRole('heading', {name: 'Your cart', exact: true})).toBeVisible();
    await expect(page.getByText('Kolam Rice')).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `customer-cart-${width}px`);
  });

  test(`@a11y customer checkout purchase controls remain usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await mockCheckout(page);
    await page.goto('/checkout');
    await expect(page.getByRole('heading', {name: 'Checkout'})).toBeVisible();
    await expect(page.getByText('₹182.50')).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page, testInfo, `customer-checkout-${width}px`);
  });
}

test('customer cart distinguishes initial loading, failure, retry, and confirmed empty state', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/cart`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Cart is temporarily unavailable'}});
    }
    return route.fulfill({json: {...cart, items: [], subtotal: '0.00'}});
  });
  await page.goto('/cart');
  await expect(page.locator('main [role="status"]')).toContainText('Loading your cart…');
  await expect(page.getByText('Your cart is empty')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Cart is temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry cart'}).click();
  await expect(page.getByText('Your cart is empty')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});

test('customer checkout distinguishes initial loading, failure, retry, and confirmed quote', async ({page}) => {
  const pending = barrier();
  let reads = 0;
  let allowSuccess = false;
  await installApiMocks(page);
  await page.route(`${apiRoot}/cart`, async route => {
    reads += 1;
    if (!allowSuccess) {
      await pending.promise;
      return route.fulfill({status: 503, json: {detail: 'Checkout cart is temporarily unavailable'}});
    }
    return route.fulfill({json: cart});
  });
  await page.route(`${apiRoot}/addresses/me`, route => route.fulfill({json: [address]}));
  await page.route(`${apiRoot}/payments/config`, route => route.fulfill({json: {enabled: false, provider: 'razorpay', currency: 'INR'}}));
  await page.route(`${apiRoot}/cart/quote**`, route => route.fulfill({json: quote}));
  await page.goto('/checkout');
  await expect(page.locator('main [role="status"]')).toContainText('Loading checkout…');
  await expect(page.getByText('Add a delivery address to continue.')).toHaveCount(0);
  pending.release();
  await expect(page.locator('main [role="alert"]')).toContainText('Checkout cart is temporarily unavailable');
  allowSuccess = true;
  await page.getByRole('button', {name: 'Retry checkout'}).click();
  await expect(page.getByText('₹182.50')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Place order'})).toBeEnabled();
  expect(reads).toBeGreaterThanOrEqual(2);
});
