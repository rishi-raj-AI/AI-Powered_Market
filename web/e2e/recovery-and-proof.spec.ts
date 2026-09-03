import {expect,test} from '@playwright/test';
import {activeRider,customer,installApiMocks,merchantUser,superAdmin} from './helpers';

test('rider reports an assigned delivery incident through the guarded endpoint',async({page})=>{
  await installApiMocks(page,activeRider);
  await page.route('http://localhost:8000/api/v1/delivery/delivery-assigned/fail',route=>route.fulfill({json:{id:'delivery-assigned',status:'failed',...route.request().postDataJSON()}}));
  await page.goto('/delivery/incidents');
  await page.getByRole('combobox').first().selectOption('delivery-assigned');
  await page.getByRole('button',{name:'Report incident'}).click();
  await expect(page.getByText('Delivery incident recorded for operations review.')).toBeVisible();
});

test('admin recovery action follows recorded custody',async({page})=>{
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/admin/deliveries/failed',route=>route.fulfill({json:[{id:'delivery-failed',order_number:'GO260903000001',status:'failed',store_name:'Niphad Daily Needs',customer_landmark:'Main Chowk',picked_up_at:'2026-09-03T10:00:00Z',failure_reason:'customer_unavailable'}]}));
  await page.route('http://localhost:8000/api/v1/admin/deliveries/delivery-failed/resolve-failure',route=>route.fulfill({json:{delivery_id:'delivery-failed',resolution:'return_to_store',order_status:'returned',delivery_status:'failed',refund_requested:true,settlement_voided:true}}));
  await page.goto('/admin/delivery-recovery');
  await expect(page.getByRole('button',{name:'Confirm return to store'})).toBeVisible();
  await page.getByRole('button',{name:'Confirm return to store'}).click();
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
