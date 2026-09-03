import {expect,test} from '@playwright/test';
import {customer,installApiMocks,merchantUser} from './helpers';

test('merchant sees only backend settlement records',async({page})=>{
  await installApiMocks(page,merchantUser);
  await page.route('http://localhost:8000/api/v1/payments/settlements',route=>route.fulfill({json:[{id:'settlement-1',order_id:'order-1',store_id:'store-1',payment_method:'upi',gross_amount:'240.00',merchant_amount:'220.00',delivery_fee_amount:'20.00',status:'pending',created_at:'2026-09-03T10:00:00Z'}]}));
  await page.goto('/merchant/settlements');
  await expect(page.getByRole('heading',{name:'Settlement ledger'})).toBeVisible();
  await expect(page.getByText('₹220.00',{exact:true}).first()).toBeVisible();
  await expect(page.getByText('pending',{exact:true})).toBeVisible();
});

test('customer manages owner-scoped addresses and notification devices',async({page})=>{
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>route.fulfill({json:[{id:'address-1',village_id:'village-niphad',label:'Home',landmark:'Niphad Bus Stand',house_details:'House 10',directions:'Blue gate',is_default:true}]}));
  await page.route('http://localhost:8000/api/v1/notifications/config',route=>route.fulfill({json:{enabled:true}}));
  await page.route('http://localhost:8000/api/v1/notifications/devices',route=>route.fulfill({json:[{id:'device-1',platform:'android',app_version:'1.0.0'}]}));
  await page.goto('/account/addresses');
  await expect(page.getByText('Home • Default')).toBeVisible();
  await expect(page.getByText(/House 10, Niphad Bus Stand/)).toBeVisible();
  await page.goto('/account/devices');
  await expect(page.getByText('Configured',{exact:true})).toBeVisible();
  await expect(page.getByText('android',{exact:true})).toBeVisible();
});

test('stored update links to its backend-referenced order',async({page})=>{
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/notifications/me',route=>route.fulfill({json:[{id:'event-1',user_id:customer.id,event_type:'order.accepted',title:'Order accepted',body:'The merchant accepted your order.',data:{order_id:'order-1'},status:'sent',created_at:'2026-09-03T10:00:00Z'}]}));
  await page.goto('/updates');
  await expect(page.getByRole('link',{name:'View order'})).toHaveAttribute('href','/orders?focus=order-1');
});
