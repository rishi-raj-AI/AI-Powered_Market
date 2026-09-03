import {expect,test} from '@playwright/test';
import {customer,installApiMocks,superAdmin} from './helpers';

const ticket={id:'ticket-1',subject:'Order support',description:'Refund is missing',category:'payment',priority:'high',status:'open',suggested_action:'Review provider state',created_at:'2026-09-03T10:00:00Z'};

test('customer creates and sees an ownership-checked support ticket',async({page})=>{
  await installApiMocks(page,customer);
  let rows:any[]=[];
  await page.route('http://localhost:8000/api/v1/support/tickets/me',r=>r.fulfill({json:rows}));
  await page.route('http://localhost:8000/api/v1/support/tickets',r=>{rows=[ticket];return r.fulfill({status:201,json:ticket})});
  await page.goto('/support?order_id=order-1');
  await page.getByLabel('What happened?').fill('Refund is missing');
  await page.getByRole('button',{name:'Create ticket'}).click();
  await expect(page.getByText('Order support')).toBeVisible();
  await expect(page.getByText(/payment • high • open/)).toBeVisible();
});

test('admin can resolve a triaged ticket',async({page})=>{
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',r=>r.fulfill({json:[ticket]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',r=>r.fulfill({json:{...ticket,status:'resolved'}}));
  await page.goto('/admin/support');
  await expect(page.getByText('Refund is missing')).toBeVisible();
  await page.getByRole('button',{name:'Resolve'}).click();
});
