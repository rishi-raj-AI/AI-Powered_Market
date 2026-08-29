import AxeBuilder from '@axe-core/playwright';
import {expect,test} from '@playwright/test';
import {customer,installApiMocks} from './helpers';

const order={id:'order-live',order_number:'GO260829LIVE01',user_id:customer.id,store_id:'store-1',address_id:'address-1',status:'out_for_delivery',payment_method:'cod',payment_status:'pending',subtotal:'220',delivery_fee:'20',total:'240',created_at:'2026-08-29T00:00:00Z',updated_at:'2026-08-29T00:10:00Z'};
const detail={...order,store_name:'Nimbu Kirana',store_phone:'+919975654529',store_landmark:'Niphad Bus Stand',recipient_name:'Kiran',recipient_phone:customer.phone,house_details:'House 10',customer_landmark:'Main Chowk',customer_directions:'Blue gate',items:[{id:'item-1',product_id:'product-1',product_name:'Rice',unit:'1 kg',unit_price:'220',quantity:1,line_total:'220'}],delivery:{id:'delivery-live',delivery_partner_id:'user-rider-active',status:'picked_up',assigned_at:'2026-08-29T00:05:00Z',picked_up_at:'2026-08-29T00:08:00Z'}};
const tracking={order_id:order.id,order_number:order.order_number,order_status:'out_for_delivery',delivery_id:'delivery-live',delivery_status:'picked_up',tracking_active:true,store:{latitude:20.0778,longitude:74.1118,label:'Nimbu Kirana'},customer:{latitude:20.081,longitude:74.115,label:'Main Chowk'},rider:{id:'location-1',delivery_id:'delivery-live',latitude:20.079,longitude:74.113,accuracy_m:7,heading_deg:90,speed_mps:4,recorded_at:'2026-08-29T00:10:00Z'},rider_location_age_seconds:4};
const route={available:true,provider:'google',origin:{latitude:20.079,longitude:74.113,label:'Delivery partner'},destination:{latitude:20.081,longitude:74.115,label:'Main Chowk'},distance_meters:1800,duration_seconds:420,encoded_polyline:''};

async function mockTracking(page:any,{delivered=false}={}){
  await installApiMocks(page,customer);
  await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[delivered?{...order,status:'delivered',payment_status:'paid'}:order]}));
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}`,route=>route.fulfill({json:delivered?{...detail,status:'delivered',payment_status:'paid',delivery:{...detail.delivery,status:'delivered',delivered_at:'2026-08-29T00:15:00Z'}}:detail}));
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}/tracking`,route=>route.fulfill({json:delivered?{...tracking,order_status:'delivered',delivery_status:'delivered',tracking_active:false,rider:null,rider_location_age_seconds:null}:tracking}));
  await page.route(`http://localhost:8000/api/v1/orders/${order.id}/route`,route=>route.fulfill({json:delivered?{...route,available:false,provider:'none'}:route}));
}

test('customer sees live rider ETA, distance and GPS freshness',async({page})=>{
  await mockTracking(page);
  await page.goto('/orders');
  await page.getByRole('button',{name:'Toggle order detail'}).click();
  await expect(page.getByText('Live delivery')).toBeVisible();
  await expect(page.getByText('ETA 7 min')).toBeVisible();
  await expect(page.getByText('1.8 km remaining')).toBeVisible();
  await expect(page.getByText('Rider location received 4s ago')).toBeVisible();
  await expect(page.getByText(/GPS accuracy ≈ 7 m/)).toBeVisible();
  await expect(page.getByRole('link',{name:'Open rider location'})).toBeVisible();
});

test('delivered order stops exposing rider location for privacy',async({page})=>{
  await mockTracking(page,{delivered:true});
  await page.goto('/orders');
  await page.getByRole('button',{name:'Toggle order detail'}).click();
  await expect(page.getByText('Delivery completed. Live rider sharing has stopped for privacy.')).toBeVisible();
  await expect(page.getByRole('link',{name:'Open rider location'})).toHaveCount(0);
});

test('@a11y customer live tracking has no serious accessibility violations',async({page})=>{
  await mockTracking(page);
  await page.goto('/orders');
  await page.getByRole('button',{name:'Toggle order detail'}).click();
  await expect(page.getByText('Live delivery')).toBeVisible();
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
});

test('live tracking avoids horizontal page overflow on mobile',async({page})=>{
  await mockTracking(page);
  await page.setViewportSize({width:390,height:844});
  await page.goto('/orders');
  await page.getByRole('button',{name:'Toggle order detail'}).click();
  const pageOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
  expect(pageOverflow).toBe(false);
});
