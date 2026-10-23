import {expect, test, type Page} from '@playwright/test';
import {installApiMocks, merchantUser} from './helpers';

const orderId = 'merchant-order-acceptance';
const baseOrder = {
  id: orderId, order_number: 'GO-MERCHANT-0001', user_id: 'customer-1', store_id: 'store-nearby',
  address_id: 'address-1', status: 'placed', payment_method: 'cod', payment_status: 'pending',
  subtotal: '250.00', delivery_fee: '37.35', total: '287.35',
  created_at: '2026-10-04T10:00:00Z', updated_at: '2026-10-04T10:00:00Z',
};
type Reply = {status?: number; json: unknown} | 'abort';
type Mutation = {path: string; payload: unknown};
const barrier = () => {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return {promise, release};
};

async function installMerchantOrders(page: Page, options: {
  order?: Partial<typeof baseOrder>;
  onRead?: () => Promise<Reply | undefined>;
  onMutation?: (mutation: Mutation) => Promise<Reply | undefined>;
} = {}) {
  await installApiMocks(page, merchantUser);
  const state = {order: {...baseOrder, ...options.order}, reads: 0, mutations: [] as Mutation[]};
  await page.route('http://localhost:8000/api/v1/merchant/orders**', async route => {
    const request = route.request();
    if (request.method() === 'GET') {
      state.reads += 1;
      const reply = await options.onRead?.();
      if (reply === 'abort') return route.abort('failed');
      return route.fulfill(reply ?? {json: [state.order]});
    }
    const mutation = {path: new URL(request.url()).pathname.replace('/api/v1', ''), payload: request.postDataJSON()};
    state.mutations.push(mutation);
    const reply = await options.onMutation?.(mutation);
    if (reply === 'abort') return route.abort('failed');
    if (reply) return route.fulfill(reply);
    const next = (mutation.payload as {status: string}).status;
    state.order = {...state.order, status: next, updated_at: '2026-10-04T10:01:00Z'};
    return route.fulfill({json: state.order});
  });
  return state;
}

const consoleScope = (page: Page) => page.locator('section').filter({has: page.getByRole('heading', {name: 'Order fulfilment'})});
const controls = (page: Page) => ({
  accept: consoleScope(page).getByRole('button', {name: 'Accept', exact: true}),
  reject: consoleScope(page).getByRole('button', {name: 'Reject', exact: true}),
  prepare: consoleScope(page).getByRole('button', {name: 'Start preparing', exact: true}),
  ready: consoleScope(page).getByRole('button', {name: 'Ready for rider', exact: true}),
});
const preparationControls = (page: Page) => ({
  accept: page.getByRole('button', {name: 'Accept order', exact: true}),
  prepare: page.getByRole('button', {name: 'Start preparing', exact: true}),
  ready: page.getByRole('button', {name: 'Mark ready', exact: true}),
  refresh: page.getByRole('button', {name: 'Refresh', exact: true}),
});

test('primary merchant console follows server order progression', async ({page}) => {
  const state = await installMerchantOrders(page);
  await page.goto('/merchant');
  await expect(controls(page).accept).toBeEnabled();
  await controls(page).accept.click();
  await expect(controls(page).prepare).toBeEnabled();
  await controls(page).prepare.click();
  await expect(controls(page).ready).toBeEnabled();
  await controls(page).ready.click();
  await expect(consoleScope(page).getByText('Waiting for rider')).toBeVisible();
  expect(state.mutations.map(item => item.payload)).toEqual([
    {status: 'accepted'}, {status: 'preparing'}, {status: 'ready'},
  ]);
});

test('primary merchant console sends only the server cancellation transition', async ({page}) => {
  const state = await installMerchantOrders(page);
  await page.goto('/merchant');
  await controls(page).reject.click();
  await expect(consoleScope(page).getByText('Cancelled', {exact: true})).toBeVisible();
  expect(state.mutations).toEqual([{path: `/merchant/orders/${orderId}/status`, payload: {status: 'cancelled'}}]);
});

test('unpaid UPI ready rejection stays server-authoritative', async ({page}) => {
  const state = await installMerchantOrders(page, {
    order: {status: 'preparing', payment_method: 'upi', payment_status: 'pending'},
    onMutation: async () => ({status: 409, json: {detail: 'Online payment must be confirmed before marking an order ready'}}),
  });
  await page.goto('/merchant');
  await controls(page).ready.click();
  await expect(page.getByText('Online payment must be confirmed before marking an order ready')).toBeVisible();
  await expect(controls(page).ready).toBeEnabled();
  expect(state.order.status).toBe('preparing');
  expect(state.mutations).toHaveLength(1);
});

test('synchronous forced duplicate acceptance issues one mutation', async ({page}) => {
  const pending = barrier();
  const state = await installMerchantOrders(page, {onMutation: async () => {
    await pending.promise;
    return undefined;
  }});
  await page.goto('/merchant');
  await page.evaluate(() => {
    const originalFetch = window.fetch.bind(window);
    let forced = false;
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);
      if (!forced && url.includes('/merchant/orders/') && init?.method === 'PATCH') {
        forced = true;
        const button = Array.from(document.querySelectorAll('button')).find(node => node.textContent?.trim() === 'Accept');
        button?.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
      }
      return originalFetch(input, init);
    };
  });
  try {
    await controls(page).accept.click();
    await expect(controls(page).accept).toBeDisabled();
    expect(state.mutations).toHaveLength(1);
  } finally {
    pending.release();
  }
  await expect(controls(page).prepare).toBeEnabled();
});

test('uncertain primary-console transition reconciles server state without replay', async ({page}) => {
  const heldRead = barrier();
  let mutated = false;
  const state = await installMerchantOrders(page, {
    onMutation: async () => {
      mutated = true;
      state.order = {...state.order, status: 'accepted'};
      return 'abort';
    },
    onRead: async () => {
      if (!mutated) return undefined;
      await heldRead.promise;
      return {json: [state.order]};
    },
  });
  await page.goto('/merchant');
  try {
    await controls(page).accept.click();
    await expect.poll(() => state.reads).toBeGreaterThan(1);
    await expect(controls(page).accept).toBeDisabled();
    expect(state.mutations).toHaveLength(1);
  } finally {
    heldRead.release();
  }
  await expect(controls(page).prepare).toBeEnabled();
  expect(state.mutations).toHaveLength(1);
});

test('primary console keeps actions locked after a failed reconciliation until explicit refresh', async ({page}) => {
  let mutated = false;
  let reconciliationReads = 0;
  const state = await installMerchantOrders(page, {
    onMutation: async () => {
      mutated = true;
      state.order = {...state.order, status: 'accepted'};
      return 'abort';
    },
    onRead: async () => {
      if (!mutated) return undefined;
      reconciliationReads += 1;
      return reconciliationReads === 1
        ? {status: 503, json: {detail: 'Orders are temporarily unavailable'}}
        : {json: [state.order]};
    },
  });
  await page.goto('/merchant');
  await controls(page).accept.click();
  await expect(page.getByText('Could not confirm this order status. Refresh before another action.')).toBeVisible();
  await expect(controls(page).accept).toBeDisabled();
  expect(state.mutations).toHaveLength(1);
  await page.getByRole('button', {name: 'Refresh', exact: true}).click();
  await expect(controls(page).prepare).toBeEnabled();
  expect(state.mutations).toHaveLength(1);
});

test('merchant preparation page has the same server progression contract', async ({page}) => {
  const state = await installMerchantOrders(page);
  await page.goto('/merchant/orders');
  await preparationControls(page).accept.click();
  await preparationControls(page).prepare.click();
  await preparationControls(page).ready.click();
  await expect(page.getByRole('heading', {name: 'Ready'})).toBeVisible();
  await expect(preparationControls(page).ready).toHaveCount(0);
  expect(state.mutations.map(item => item.payload)).toEqual([
    {status: 'accepted'}, {status: 'preparing'}, {status: 'ready'},
  ]);
});

test('merchant preparation page serializes duplicate acceptance and reconciles an aborted response', async ({page}) => {
  const release = barrier();
  let mutated = false;
  const state = await installMerchantOrders(page, {
    onMutation: async () => {
      mutated = true;
      state.order = {...state.order, status: 'accepted'};
      await release.promise;
      return 'abort';
    },
    onRead: async () => mutated ? {json: [state.order]} : undefined,
  });
  await page.goto('/merchant/orders');
  await page.evaluate(() => {
    const originalFetch = window.fetch.bind(window);
    let forced = false;
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);
      if (!forced && url.includes('/merchant/orders/') && init?.method === 'PATCH') {
        forced = true;
        Array.from(document.querySelectorAll('button')).find(node => node.textContent?.trim() === 'Accept order')
          ?.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
      }
      return originalFetch(input, init);
    };
  });
  try {
    await preparationControls(page).accept.click();
    await expect(preparationControls(page).accept).toBeDisabled();
    expect(state.mutations).toHaveLength(1);
  } finally {
    release.release();
  }
  await expect(preparationControls(page).prepare).toBeEnabled();
  expect(state.mutations).toHaveLength(1);
});

test('merchant preparation page keeps actions locked after failed reconciliation until refresh', async ({page}) => {
  let mutated = false;
  let reconciliationReads = 0;
  const state = await installMerchantOrders(page, {
    onMutation: async () => {
      mutated = true;
      state.order = {...state.order, status: 'accepted'};
      return 'abort';
    },
    onRead: async () => {
      if (!mutated) return undefined;
      reconciliationReads += 1;
      return reconciliationReads === 1
        ? {status: 503, json: {detail: 'Orders are temporarily unavailable'}}
        : {json: [state.order]};
    },
  });
  await page.goto('/merchant/orders');
  await preparationControls(page).accept.click();
  await expect(page.getByText('Could not confirm this order status. Refresh before another order action.')).toBeVisible();
  await expect(preparationControls(page).accept).toBeDisabled();
  expect(state.mutations).toHaveLength(1);
  await preparationControls(page).refresh.click();
  await expect(preparationControls(page).prepare).toBeEnabled();
  expect(state.mutations).toHaveLength(1);
});
