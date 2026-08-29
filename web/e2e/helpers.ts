import {Page} from '@playwright/test';

export type MockUser={
  id:string;phone:string;full_name?:string;role:'customer'|'merchant'|'delivery'|'admin';
  is_super_admin?:boolean;is_active:boolean;is_verified:boolean;created_at:string;
};

export const customer:MockUser={id:'user-customer',phone:'+919284800336',full_name:'Kiran',role:'customer',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const merchantUser:MockUser={id:'merchant-owner',phone:'+919975654529',full_name:'Nimbu',role:'merchant',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const superAdmin:MockUser={id:'user-super',phone:'+917249723727',full_name:'Rushikesh',role:'admin',is_super_admin:true,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const normalAdmin:MockUser={id:'user-admin',phone:'+919111111111',full_name:'Pilot Admin',role:'admin',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const riderCandidate:MockUser={id:'user-rider',phone:'+917774877196',full_name:'Bhushan',role:'customer',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};

const overview={users:5,villages:1,active_stores:0,merchants:{pending:0,approved:1,suspended:0},orders:{total:0,by_status:{}},operations:{low_stock_listings:0,ready_unassigned_deliveries:0,active_delivery_partners:0},paid_gmv:'0',gross_order_value:'0'};
const pendingMerchant={id:'merchant-pending',owner_user_id:'user-customer',business_name:'Nimbu Kirana',gstin:null,status:'pending',created_at:'2026-08-28T00:00:00Z'};
const approvedMerchant={id:'merchant-approved',owner_user_id:'merchant-owner',business_name:'Nimbu Kirana',gstin:null,status:'approved',created_at:'2026-08-28T00:00:00Z'};
const village={id:'village-niphad',name:'Niphad',taluka:'Niphad',district:'Nashik',state:'Maharashtra',pincode:'422303',latitude:20.0778,longitude:74.1118,is_active:true};
const serviceArea={id:'area-niphad',name:'Niphad Local',hub_village_id:village.id,radius_km:10,is_active:true};

export async function installApiMocks(page:Page,currentUser:MockUser=customer){
  await page.addInitScript(()=>localStorage.setItem('gaonone_token','e2e-token'));
  await page.route('http://localhost:8000/api/v1/**',async route=>{
    const request=route.request();const url=new URL(request.url());const path=url.pathname.replace('/api/v1','');const method=request.method();
    if(path==='/users/me')return route.fulfill({json:currentUser});
    if(path==='/admin/overview')return route.fulfill({json:overview});
    if(path==='/admin/users')return route.fulfill({json:[superAdmin,normalAdmin,riderCandidate,customer,merchantUser]});
    if(path==='/merchants/me')return currentUser.role==='merchant'?route.fulfill({json:approvedMerchant}):route.fulfill({status:404,json:{detail:'Merchant profile not found'}});
    if(path==='/merchants')return route.fulfill({json:[pendingMerchant]});
    if(path==='/merchants/apply'&&method==='POST')return route.fulfill({json:pendingMerchant});
    if(path==='/notifications/flush'&&method==='POST')return route.fulfill({json:{events:0,pushes:0}});
    if(path.startsWith('/admin/users/')&&path.endsWith('/role')&&method==='PATCH'){const id=path.split('/')[3];const payload=request.postDataJSON() as {role:MockUser['role'];is_active:boolean};const source=[superAdmin,normalAdmin,riderCandidate,customer,merchantUser].find(user=>user.id===id)??customer;return route.fulfill({json:{...source,role:payload.role,is_active:payload.is_active}})}
    if(path.startsWith('/merchants/')&&path.endsWith('/status')&&method==='PATCH')return route.fulfill({json:{...pendingMerchant,status:'approved'}});
    if(path==='/villages')return route.fulfill({json:[village]});
    if(path==='/service-areas')return route.fulfill({json:[serviceArea]});
    if(path==='/location/autocomplete')return route.fulfill({json:[{place_id:'place-niphad',text:'Niphad, Maharashtra, India',main_text:'Niphad',secondary_text:'Maharashtra, India'}]});
    if(path==='/location/place/place-niphad')return route.fulfill({json:{place_id:'place-niphad',formatted_address:'Niphad, Nashik, Maharashtra 422303, India',latitude:20.0778,longitude:74.1118}});
    if(path==='/location/reverse')return route.fulfill({json:{formatted_address:'Niphad, Nashik, Maharashtra 422303, India',latitude:Number(url.searchParams.get('lat')),longitude:Number(url.searchParams.get('lng'))}});
    if(path==='/location/serviceability')return route.fulfill({json:{serviceable:true,service_area_id:serviceArea.id,service_area_name:serviceArea.name,distance_km:0.4,radius_km:10}});
    if(path==='/stores/mine'||path==='/merchant/orders'||path==='/categories'||path==='/orders/me'||path==='/notifications/me'||path==='/addresses/me')return route.fulfill({json:[]});
    if(path==='/stores'&&method==='POST')return route.fulfill({status:201,json:{id:'store-new',merchant_id:approvedMerchant.id,village_id:village.id,service_area_id:serviceArea.id,...request.postDataJSON(),is_active:true}});
    if(path==='/cart')return route.fulfill({json:{id:'cart-1',items:[],subtotal:'0'}});
    if(path==='/payments/config')return route.fulfill({json:{enabled:false,provider:'razorpay',currency:'INR'}});
    if(path.startsWith('/products'))return route.fulfill({json:[]});
    return route.fulfill({status:404,json:{detail:`Unmocked E2E API route: ${method} ${path}`}});
  });
}
