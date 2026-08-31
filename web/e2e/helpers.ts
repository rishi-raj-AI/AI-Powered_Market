import {Page} from '@playwright/test';

export type MockUser={id:string;phone:string;full_name?:string;role:'customer'|'merchant'|'delivery'|'admin';is_super_admin?:boolean;is_active:boolean;is_verified:boolean;created_at:string};
export const customer:MockUser={id:'user-customer',phone:'+919284800336',full_name:'Kiran',role:'customer',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const merchantUser:MockUser={id:'merchant-owner',phone:'+919975654529',full_name:'Nimbu',role:'merchant',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const superAdmin:MockUser={id:'user-super',phone:'+917249723727',full_name:'Rushikesh',role:'admin',is_super_admin:true,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const normalAdmin:MockUser={id:'user-admin',phone:'+919111111111',full_name:'Pilot Admin',role:'admin',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const activeRider:MockUser={id:'user-rider-active',phone:'+917774877196',full_name:'Bhushan',role:'delivery',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const busyRider:MockUser={id:'user-rider-busy',phone:'+919333333333',full_name:'Suresh',role:'delivery',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const riderCandidate:MockUser={id:'user-rider',phone:'+919222222222',full_name:'Rider Candidate',role:'customer',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
const overview={users:7,villages:1,active_stores:1,merchants:{pending:1,approved:1,suspended:0},orders:{total:1,by_status:{ready:1}},operations:{low_stock_listings:0,ready_unassigned_deliveries:1,active_delivery_partners:2},paid_gmv:'0',gross_order_value:'240'};
const pendingMerchant={id:'merchant-pending',owner_user_id:'user-customer',business_name:'Nimbu Kirana',gstin:null,status:'pending',created_at:'2026-08-28T00:00:00Z'};
const approvedMerchant={id:'merchant-approved',owner_user_id:'merchant-owner',business_name:'Nimbu Kirana',gstin:null,status:'approved',created_at:'2026-08-28T00:00:00Z'};
const village={id:'village-niphad',name:'Niphad',taluka:'Niphad',district:'Nashik',state:'Maharashtra',pincode:'422303',latitude:20.0778,longitude:74.1118,is_active:true};
const serviceArea={id:'area-niphad',name:'Niphad Local',hub_village_id:village.id,radius_km:10,is_active:true};
// An unassigned task is an offer: the backend deliberately withholds customer
// identity until a rider is actually assigned, so the mock must too.
const deliveryOffer={id:'delivery-ready',order_id:'order-ready',order_number:'GO260829000001',status:'unassigned',payment_method:'cod',payment_status:'pending',total:'240',item_count:3,store_name:'Nimbu Kirana',store_landmark:'Niphad Bus Stand',store_latitude:20.0778,store_longitude:74.1118,dropoff_area:'Niphad',dropoff_distance_km:0.5};
// An assigned delivery carries the detail the rider needs to actually deliver.
const assignedTask={id:'delivery-assigned',order_id:'order-assigned',order_number:'GO260829000002',status:'assigned',payment_method:'cod',payment_status:'pending',total:'240',store_name:'Nimbu Kirana',store_phone:'+912550000000',store_landmark:'Niphad Bus Stand',store_latitude:20.0778,store_longitude:74.1118,recipient_name:'Kiran',recipient_phone:'+919284800336',house_details:'House 10',customer_landmark:'Main Chowk',customer_directions:'Blue gate',customer_latitude:20.081,customer_longitude:74.115};
const activeDelivery={id:'delivery-active-admin',order_id:'order-active-admin',order_number:'GO260829000003',delivery_partner_id:busyRider.id,rider_name:'Suresh',rider_phone:busyRider.phone,status:'assigned',assigned_at:'2026-08-29T00:10:00Z',store_name:'Nimbu Kirana',store_landmark:'Niphad Bus Stand',customer_landmark:'Main Chowk'};
export async function installApiMocks(page:Page,currentUser:MockUser=customer){
  await page.addInitScript(()=>localStorage.setItem('gaonone_token','e2e-token'));
  await page.route('http://localhost:8000/api/v1/**',async route=>{
    const request=route.request();const url=new URL(request.url());const path=url.pathname.replace('/api/v1','');const method=request.method();
    if(path==='/users/me')return route.fulfill({json:currentUser});
    if(path==='/admin/overview')return route.fulfill({json:overview});
    if(path==='/admin/users')return route.fulfill({json:[superAdmin,normalAdmin,activeRider,busyRider,riderCandidate,customer,merchantUser]});
    if(path==='/admin/deliveries/active')return route.fulfill({json:[activeDelivery]});
    if(path==='/admin/deliveries/delivery-active-admin/unassign'&&method==='POST')return route.fulfill({json:{...activeDelivery,delivery_partner_id:null,rider_name:null,rider_phone:null,status:'unassigned',assigned_at:null}});
    if(path==='/delivery/tasks/available')return route.fulfill({json:[deliveryOffer]});
    if(path==='/delivery/tasks/me')return route.fulfill({json:[assignedTask]});
    if(path==='/delivery/delivery-assigned/location'&&method==='POST')return route.fulfill({status:201,json:{id:'location-1',delivery_id:'delivery-assigned',...request.postDataJSON()}});
    if(path==='/delivery/delivery-assigned/status'&&method==='PATCH')return route.fulfill({json:{id:'delivery-assigned',order_id:'order-assigned',delivery_partner_id:activeRider.id,status:(request.postDataJSON() as any).status,updated_at:'2026-08-29T00:00:00Z'}});
    if(path==='/merchants/me')return currentUser.role==='merchant'?route.fulfill({json:approvedMerchant}):route.fulfill({status:404,json:{detail:'Merchant profile not found'}});
    if(path==='/merchants')return route.fulfill({json:[pendingMerchant]});
    if(path==='/merchants/apply'&&method==='POST')return route.fulfill({json:pendingMerchant});
    if(path==='/notifications/flush'&&method==='POST')return route.fulfill({json:{events:0,pushes:0}});
    if(path.startsWith('/admin/users/')&&path.endsWith('/role')&&method==='PATCH'){const id=path.split('/')[3];const payload=request.postDataJSON() as {role:MockUser['role'];is_active:boolean};const source=[superAdmin,normalAdmin,activeRider,busyRider,riderCandidate,customer,merchantUser].find(user=>user.id===id)??customer;return route.fulfill({json:{...source,role:payload.role,is_active:payload.is_active}})}
    if(path==='/admin/deliveries/delivery-ready/assign'&&method==='POST'){const payload=request.postDataJSON() as {rider_id:string};return route.fulfill({json:{id:deliveryOffer.id,order_id:deliveryOffer.order_id,delivery_partner_id:payload.rider_id,status:'assigned',assigned_at:'2026-08-29T00:00:00Z'}})}
    if(path.startsWith('/merchants/')&&path.endsWith('/status')&&method==='PATCH')return route.fulfill({json:{...pendingMerchant,status:'approved'}});
    if(path==='/villages')return route.fulfill({json:[village]});if(path==='/service-areas')return route.fulfill({json:[serviceArea]});
    if(path==='/location/autocomplete')return route.fulfill({json:[{place_id:'place-niphad',text:'Niphad, Maharashtra, India',main_text:'Niphad',secondary_text:'Maharashtra, India'}]});
    if(path==='/location/place/place-niphad')return route.fulfill({json:{place_id:'place-niphad',formatted_address:'Niphad, Nashik, Maharashtra 422303, India',latitude:20.0778,longitude:74.1118}});
    if(path==='/location/reverse')return route.fulfill({json:{formatted_address:'Niphad, Nashik, Maharashtra 422303, India',latitude:Number(url.searchParams.get('latitude')),longitude:Number(url.searchParams.get('longitude'))}});
    if(path==='/location/serviceability')return route.fulfill({json:{serviceable:true,service_area_id:serviceArea.id,service_area_name:serviceArea.name,distance_km:0.4,radius_km:10}});
    if(path==='/stores/mine'||path==='/merchant/orders'||path==='/categories'||path==='/orders/me'||path==='/notifications/me'||path==='/addresses/me')return route.fulfill({json:[]});
    if(path==='/stores'&&method==='POST')return route.fulfill({status:201,json:{id:'store-new',merchant_id:approvedMerchant.id,village_id:village.id,service_area_id:serviceArea.id,...request.postDataJSON(),is_active:true}});
    if(path==='/cart')return route.fulfill({json:{id:'cart-1',items:[],subtotal:'0'}});if(path==='/payments/config')return route.fulfill({json:{enabled:false,provider:'razorpay',currency:'INR'}});if(path.startsWith('/products'))return route.fulfill({json:[]});
    return route.fulfill({status:404,json:{detail:`Unmocked E2E API route: ${method} ${path}`}});
  });
}
