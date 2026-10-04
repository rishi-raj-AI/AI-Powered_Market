import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Page} from '@playwright/test';
import path from 'node:path';
import {installApiMocks, type MockUser} from './helpers';

const rider: MockUser = {
  id: 'acceptance-rider', phone: '+919000000050', full_name: 'Test Rider',
  role: 'delivery', is_active: true, is_verified: true,
  created_at: '2026-10-04T00:00:00Z',
};
const deliveryId = 'delivery-acceptance';
const deliveryPath = `/delivery/${deliveryId}`;
const task = {
  id: deliveryId, order_id: 'order-acceptance', order_number: 'GO-TEST-0001',
  status: 'picked_up', payment_method: 'cod', payment_status: 'pending',
  total: '287.35', store_name: 'Test Village Store', customer_landmark: 'Test community hall',
};
type Reply = {status?: number; json: unknown};
type Mutation = {path: string; method: string; payload: unknown};
type HarnessOptions = {
  task?: Partial<typeof task>;
  verified?: boolean;
  collected?: boolean;
  onRead?: (count: number) => Promise<Reply | undefined>;
  onMutation?: (mutation: Mutation) => Promise<Reply | 'abort' | undefined>;
};

function barrier() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return {promise, release};
}

async function installHarness(page: Page, options: HarnessOptions = {}) {
  await installApiMocks(page, rider);
  await page.addInitScript(() => {
    const testWindow = window as typeof window & {__deliveryMutationFetches: string[]};
    testWindow.__deliveryMutationFetches = [];
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);
      const method = init?.method || (input instanceof Request ? input.method : 'GET');
      if (url.includes('/api/v1/delivery/') && method !== 'GET') {
        testWindow.__deliveryMutationFetches.push(`${method} ${new URL(url).pathname}`);
      }
      return originalFetch(input, init);
    };
  });
  const state = {
    task: {...task, ...options.task}, reads: 0, mutations: [] as Mutation[],
    verified: options.verified ?? false, collected: options.collected ?? false,
  };
  await page.route('http://localhost:8000/api/v1/delivery/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1', '');
    if (path === '/delivery/tasks/me' && request.method() === 'GET') {
      state.reads += 1;
      const override = await options.onRead?.(state.reads);
      return route.fulfill(override ?? {json: [state.task]});
    }
    const mutation = {path, method: request.method(), payload: request.postData() ? request.postDataJSON() : null};
    state.mutations.push(mutation);
    const override = await options.onMutation?.(mutation);
    if (override === 'abort') return route.abort('failed');
    if (override) return route.fulfill(override);
    if (path === `${deliveryPath}/status` && mutation.method === 'PATCH') {
      if (JSON.stringify(mutation.payload) !== JSON.stringify({status: 'picked_up'})) {
        return route.fulfill({status: 422, json: {detail: 'Terminal status changes require completion'}});
      }
      state.task.status = 'picked_up';
      return route.fulfill({json: state.task});
    }
    if (path === `${deliveryPath}/proof/challenge` && mutation.method === 'POST') {
      return route.fulfill({json: {delivery_id: deliveryId, expires_at: '2026-10-04T12:15:00Z'}});
    }
    if (path === `${deliveryPath}/proof` && mutation.method === 'POST') {
      if (JSON.stringify(mutation.payload) !== JSON.stringify({otp: '123456'})) {
        return route.fulfill({status: 422, json: {detail: 'Invalid delivery verification code'}});
      }
      state.verified = true;
      return route.fulfill({json: {id: 'proof-acceptance', delivery_id: deliveryId, verified_at: '2026-10-04T12:00:00Z'}});
    }
    if (path === `${deliveryPath}/cod-collection` && mutation.method === 'POST') {
      if (JSON.stringify(mutation.payload) !== JSON.stringify({amount: state.task.total})) {
        return route.fulfill({status: 422, json: {detail: 'Collected COD amount must match the order total'}});
      }
      state.collected = true;
      return route.fulfill({json: {id: 'collection-acceptance', amount: state.task.total}});
    }
    if (path === `${deliveryPath}/complete` && mutation.method === 'POST') {
      if (!state.verified || (state.task.payment_method === 'cod' && !state.collected)) {
        return route.fulfill({status: 409, json: {detail: 'Verified proof and recorded cash collection are required'}});
      }
      state.task.status = 'delivered';
      state.task.payment_status = 'paid';
      return route.fulfill({json: state.task});
    }
    return route.fulfill({status: 404, json: {detail: `Unmocked delivery request ${mutation.method} ${path}`}});
  });
  return state;
}

async function openCompletion(page: Page) {
  await page.goto('/delivery/complete');
  await expect(page.getByText(task.order_number, {exact: true})).toBeVisible();
}

function actions(page: Page) {
  return {
    send: page.getByRole('button', {name: 'Send customer OTP', exact: true}),
    verify: page.getByRole('button', {name: 'Verify proof', exact: true}),
    collect: page.getByRole('button', {name: /^Record COD /}),
    complete: page.getByRole('button', {name: 'Complete delivery', exact: true}),
    refresh: page.getByRole('button', {name: 'Refresh', exact: true}),
  };
}

async function fetches(page: Page) {
  return page.evaluate(() => (window as typeof window & {__deliveryMutationFetches: string[]}).__deliveryMutationFetches);
}

async function forceDisabledActions(page: Page) {
  // Native/React disabled handling would suppress a dispatched click before
  // the application handler ran. Invoke the mounted callbacks to prove the
  // synchronous application guard also protects delayed/forced activation.
  return page.evaluate(() => {
    let invoked = 0;
    for (const button of document.querySelectorAll('button')) {
      if (!/^(Send customer OTP|Verify proof|Record COD |Complete delivery)/.test(button.textContent?.trim() || '')) continue;
      const propsKey = Object.keys(button).find(key => key.startsWith('__reactProps$'));
      if (!propsKey) throw new Error('No mounted React action callback');
      const props = (button as unknown as Record<string, {onClick?: () => unknown}>)[propsKey];
      if (!props.onClick) throw new Error('Delivery action is missing its callback');
      props.onClick();
      invoked += 1;
    }
    return invoked;
  });
}

test('COD completion preserves the server total and proof collection sequence', async ({page}) => {
  const state = await installHarness(page, {task: {status: 'assigned'}});
  await openCompletion(page);
  await page.getByRole('button', {name: 'Confirm pickup'}).click();
  await expect(actions(page).send).toBeEnabled();
  await actions(page).send.click();
  await expect(actions(page).send).toBeEnabled();
  await page.getByPlaceholder('6-digit customer OTP').fill('123456');
  await actions(page).verify.click();
  await expect(actions(page).verify).toBeEnabled();
  await actions(page).collect.click();
  await expect(actions(page).collect).toBeEnabled();
  await actions(page).complete.click();
  await expect(page.getByText(task.order_number, {exact: true})).toHaveCount(0);
  expect(state.mutations).toEqual([
    {method: 'PATCH', path: `${deliveryPath}/status`, payload: {status: 'picked_up'}},
    {method: 'POST', path: `${deliveryPath}/proof/challenge`, payload: null},
    {method: 'POST', path: `${deliveryPath}/proof`, payload: {otp: '123456'}},
    {method: 'POST', path: `${deliveryPath}/cod-collection`, payload: {amount: '287.35'}},
    {method: 'POST', path: `${deliveryPath}/complete`, payload: null},
  ]);
  expect(state.task.status).toBe('delivered');
});

test('paid UPI completion does not offer or issue cash collection', async ({page}) => {
  const state = await installHarness(page, {task: {payment_method: 'upi', payment_status: 'paid'}});
  await openCompletion(page);
  await expect(actions(page).collect).toHaveCount(0);
  await actions(page).send.click();
  await expect(actions(page).send).toBeEnabled();
  await page.getByPlaceholder('6-digit customer OTP').fill('123456');
  await actions(page).verify.click();
  await expect(actions(page).verify).toBeEnabled();
  await actions(page).complete.click();
  await expect(page.getByText(task.order_number, {exact: true})).toHaveCount(0);
  expect(state.mutations.map(item => item.path)).toEqual([
    `${deliveryPath}/proof/challenge`, `${deliveryPath}/proof`, `${deliveryPath}/complete`,
  ]);
});

for (const failure of [
  {action: 'challenge', status: 429, detail: 'Wait before requesting another delivery code.'},
  {action: 'verify', status: 429, detail: 'Delivery code verification is locked. Contact support.'},
  {action: 'verify', status: 503, detail: 'Delivery code service is temporarily unavailable.'},
] as const) {
  test(`${failure.action} ${failure.status} remains an error without retry or completion`, async ({page}) => {
    const path = `${deliveryPath}/proof${failure.action === 'challenge' ? '/challenge' : ''}`;
    const state = await installHarness(page, {
      onMutation: async mutation => mutation.path === path
        ? {status: failure.status, json: {detail: failure.detail}} : undefined,
    });
    await openCompletion(page);
    if (failure.action === 'verify') await page.getByPlaceholder('6-digit customer OTP').fill('123456');
    await (failure.action === 'challenge' ? actions(page).send : actions(page).verify).click();
    await expect(page.getByText(failure.detail, {exact: true})).toBeVisible();
    await expect(page.getByText(task.order_number, {exact: true})).toBeVisible();
    expect(state.verified).toBe(false);
    expect(state.collected).toBe(false);
    expect(state.task.status).toBe('picked_up');
    expect(state.mutations).toHaveLength(1);
    expect(await fetches(page)).toEqual([`POST /api/v1${path}`]);
    await expect(page.getByText('Proof of delivery verified.', {exact: true})).toHaveCount(0);
  });
}

test('a synchronous duplicate challenge cannot issue a second request', async ({page}) => {
  const pending = barrier();
  const state = await installHarness(page, {
    onMutation: async mutation => {
      if (mutation.path === `${deliveryPath}/proof/challenge`) await pending.promise;
      return undefined;
    },
  });
  await openCompletion(page);
  await page.evaluate(() => {
    let forced = false;
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);
      if (url.endsWith('/proof/challenge') && !forced) {
        forced = true;
        const button = Array.from(document.querySelectorAll('button')).find(candidate => candidate.textContent?.trim() === 'Send customer OTP');
        if (!button) throw new Error('No challenge action for synchronous duplicate');
        button.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
      }
      return originalFetch(input, init);
    };
  });
  try {
    await actions(page).send.click();
    await expect(actions(page).send).toBeDisabled();
    expect(await fetches(page)).toEqual([`POST /api/v1${deliveryPath}/proof/challenge`]);
    expect(await forceDisabledActions(page)).toBe(4);
    expect(await fetches(page)).toHaveLength(1);
  } finally {
    pending.release();
  }
  await expect(actions(page).send).toBeEnabled();
  expect(state.mutations).toHaveLength(1);
});

for (const response of ['503', 'network abort'] as const) {
test(`a lost completion response (${response}) reconciles terminal state before any further mutation`, async ({page}) => {
  const reconcile = barrier();
  let completionAttempted = false;
  let reconciliationReads = 0;
  const state = await installHarness(page, {
    verified: true, collected: true,
    onMutation: async mutation => {
      if (mutation.path !== `${deliveryPath}/complete`) return undefined;
      completionAttempted = true;
      if (response === 'network abort') return 'abort';
      return {status: 503, json: {detail: 'Completion response was interrupted'}};
    },
    onRead: async () => {
      if (!completionAttempted) return undefined;
      reconciliationReads += 1;
      await reconcile.promise;
      return {json: [{...task, status: 'delivered', payment_status: 'paid'}]};
    },
  });
  await openCompletion(page);
  await page.getByPlaceholder('6-digit customer OTP').fill('123456');
  try {
    await actions(page).complete.click();
    await expect.poll(() => reconciliationReads).toBe(1);
    for (const control of [actions(page).send, actions(page).verify, actions(page).collect, actions(page).complete]) {
      await expect(control).toBeDisabled();
    }
    expect(await forceDisabledActions(page)).toBe(4);
    expect(await fetches(page)).toEqual([`POST /api/v1${deliveryPath}/complete`]);
  } finally {
    reconcile.release();
  }
  await expect(page.getByText(task.order_number, {exact: true})).toHaveCount(0);
  await expect(actions(page).complete).toHaveCount(0);
  expect(state.mutations).toHaveLength(1);
  expect(reconciliationReads).toBe(1);
});
}

test('failed completion reconciliation keeps mutations blocked until successful explicit refresh', async ({page}) => {
  const refresh = barrier();
  let completionAttempted = false;
  let reconciliationReads = 0;
  const state = await installHarness(page, {
    verified: true, collected: true,
    onMutation: async mutation => {
      if (mutation.path !== `${deliveryPath}/complete`) return undefined;
      completionAttempted = true;
      return {status: 503, json: {detail: 'Completion response was interrupted'}};
    },
    onRead: async () => {
      if (!completionAttempted) return undefined;
      reconciliationReads += 1;
      if (reconciliationReads === 1) return {status: 503, json: {detail: 'Task refresh temporarily unavailable'}};
      await refresh.promise;
      return undefined;
    },
  });
  await openCompletion(page);
  await page.getByPlaceholder('6-digit customer OTP').fill('123456');
  await actions(page).complete.click();
  await expect.poll(() => reconciliationReads).toBe(1);
  await expect(actions(page).refresh).toBeEnabled();
  for (const control of [actions(page).send, actions(page).verify, actions(page).collect, actions(page).complete]) {
    await expect(control).toBeDisabled();
  }
  expect(await forceDisabledActions(page)).toBe(4);
  expect(await fetches(page)).toHaveLength(1);
  try {
    await actions(page).refresh.click();
    await expect.poll(() => reconciliationReads).toBe(2);
    expect(await forceDisabledActions(page)).toBe(4);
    expect(await fetches(page)).toHaveLength(1);
  } finally {
    refresh.release();
  }
  await expect(actions(page).send).toBeEnabled();
  await expect(actions(page).complete).toBeEnabled();
  await actions(page).send.click();
  await expect(actions(page).send).toBeEnabled();
  expect(state.mutations.map(item => item.path)).toEqual([
    `${deliveryPath}/complete`, `${deliveryPath}/proof/challenge`,
  ]);
});

for (const width of [320, 390, 1280]) {
  test(`@a11y delivery completion stays usable at ${width}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    await installHarness(page, {task: {
      store_name: 'चाचणी गावातील स्थानिक किराणा दुकान',
      customer_landmark: 'समुदाय भवन के पास, मुख्य चौक से मंदिर की ओर जाने वाली गली',
    }});
    await openCompletion(page);
    await expect(actions(page).send).toBeEnabled();
    const results = await new AxeBuilder({page}).include('main').withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    const screenshot = process.env.GAONONE_VISUAL_OUTPUT_DIR
      ? path.join(process.env.GAONONE_VISUAL_OUTPUT_DIR, `delivery-completion-${width}px-${testInfo.project.name}.png`)
      : testInfo.outputPath(`delivery-completion-${width}px.png`);
    await page.screenshot({path: screenshot, fullPage: true});
    await testInfo.attach(`delivery-completion-${width}px`, {path: screenshot, contentType: 'image/png'});
    await expect(page.getByLabel(/customer handoff code/i)).toBeVisible();
    for (const control of await page.locator('main button, main input').all()) {
      const box = (await control.boundingBox())!;
      expect(box.height).toBeGreaterThanOrEqual(44);
      expect(box.width).toBeGreaterThanOrEqual(44);
    }
    expect(results.violations.filter(item => ['serious', 'critical'].includes(item.impact || ''))).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
  });
}

test('loading and failed task reads are not presented as an empty assignment', async ({page}) => {
  const pending = barrier();
  let unavailable = true;
  const state = await installHarness(page, {
    onRead: async () => {
      await pending.promise;
      return unavailable ? {status: 503, json: {detail: 'Delivery tasks temporarily unavailable'}} : {json: []};
    },
  });
  try {
    await page.goto('/delivery/complete');
    await expect.poll(() => state.reads).toBeGreaterThan(0);
    await expect(page.getByRole('status')).toContainText('Loading delivery tasks');
    await expect(page.getByText('No active delivery to complete')).toHaveCount(0);
    await expect(actions(page).refresh).toBeDisabled();
  } finally {
    pending.release();
  }
  await expect(page.locator('main').getByRole('alert')).toContainText('Delivery tasks temporarily unavailable');
  await expect(page.getByText('No active delivery to complete')).toHaveCount(0);
  unavailable = false;
  await actions(page).refresh.click();
  await expect(page.getByRole('heading', {name: 'No active delivery to complete'})).toBeVisible();
  await expect(page.locator('main').getByRole('alert')).toHaveCount(0);
  expect(state.mutations).toHaveLength(0);
});

test('a definitive completion rejection stays a server error without replay', async ({page}) => {
  const state = await installHarness(page);
  await openCompletion(page);
  await actions(page).complete.click();
  await expect(page.locator('main').getByRole('alert')).toHaveText('Verified proof and recorded cash collection are required');
  await expect(actions(page).complete).toBeEnabled();
  await expect(page.getByText(task.order_number, {exact: true})).toBeVisible();
  expect(state.task.status).toBe('picked_up');
  expect(state.mutations).toEqual([{method: 'POST', path: `${deliveryPath}/complete`, payload: null}]);
});

test('acknowledged completion with failed task refresh stays locked without replay', async ({page}) => {
  let acknowledged = false;
  let reconciliationReads = 0;
  const state = await installHarness(page, {
    onMutation: async mutation => {
      if (mutation.path !== `${deliveryPath}/complete`) return undefined;
      acknowledged = true;
      return {json: {...task, status: 'delivered', payment_status: 'paid'}};
    },
    onRead: async () => {
      if (!acknowledged) return undefined;
      reconciliationReads += 1;
      return reconciliationReads === 1
        ? {status: 503, json: {detail: 'Task refresh temporarily unavailable'}}
        : {json: [{...task, status: 'delivered', payment_status: 'paid'}]};
    },
  });
  await openCompletion(page);
  await actions(page).complete.click();
  await expect(page.locator('main').getByRole('status')).toContainText('The action was recorded');
  await expect(actions(page).complete).toBeDisabled();
  expect(await forceDisabledActions(page)).toBe(4);
  expect(await fetches(page)).toHaveLength(1);
  await actions(page).refresh.click();
  await expect(actions(page).complete).toHaveCount(0);
  expect(state.mutations).toHaveLength(1);
  expect(reconciliationReads).toBe(2);
});
