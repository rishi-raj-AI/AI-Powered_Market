import AxeBuilder from '@axe-core/playwright';
import {expect,Page,test} from '@playwright/test';
import {customer,installApiMocks} from './helpers';

const order={id:'order-live',order_number:'GO260829LIVE01',user_id:customer.id,store_id:'store-1',address_id:'address-1',status:'out_for_delivery',payment_method:'cod',payment_status:'pending',subtotal:'220',delivery_fee:'20',total:'240',created_at:'2026-08-29T00:00:00Z',updated_at:'2026-08-29T00:10:00Z'};
const detail={...order,store_name:'Nimbu Kirana',store_phone:'+919975654529',store_landmark:'Niphad Bus Stand',recipient_name:'Kiran',recipient_phone:customer.phone,house_details:'House 10',customer_landmark:'Main Chowk',customer_directions:'Blue gate',items:[{id:'item-1',product_id:'product-1',product_name:'Rice',unit:'1 kg',unit_price:'220',quantity:1,line_total:'220'}],delivery:{id:'delivery-live',delivery_partner_id:'user-rider-active',status:'picked_up',assigned_at:'2026-08-29T00:05:00Z',picked_up_at:'2026-08-29T00:08:00Z'}};
const tracking={order_id:order.id,order_number:order.order_number,order_status:'out_for_delivery',delivery_id:'delivery-live',delivery_status:'picked_up',tracking_active:true,store:{latitude:20.0778,longitude:74.1118,label:'Nimbu Kirana'},customer:{latitude:20.081,longitude:74.115,label:'Main Chowk'},rider:{id:'location-1',delivery_id:'delivery-live',latitude:20.079,longitude:74.113,accuracy_m:7,heading_deg:90,speed_mps:4,recorded_at:'2026-08-29T00:10:00Z'},rider_location_age_seconds:4};
const route={available:true,provider:'google',origin:{latitude:20.079,longitude:74.113,label:'Delivery partner'},destination:{latitude:20.081,longitude:74.115,label:'Main Chowk'},distance_meters:1800,duration_seconds:420,encoded_polyline:''};

async function mockTracking(page:Page,{delivered=false,stale=false,expired=false}={}){
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/orders/me',r=>r.fulfill({json:[delivered?{...order,status:'delivered',payment_status:'paid'}:order]}));
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}`,r=>r.fulfill({json:delivered?{...detail,status:'delivered',payment_status:'paid',delivery:{...detail.delivery,status:'delivered',delivered_at:'2026-08-29T00:15:00Z'}}:detail}));
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}/tracking`,r=>r.fulfill(expired?{status:401,json:{detail:'Not authenticated'}}:{json:delivered?{...tracking,order_status:'delivered',delivery_status:'delivered',tracking_active:false,rider:null,rider_location_age_seconds:null}:stale?{...tracking,rider_location_age_seconds:45}:tracking}));
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}/route`,r=>r.fulfill({json:delivered?{...route,available:false,provider:'none'}:route}));
}

test('customer cannot start a second payment intent while the first is pending',async({page})=>{
  const upiOrder={...order,status:'placed',payment_method:'upi',payment_status:'pending'};let attempts=0;let releaseIntent!:()=>void;let intentStarted!:()=>void;
  const intentGate=new Promise<void>(resolve=>{releaseIntent=resolve});const firstIntent=new Promise<void>(resolve=>{intentStarted=resolve});
  await installApiMocks(page,customer);await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[upiOrder]}));
  await page.route(`http://localhost:8000/api/v1/payments/orders/${order.id}/intent`,async route=>{attempts+=1;intentStarted();await intentGate;await route.abort('connectionreset')});
  await page.goto('/orders');await page.getByRole('button',{name:'Pay now'}).click();await firstIntent;
  const opening=page.getByRole('button',{name:'Opening…'});await expect(opening).toBeDisabled();
  await opening.evaluate(button=>{button.removeAttribute('disabled');button.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))});
  expect(attempts).toBe(1);releaseIntent();await expect(page.getByRole('button',{name:'Pay now'})).toBeEnabled();
});

test('customer keeps a pending UPI order recoverable when online payment is unavailable',async({page})=>{
  const upiOrder={...order,status:'placed',payment_method:'upi',payment_status:'pending'};let attempts=0;let secondIntentStarted!:()=>void;let releaseSecondIntent!:()=>void;
  const secondIntent=new Promise<void>(resolve=>{secondIntentStarted=resolve});const secondIntentGate=new Promise<void>(resolve=>{releaseSecondIntent=resolve});
  await installApiMocks(page,customer);await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[upiOrder]}));
  await page.route(`http://localhost:8000/api/v1/payments/orders/${order.id}/intent`,async route=>{attempts+=1;if(attempts===2){secondIntentStarted();await secondIntentGate}await route.fulfill({status:503,json:{detail:'Payment provider is not configured'}})});
  await page.goto('/orders');
  const pay=page.getByRole('button',{name:'Pay now'});await expect(pay).toBeEnabled();await pay.click();
  await expect(page.getByText('We could not safely check your previous payment right now. Your order is saved; please check its status before trying again to avoid paying twice.')).toBeVisible();
  await expect(page.getByText('Payment provider is not configured')).toHaveCount(0);await expect(pay).toBeEnabled();await expect(page.getByText('Payment: Pending')).toBeVisible();expect(attempts).toBe(1);
  await pay.click();await secondIntent;const opening=page.getByRole('button',{name:'Opening…'});await expect(opening).toBeDisabled();releaseSecondIntent();await expect(pay).toBeEnabled();expect(attempts).toBe(2);
});

test('customer sees verified payment after intent fails but a webhook has already captured it',async({page})=>{
  const upiOrder={...order,status:'placed',payment_method:'upi',payment_status:'pending'};
  let orderReads=0;let intentCalls=0;let webhookCaptured=false;
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/orders/me',route=>{
    orderReads+=1;
    // React Strict Mode may load orders twice on mount. Payment must only
    // become paid after the attempted intent discovers the webhook capture,
    // not after an arbitrary number of initial GET requests.
    return route.fulfill({json:[webhookCaptured?{...upiOrder,payment_status:'paid'}:upiOrder]});
  });
  await page.route(`http://localhost:8000/api/v1/payments/orders/${order.id}/intent`,route=>{
    intentCalls+=1;
    webhookCaptured=true;
    return route.fulfill({status:409,json:{detail:'Existing payment requires reconciliation'}});
  });
  await page.goto('/orders');
  const pay=page.getByRole('button',{name:'Pay now'});
  await expect(pay).toBeVisible();
  await pay.click();
  await expect(page.getByText(`Payment verified for ${order.order_number}.`)).toBeVisible();
  await expect(page.getByText('Payment: Paid')).toBeVisible();
  await expect(pay).toHaveCount(0);
  expect(intentCalls).toBe(1);
  expect(orderReads).toBeGreaterThanOrEqual(2);
});

test('a slow older orders refresh cannot undo a verified payment',async({page})=>{
  const upiOrder={...order,status:'placed',payment_method:'upi',payment_status:'pending'};
  let intentCalls=0;let holdRefresh=false;let refreshHeld=false;let providerCaptured=false;
  let staleRequested!:()=>void;let releaseStale!:()=>void;
  const staleStarted=new Promise<void>(resolve=>{staleRequested=resolve});
  const staleGate=new Promise<void>(resolve=>{releaseStale=resolve});
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/orders/me',async route=>{
    if(holdRefresh && !refreshHeld){
      refreshHeld=true;
      staleRequested();
      await staleGate;
      return route.fulfill({json:[upiOrder],headers:{'x-e2e-stale':'1'}});
    }
    return route.fulfill({json:[providerCaptured?{...upiOrder,payment_status:'paid'}:upiOrder]});
  });
  await page.route(`http://localhost:8000/api/v1/payments/orders/${order.id}/intent`,route=>{
    intentCalls+=1;
    providerCaptured=true;
    return route.fulfill({status:409,json:{detail:'Payment requires reconciliation'}});
  });
  await page.goto('/orders');
  const pay=page.getByRole('button',{name:'Pay now'});
  await expect(pay).toBeVisible();
  holdRefresh=true;
  await page.getByRole('button',{name:'Refresh',exact:true}).click();
  await staleStarted;
  await pay.click();
  await expect(page.getByText(`Payment verified for ${order.order_number}.`)).toBeVisible();
  await expect(page.getByText('Payment: Paid')).toBeVisible();
  const staleResponse=page.waitForResponse(response=>
    response.url().endsWith('/orders/me') && response.headers()['x-e2e-stale']==='1'
  );
  releaseStale();
  await staleResponse;
  // Allow the response handler to render: a late PENDING response must not
  // replace the paid card or expose a second checkout window.
  await page.waitForTimeout(150);
  await expect(page.getByText('Payment: Paid')).toBeVisible();
  await expect(pay).toHaveCount(0);
  expect(intentCalls).toBe(1);
});

test('non-placed UPI orders cannot start a new checkout from the website',async({page})=>{
  const stale={...order,status:'accepted',payment_method:'upi',payment_status:'pending'};
  let intentCalls=0;
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[stale]}));
  await page.route(`http://localhost:8000/api/v1/payments/orders/${order.id}/intent`,route=>{
    intentCalls+=1;
    return route.fulfill({status:409,json:{detail:'Order is not eligible for online payment'}});
  });
  await page.goto('/orders');
  await expect(page.getByText('Payment: Pending')).toBeVisible();
  await expect(page.getByRole('button',{name:'Pay now'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Retry payment'})).toHaveCount(0);
  expect(intentCalls).toBe(0);
});

test('customer sees live rider route estimate, distance and GPS freshness',async({page})=>{await mockTracking(page);await page.goto('/orders');await page.getByRole('button',{name:'Toggle order detail'}).click();await expect(page.getByText('Live delivery')).toBeVisible();await expect(page.getByText('Live route estimate 7 min')).toBeVisible();await expect(page.getByText('1.8 km remaining')).toBeVisible();await expect(page.getByText('Rider location received 4s ago')).toBeVisible();await expect(page.getByText(/GPS accuracy ≈ 7 m/)).toBeVisible();await expect(page.getByRole('link',{name:'Open rider location'})).toBeVisible()});
test('stale rider GPS pauses ETA and warns customer',async({page})=>{await mockTracking(page,{stale:true});await page.goto('/orders');await page.getByRole('button',{name:'Toggle order detail'}).click();await expect(page.getByText('ETA paused until a fresh rider location arrives.')).toBeVisible();await expect(page.getByText(/Rider location may be delayed/)).toBeVisible();await expect(page.getByText('Live route estimate 7 min')).toHaveCount(0)});
test('tracking keeps the last known rider location but pauses ETA after polling fails',async({page})=>{
  await mockTracking(page);
  // Allow initial tracking and route requests to settle before simulating an outage.
  // Counting requests races with background polling and can fail before the initial
  // live ETA is rendered, particularly in slower CI browsers.
  let failTracking=false;
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}/tracking`,r=>
    failTracking?r.fulfill({status:503,json:{detail:'Temporary outage'}}):r.fulfill({json:tracking})
  );
  await page.goto('/orders');
  await page.getByRole('button',{name:'Toggle order detail'}).click();
  await expect(page.getByText('Live route estimate 7 min')).toBeVisible();
  failTracking=true;
  await expect(page.getByText('Tracking connection interrupted. Showing last known information; ETA paused until updates resume.')).toBeVisible({timeout:12000});
  await expect(page.getByText('ETA paused until a fresh rider location arrives.')).toBeVisible();
  await expect(page.getByText('Live route estimate 7 min')).toHaveCount(0);
  await expect(page.getByRole('link',{name:'Open rider location'})).toBeVisible();
});
test('delivered order stops exposing rider location for privacy',async({page})=>{await mockTracking(page,{delivered:true});await page.goto('/orders');await page.getByRole('button',{name:'Toggle order detail'}).click();await expect(page.getByText('Delivery completed. Live rider sharing has stopped for privacy.')).toBeVisible();await expect(page.getByRole('link',{name:'Open rider location'})).toHaveCount(0)});
test('expired live tracking session clears GaonOne state and returns to provider-neutral sign-in',async({page})=>{await mockTracking(page,{expired:true});await page.addInitScript(()=>{const removeItem=Storage.prototype.removeItem;Storage.prototype.removeItem=function(key){if(key==='gaonone_token')sessionStorage.setItem('gaonone_e2e_token_cleared','true');return removeItem.call(this,key)}});await page.goto('/orders');await Promise.all([page.waitForURL(/\/login\?next=%2Forders$/),page.getByRole('button',{name:'Toggle order detail'}).click()]);expect(await page.evaluate(()=>sessionStorage.getItem('gaonone_e2e_token_cleared'))).toBe('true');await expect(page.getByRole('button',{name:'Continue with Google'})).toBeVisible()});
test('@a11y customer live tracking has no serious accessibility violations',async({page})=>{await mockTracking(page);await page.goto('/orders');await page.getByRole('button',{name:'Toggle order detail'}).click();await expect(page.getByText('Live delivery')).toBeVisible();const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();expect(results.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([])});
test('live tracking avoids horizontal page overflow on mobile',async({page})=>{await mockTracking(page);await page.setViewportSize({width:390,height:844});await page.goto('/orders');await page.getByRole('button',{name:'Toggle order detail'}).click();const pageOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);expect(pageOverflow).toBe(false)});
