import AxeBuilder from '@axe-core/playwright';
import {expect,test,type Page,type TestInfo} from '@playwright/test';
import path from 'node:path';
import {customer,installApiMocks,superAdmin} from './helpers';

const apiRoot='http://localhost:8000/api/v1';
const customerTicket={id:'support-a11y-customer',user_id:customer.id,store_id:null,order_id:'order-a11y',delivery_id:null,requester_type:'customer',subject:'Order support',description:'रिफंड की स्थिति स्पष्ट नहीं है',category:'payment',priority:'high',status:'open',resolution_notes:null,version:0,created_at:'2026-10-25T10:00:00Z',updated_at:'2026-10-25T10:00:00Z',resolved_at:null};
const adminTicket={...customerTicket,id:'support-a11y-admin',assigned_admin_id:null,triage_summary:'Payment support request',suggested_action:'Review provider state'};

async function capture(page:Page,testInfo:TestInfo,name:string){
  const screenshot=process.env.GAONONE_VISUAL_OUTPUT_DIR?path.join(process.env.GAONONE_VISUAL_OUTPUT_DIR,`${name}-${testInfo.project.name}.png`):testInfo.outputPath(`${name}.png`);
  await page.screenshot({path:screenshot,fullPage:true});
  await testInfo.attach(name,{path:screenshot,contentType:'image/png'});
}

async function expectNoSeriousAxeFindings(page:Page){
  const results=await new AxeBuilder({page}).include('main').withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
}

async function expectUsableControls(page:Page){
  for(const control of await page.locator('main button,main select').all()){
    const box=await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
  }
}

async function expectNoPageOverflow(page:Page){expect(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)).toBe(false)}

async function mockCustomerSupport(page:Page){
  await installApiMocks(page,customer);
  await page.route(`${apiRoot}/support/tickets/me`,route=>route.fulfill({json:[customerTicket]}));
  await page.route(`${apiRoot}/support/tickets/${customerTicket.id}`,route=>route.fulfill({json:customerTicket}));
  await page.route(`${apiRoot}/support/tickets/${customerTicket.id}/messages**`,route=>route.fulfill({json:[]}));
}

async function mockAdminSupport(page:Page){
  await installApiMocks(page,superAdmin);
  await page.route(`${apiRoot}/admin/support/tickets`,route=>route.fulfill({json:[adminTicket]}));
  await page.route(`${apiRoot}/admin/support/tickets/${adminTicket.id}`,route=>route.fulfill({json:adminTicket}));
  await page.route(`${apiRoot}/admin/support/tickets/${adminTicket.id}/messages**`,route=>route.fulfill({json:[]}));
}

for(const width of [320,390,1280]){
  test(`@a11y customer support remains usable at ${width}px`,async({page},testInfo)=>{
    await page.setViewportSize({width,height:844});
    await mockCustomerSupport(page);
    await page.goto('/support');
    await expect(page.getByRole('button',{name:'Order support'})).toBeVisible();
    await page.getByRole('button',{name:'Order support'}).click();
    await expect(page.getByRole('heading',{name:'Conversation'})).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page,testInfo,`customer-support-${width}px`);
  });

  test(`@a11y authorized support operations remain usable at ${width}px`,async({page},testInfo)=>{
    await page.setViewportSize({width,height:844});
    await mockAdminSupport(page);
    await page.goto('/admin/support');
    await expect(page.getByRole('button',{name:'Order support'})).toBeVisible();
    await page.getByRole('button',{name:'Order support'}).click();
    await expect(page.getByRole('heading',{name:'Ticket workspace'})).toBeVisible();
    await expect(page.getByText('Internal — staff only')).toBeVisible();
    await expectNoSeriousAxeFindings(page);
    await expectUsableControls(page);
    await expectNoPageOverflow(page);
    await capture(page,testInfo,`admin-support-${width}px`);
  });
}

test('customer support distinguishes queue failure, retry, and empty state',async({page})=>{
  await installApiMocks(page,customer);let reads=0;let allowSuccess=false;
  await page.route(`${apiRoot}/support/tickets/me`,route=>{reads+=1;return allowSuccess?route.fulfill({json:[]}):route.fulfill({status:503,json:{detail:'Support queue temporarily unavailable'}})});
  await page.goto('/support');
  await expect(page.locator('main .notice[role="alert"]')).toContainText('Support queue temporarily unavailable');
  allowSuccess=true;await page.getByRole('button',{name:'Retry'}).click();
  await expect(page.getByText('No support tickets yet.')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});

test('support operations distinguish queue failure, retry, and empty state',async({page})=>{
  await installApiMocks(page,superAdmin);let reads=0;let allowSuccess=false;
  await page.route(`${apiRoot}/admin/support/tickets`,route=>{reads+=1;return allowSuccess?route.fulfill({json:[]}):route.fulfill({status:503,json:{detail:'Support queue temporarily unavailable'}})});
  await page.goto('/admin/support');
  await expect(page.locator('main .notice[role="alert"]')).toContainText('Support queue temporarily unavailable');
  allowSuccess=true;await page.getByRole('button',{name:'Retry queue'}).click();
  await expect(page.getByText('No support tickets.')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
});
