import AxeBuilder from '@axe-core/playwright';
import {expect,test} from '@playwright/test';
import {activeRider,customer,installApiMocks,merchantUser,normalAdmin,superAdmin} from './helpers';

test('rider reports an assigned delivery incident through the guarded endpoint',async({page})=>{
  await installApiMocks(page,activeRider);
  await page.route('http://localhost:8000/api/v1/delivery/delivery-assigned/fail',route=>route.fulfill({json:{id:'delivery-assigned',status:'failed',...route.request().postDataJSON()}}));
  await page.goto('/delivery/incidents');
  await page.getByRole('combobox').first().selectOption('delivery-assigned');
  await page.getByRole('button',{name:'Report incident'}).click();
  await expect(page.getByText('Delivery incident recorded for operations review.')).toBeVisible();
});

test('normal admin can reassign a pre-pickup failure but cannot start financial return',async({page})=>{
  let resolutions=0;
  await installApiMocks(page,normalAdmin);
  await page.route('http://localhost:8000/api/v1/admin/deliveries/failed',route=>route.fulfill({json:[{id:'delivery-pre-pickup',order_number:'GO260903000001',status:'failed',store_name:'Niphad Daily Needs',customer_landmark:'Main Chowk',picked_up_at:null,failure_reason:'rider_unavailable'},{id:'delivery-post-pickup',order_number:'GO260903000002',status:'failed',store_name:'Niphad Daily Needs',customer_landmark:'Main Chowk',picked_up_at:'2026-09-03T10:00:00Z',failure_reason:'customer_unavailable'}]}));
  await page.route('http://localhost:8000/api/v1/admin/deliveries/delivery-pre-pickup/resolve-failure',route=>{resolutions+=1;expect(route.request().postDataJSON()).toEqual({resolution:'reassign'});return route.fulfill({json:{delivery_id:'delivery-pre-pickup',order_id:'order-pre-pickup',resolution:'reassign',order_status:'ready',delivery_status:'unassigned',refund_requested:false,settlement_voided:false}})});
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByRole('button',{name:'Return to dispatch pool'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Review return to store'})).toHaveCount(0);
  await expect(page.getByText('Financial recovery requires elevated refund and settlement authority.')).toBeVisible();
  await page.getByRole('button',{name:'Return to dispatch pool'}).click();
  await expect(page.getByText('GO260903000001 returned to the dispatch pool.')).toBeVisible();
  expect(resolutions).toBe(1);
});

test('financial recovery waits for confirmation and renders the authoritative outcome',async({page})=>{
  let resolutions=0;
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/admin/deliveries/failed',route=>route.fulfill({json:[{id:'delivery-failed',order_number:'GO260903000001',status:'failed',store_name:'Niphad Daily Needs',customer_landmark:'Main Chowk',picked_up_at:'2026-09-03T10:00:00Z',failure_reason:'customer_unavailable'}]}));
  await page.route('http://localhost:8000/api/v1/admin/deliveries/delivery-failed/resolve-failure',route=>{resolutions+=1;expect(route.request().postDataJSON()).toEqual({resolution:'return_to_store'});return route.fulfill({json:{delivery_id:'delivery-failed',order_id:'order-failed',resolution:'return_to_store',order_status:'returned',delivery_status:'failed',refund_requested:true,settlement_voided:true}})});
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByRole('button',{name:'Review return to store'})).toBeVisible();
  expect(resolutions).toBe(0);
  await page.getByRole('button',{name:'Review return to store'}).click();
  await expect(page.getByRole('region',{name:'Return-to-store confirmation'})).toBeVisible();
  await expect(page.getByText('The backend will return this order, restore stock once, void settlement, and request a refund when appropriate. This recovery cannot be undone here.')).toBeVisible();
  expect(resolutions).toBe(0);
  await page.getByRole('button',{name:'Cancel'}).click();
  await expect(page.getByRole('region',{name:'Return-to-store confirmation'})).toHaveCount(0);
  expect(resolutions).toBe(0);
  await page.getByRole('button',{name:'Review return to store'}).click();
  await page.getByRole('button',{name:'Confirm return to store'}).click();
  await expect(page.getByText('GO260903000001 returned to the store. Settlement was voided. A refund was requested.')).toBeVisible();
  expect(resolutions).toBe(1);
});

test('@a11y delivery recovery confirmation has no serious accessibility violations',async({page})=>{
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/admin/deliveries/failed',route=>route.fulfill({json:[{id:'delivery-failed',order_number:'GO260903000001',status:'failed',store_name:'Niphad Daily Needs',customer_landmark:'Main Chowk',picked_up_at:'2026-09-03T10:00:00Z',failure_reason:'customer_unavailable'}]}));
  await page.goto('/admin/delivery-recovery');
  await page.getByRole('button',{name:'Review return to store'}).click();
  const results=await new AxeBuilder({page}).include('main').withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
});

test('delivery recovery fails closed when capability lookup fails',async({page})=>{
  let queueRequests=0;
  page.on('request',request=>{if(new URL(request.url()).pathname.endsWith('/admin/deliveries/failed'))queueRequests+=1});
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/users/me/capabilities',route=>route.fulfill({status:503,json:{detail:'Capability service unavailable'}}));
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByText('Unable to verify delivery recovery access. Recovery actions are unavailable.')).toBeVisible();
  await expect(page.getByRole('button',{name:'Review return to store'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Return to dispatch pool'})).toHaveCount(0);
  expect(queueRequests).toBe(0);
});

test('customer reads only verified backend proof metadata',async({page})=>{
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[{id:'order-1',order_number:'GO260903000002',status:'delivered',payment_method:'cod',payment_status:'paid',total:'240',created_at:'2026-09-03T10:00:00Z'}]}));
  await page.route('http://localhost:8000/api/v1/orders/order-1',route=>route.fulfill({json:{id:'order-1',order_number:'GO260903000002',status:'delivered',payment_method:'cod',payment_status:'paid',total:'240',items:[],delivery:{id:'delivery-1'}}}));
  await page.route('http://localhost:8000/api/v1/delivery/delivery-1/proof',route=>route.fulfill({json:{id:'proof-1',delivery_id:'delivery-1',verified_at:'2026-09-03T10:30:00Z',recipient_name:'Kiran',created_at:'2026-09-03T10:20:00Z',updated_at:'2026-09-03T10:30:00Z'}}));
  await page.goto('/orders/proof');
  await page.getByRole('combobox').selectOption('order-1');
  await expect(page.getByText('Verified delivery proof')).toBeVisible();
  await expect(page.getByText('Recipient: Kiran')).toBeVisible();
});

test('merchant image upload remains explicit and backend validated',async({page})=>{
  await installApiMocks(page,merchantUser);
  await page.route('http://localhost:8000/api/v1/media/images',route=>route.fulfill({status:201,json:{filename:'catalog.webp',size:4,url:'/media/catalog.webp'}}));
  await page.goto('/merchant/media');
  await page.locator('input[type=file]').setInputFiles({name:'catalog.webp',mimeType:'image/webp',buffer:Buffer.from('test')});
  await page.getByRole('button',{name:'Upload image'}).click();
  await expect(page.getByText('Upload ready')).toBeVisible();
});
