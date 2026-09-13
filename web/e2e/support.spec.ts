import {expect,test} from '@playwright/test';
import {customer,installApiMocks,normalAdmin,superAdmin} from './helpers';

const ticket={id:'ticket-1',user_id:customer.id,store_id:null,order_id:'order-1',delivery_id:null,requester_type:'customer',subject:'Order support',description:'Refund is missing',category:'payment',priority:'high',status:'open',resolution_notes:null,version:0,created_at:'2026-09-03T10:00:00Z',updated_at:'2026-09-03T10:00:00Z',resolved_at:null};
const adminTicket={...ticket,assigned_admin_id:null,triage_summary:'Payment support request',suggested_action:'Review provider state'};

test('customer creates and sees an ownership-checked support ticket',async({page})=>{
  await installApiMocks(page,customer);
  let rows:any[]=[];let listRequestCount=0;let releaseInitialList!:()=>void;let markInitialStarted!:()=>void;let markInitialFinished!:()=>void;
  const initialListGate=new Promise<void>(resolve=>{releaseInitialList=resolve});const initialListStarted=new Promise<void>(resolve=>{markInitialStarted=resolve});const initialListFinished=new Promise<void>(resolve=>{markInitialFinished=resolve});
  await page.route('http://localhost:8000/api/v1/support/tickets/me',async route=>{const requestNumber=++listRequestCount;const snapshot=[...rows];if(requestNumber===1){markInitialStarted();await initialListGate}await route.fulfill({json:snapshot});if(requestNumber===1)markInitialFinished()});
  await page.route('http://localhost:8000/api/v1/support/tickets',route=>{if(route.request().method()==='POST'){rows=[ticket];return route.fulfill({status:201,json:ticket})}return route.fallback()});
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1',route=>route.fulfill({json:ticket}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1/messages**',route=>route.fulfill({json:[]}));
  await page.goto('/support?order_id=order-1');await initialListStarted;await page.getByLabel('What happened?').fill('Refund is missing');await page.getByRole('button',{name:'Create ticket'}).click();await expect(page.getByText('Order support').first()).toBeVisible();releaseInitialList();await initialListFinished;await expect(page.getByText('Order support').first()).toBeVisible();
});

test('customer retries an uncertain reply with the same idempotency key',async({page})=>{
  await installApiMocks(page,customer);let attempts=0;const keys:string[]=[];
  await page.route('http://localhost:8000/api/v1/support/tickets/me',route=>route.fulfill({json:[ticket]}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1',route=>route.fulfill({json:ticket}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1/messages**',route=>{if(route.request().method()==='GET')return route.fulfill({json:[]});attempts+=1;keys.push(route.request().postDataJSON().idempotency_key);if(attempts===1)return route.fulfill({status:503,json:{detail:'Delivery uncertain. Retry safely.'}});return route.fulfill({status:201,json:{id:'message-1',author_type:'customer',body:'Here are the details',created_at:'2026-09-03T10:01:00Z'}})});
  await page.goto('/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByLabel('Reply').fill('Here are the details');await page.getByRole('button',{name:'Send reply'}).click();await expect(page.getByText('Delivery uncertain. Retry safely.')).toBeVisible();await page.getByRole('button',{name:'Send reply'}).click();await expect(page.getByText('Here are the details')).toBeVisible();expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
});

test('latest selected customer ticket wins delayed transcript responses',async({page})=>{
  await installApiMocks(page,customer);const second={...ticket,id:'ticket-2',subject:'Delivery support'};let releaseFirst!:()=>void;const firstGate=new Promise<void>(resolve=>{releaseFirst=resolve});
  await page.route('http://localhost:8000/api/v1/support/tickets/me',route=>route.fulfill({json:[ticket,second]}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1',async route=>{await firstGate;return route.fulfill({json:ticket})});
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1/messages**',async route=>{await firstGate;return route.fulfill({json:[{id:'old',author_type:'admin',body:'Old ticket reply',created_at:'2026-09-03T10:01:00Z'}]})});
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-2',route=>route.fulfill({json:second}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-2/messages**',route=>route.fulfill({json:[{id:'new',author_type:'admin',body:'Current ticket reply',created_at:'2026-09-03T10:02:00Z'}]}));
  await page.goto('/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByRole('button',{name:/Delivery support/}).click();await expect(page.getByText('Current ticket reply')).toBeVisible();releaseFirst();await expect(page.getByText('Old ticket reply')).not.toBeVisible();
});

test('customer ticket detail remains usable when the transcript request fails',async({page})=>{
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/support/tickets/me',route=>route.fulfill({json:[ticket]}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1',route=>route.fulfill({json:ticket}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1/messages**',route=>route.fulfill({status:503,json:{detail:'Conversation temporarily unavailable'}}));
  await page.goto('/support');await page.getByRole('button',{name:/Order support/}).click();
  await expect(page.getByText('Refund is missing').last()).toBeVisible();
  await expect(page.getByText(/Conversation unavailable/)).toBeVisible();
  await expect(page.getByText('No replies yet.')).not.toBeVisible();
});

test('customer list failure is not presented as an empty queue',async({page})=>{
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/support/tickets/me',route=>route.fulfill({status:503,json:{detail:'Ticket list temporarily unavailable'}}));
  await page.goto('/support');
  await expect(page.getByText(/Tickets unavailable/)).toBeVisible();
  await expect(page.getByText('No support tickets yet.')).not.toBeVisible();
  await expect(page.getByRole('button',{name:'Retry'})).toBeVisible();
});

test('customer pending reply preserves text typed after the request started',async({page})=>{
  await installApiMocks(page,customer);let releaseSend!:()=>void;const sendGate=new Promise<void>(resolve=>{releaseSend=resolve});
  await page.route('http://localhost:8000/api/v1/support/tickets/me',route=>route.fulfill({json:[ticket]}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1',route=>route.fulfill({json:ticket}));
  await page.route('http://localhost:8000/api/v1/support/tickets/ticket-1/messages**',async route=>{if(route.request().method()==='GET')return route.fulfill({json:[]});await sendGate;return route.fulfill({status:201,json:{id:'sent',author_type:'customer',body:'Original reply',created_at:'2026-09-03T10:05:00Z'}})});
  await page.goto('/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByLabel('Reply').fill('Original reply');await page.getByRole('button',{name:'Send reply'}).click();await page.getByLabel('Reply').fill('Follow-up draft');releaseSend();
  await expect(page.getByLabel('Reply')).toHaveValue('Follow-up draft');
  await expect(page.getByText('Original reply')).toBeVisible();
});

test('admin without support.manage never loads or renders the privileged workspace',async({page})=>{
  await installApiMocks(page,normalAdmin);let supportRequests=0;
  page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/v1/admin/support/'))supportRequests+=1});
  await page.route('http://localhost:8000/api/v1/users/me/capabilities',route=>route.fulfill({json:{is_super_admin:false,capabilities:['user.read']}}));
  await page.goto('/admin/support');
  await expect(page.getByRole('alert').filter({hasText:'Support access is not available for this account.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Ticket workspace'})).not.toBeVisible();
  expect(supportRequests).toBe(0);
});

test('capability discovery failure denies privileged rendering until an explicit retry succeeds',async({page})=>{
  await installApiMocks(page,superAdmin);let allowCapabilities=false;let supportRequests=0;
  page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/v1/admin/support/'))supportRequests+=1});
  await page.route('http://localhost:8000/api/v1/users/me/capabilities',route=>allowCapabilities?route.fulfill({json:{is_super_admin:true,capabilities:['support.manage','user.read']}}):route.fulfill({status:503,json:{detail:'Capability service temporarily unavailable'}}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[]}));
  await page.goto('/admin/support');
  await expect(page.getByRole('alert').filter({hasText:'Unable to verify support access.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Ticket workspace'})).not.toBeVisible();expect(supportRequests).toBe(0);
  allowCapabilities=true;await page.getByRole('button',{name:'Retry access check'}).click();
  await expect(page.getByRole('heading',{name:'Ticket workspace'})).toBeVisible();expect(supportRequests).toBe(1);
});

test('support.manage without user.read keeps the queue usable without user discovery',async({page})=>{
  await installApiMocks(page,normalAdmin);let userRequests=0;
  page.on('request',request=>{if(new URL(request.url()).pathname==='/api/v1/admin/users')userRequests+=1});
  await page.route('http://localhost:8000/api/v1/users/me/capabilities',route=>route.fulfill({json:{is_super_admin:false,capabilities:['support.manage']}}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',route=>route.fulfill({json:adminTicket}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>route.fulfill({json:[]}));
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();
  await expect(page.getByRole('heading',{name:'Ticket workspace'})).toBeVisible();
  await expect(page.getByLabel('Assigned administrator')).toBeDisabled();
  await expect(page.getByText(/Administrator assignment requires user.read access/)).toBeVisible();
  expect(userRequests).toBe(0);
});

test('admin keeps public replies, internal notes, assignment and status contracts distinct',async({page})=>{
  await installApiMocks(page,superAdmin);let current:any={...adminTicket};const writes:{path:string;payload:any}[]=[];
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[current]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',route=>{const request=route.request();if(request.method()==='GET')return route.fulfill({json:current});const payload=request.postDataJSON();writes.push({path:'status',payload});current={...current,status:payload.status,version:current.version+1};return route.fulfill({json:current})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/assignment',route=>{const payload=route.request().postDataJSON();writes.push({path:'assignment',payload});current={...current,assigned_admin_id:payload.assigned_admin_id,version:current.version+1};return route.fulfill({json:current})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>{const request=route.request();if(request.method()==='GET')return route.fulfill({json:[]});const payload=request.postDataJSON();writes.push({path:'public',payload});current={...current,version:current.version+1};return route.fulfill({status:201,json:{id:'public-1',author_type:'admin',body:payload.body,created_at:'2026-09-03T10:01:00Z'}})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/internal-notes',route=>{const payload=route.request().postDataJSON();writes.push({path:'internal',payload});current={...current,version:current.version+1};return route.fulfill({status:201,json:{id:'internal-1',author_type:'admin',author_user_id:superAdmin.id,body:payload.body,created_at:'2026-09-03T10:02:00Z'}})});
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByLabel('Assigned administrator').selectOption(normalAdmin.id);await page.getByLabel('Public reply').fill('Visible requester reply');await page.getByRole('button',{name:'Send public reply'}).click();await page.getByLabel('Internal note').fill('Staff-only provider reference');await page.getByRole('button',{name:'Save internal note'}).click();await page.getByRole('button',{name:'Resolve'}).click();
  expect(writes.find(write=>write.path==='assignment')?.payload).toEqual({assigned_admin_id:normalAdmin.id,expected_version:0});expect(writes.find(write=>write.path==='public')?.payload.idempotency_key).toBeTruthy();expect(writes.find(write=>write.path==='internal')?.payload.idempotency_key).toBeTruthy();expect(writes.find(write=>write.path==='status')?.payload).toEqual({status:'resolved',expected_version:3});await expect(page.getByText('Visible requester reply')).toBeVisible();await expect(page.getByText('Staff-only provider reference')).toBeVisible();
});

test('admin refreshes authoritative ticket state after a version conflict',async({page})=>{
  await installApiMocks(page,superAdmin);let detail:any={...adminTicket};let patchCount=0;
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',route=>{if(route.request().method()==='GET')return route.fulfill({json:detail});patchCount+=1;detail={...detail,status:'waiting_customer',version:4};return route.fulfill({status:409,json:{detail:{message:'Support ticket changed; refresh and retry',version:4}}})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>route.fulfill({json:[]}));
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByRole('button',{name:'Resolve'}).click();expect(patchCount).toBe(1);await expect(page.getByText('Waiting for requester').first()).toBeVisible();
});

test('admin loads assignee pages independently and retains public messages when internal notes fail',async({page})=>{
  await installApiMocks(page,superAdmin);
  const firstPage=Array.from({length:500},(_,index)=>({...customer,id:`customer-${index}`,phone:`+9188${String(index).padStart(8,'0')}`}));
  await page.route('http://localhost:8000/api/v1/admin/users**',route=>{const offset=new URL(route.request().url()).searchParams.get('offset');return route.fulfill({json:offset==='500'?[normalAdmin]:firstPage})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',route=>route.fulfill({json:adminTicket}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>{const visibility=new URL(route.request().url()).searchParams.get('visibility');if(visibility==='internal')return route.fulfill({status:503,json:{detail:'Internal notes temporarily unavailable'}});return route.fulfill({json:[{id:'public-existing',author_type:'customer',body:'Public context remains visible',created_at:'2026-09-03T10:04:00Z'}]})});
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();
  await expect(page.getByText('Public context remains visible')).toBeVisible();
  await expect(page.getByText(/Internal notes temporarily unavailable/)).toBeVisible();
  await expect(page.getByLabel('Assigned administrator').getByRole('option',{name:'Pilot Admin'})).toHaveCount(1);
});

test('admin clears protected ticket content when support access is revoked',async({page})=>{
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',route=>route.fulfill({json:adminTicket}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>route.fulfill({json:[]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/assignment',route=>route.fulfill({status:403,json:{detail:'Missing capability: support.manage'}}));
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByLabel('Assigned administrator').selectOption(normalAdmin.id);
  await expect(page.getByText('Support access is not available for this account.')).toBeVisible();
  await expect(page.getByText('Internal — staff only')).not.toBeVisible();
  await expect(page.getByText('Refund is missing')).not.toBeVisible();
});

test('admin ignores a delayed mutation response after selecting another ticket',async({page})=>{
  await installApiMocks(page,superAdmin);const second={...adminTicket,id:'ticket-2',subject:'Delivery support'};let releasePatch!:()=>void;const patchGate=new Promise<void>(resolve=>{releasePatch=resolve});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket,second]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',async route=>{if(route.request().method()==='GET')return route.fulfill({json:adminTicket});await patchGate;return route.fulfill({json:{...adminTicket,status:'resolved',version:1}})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-2',route=>route.fulfill({json:second}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>route.fulfill({json:[]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-2/messages**',route=>route.fulfill({json:[]}));
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();await page.getByRole('button',{name:'Resolve'}).click();await page.getByRole('button',{name:/Delivery support/}).click();releasePatch();
  await expect(page.getByRole('heading',{name:'Ticket workspace'})).toBeVisible();
  await expect(page.getByText('Delivery support').last()).toBeVisible();
  await expect(page.getByText('Ticket status updated.')).not.toBeVisible();
});

test('support denial invalidates delayed protected responses in both directions',async({page})=>{
  await installApiMocks(page,superAdmin);let releaseInternal!:()=>void;const internalGate=new Promise<void>(resolve=>{releaseInternal=resolve});let releaseAssignees!:()=>void;const assigneeGate=new Promise<void>(resolve=>{releaseAssignees=resolve});
  await page.route('http://localhost:8000/api/v1/admin/users**',async route=>{await assigneeGate;return route.fulfill({json:[normalAdmin]})});
  await page.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket]}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',route=>route.fulfill({status:403,json:{detail:'Missing capability: support.manage'}}));
  await page.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',async route=>{const visibility=new URL(route.request().url()).searchParams.get('visibility');if(visibility==='internal'){await internalGate;return route.fulfill({json:[{id:'late-note',author_type:'admin',author_user_id:superAdmin.id,body:'Late protected note',created_at:'2026-09-03T10:06:00Z'}]})}return route.fulfill({json:[]})});
  await page.goto('/admin/support');await page.getByRole('button',{name:/Order support/}).click();await expect(page.getByText('Support access is not available for this account.')).toBeVisible();releaseInternal();releaseAssignees();await expect(page.getByText('Late protected note')).not.toBeVisible();await expect(page.getByLabel('Assigned administrator')).not.toBeVisible();

  const secondPage=await page.context().newPage();await installApiMocks(secondPage,superAdmin);let releaseDetail!:()=>void;const detailGate=new Promise<void>(resolve=>{releaseDetail=resolve});
  await secondPage.route('http://localhost:8000/api/v1/admin/support/tickets',route=>route.fulfill({json:[adminTicket]}));
  await secondPage.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1',async route=>{await detailGate;return route.fulfill({json:adminTicket})});
  await secondPage.route('http://localhost:8000/api/v1/admin/support/tickets/ticket-1/messages**',route=>{const visibility=new URL(route.request().url()).searchParams.get('visibility');return visibility==='internal'?route.fulfill({status:403,json:{detail:'Missing capability: support.manage'}}):route.fulfill({json:[]})});
  await secondPage.goto('/admin/support');await secondPage.getByRole('button',{name:/Order support/}).click();await expect(secondPage.getByRole('alert').filter({hasText:'Support access is not available for this account.'})).toBeVisible();releaseDetail();await expect(secondPage.getByText('Payment support request')).not.toBeVisible();await secondPage.close();
});

test('admin sees factual delivery performance without invented confidence',async({page})=>{
  await installApiMocks(page,superAdmin);
  await page.route('http://localhost:8000/api/v1/admin/delivery-performance',route=>route.fulfill({json:{window_days:30,total_records:12,delivered:9,failed:1,active:2,median_assignment_to_pickup_seconds:600,median_pickup_to_delivery_seconds:1200,basis:'recorded_delivery_timestamps'}}));
  await page.goto('/admin/delivery-performance');
  await expect(page.getByText('10 min median')).toBeVisible();
  await expect(page.getByText('20 min median')).toBeVisible();
  await expect(page.getByText(/No predicted ETA or confidence score/)).toBeVisible();
});
