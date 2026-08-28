import {Page} from '@playwright/test';

export type MockUser={
  id:string;phone:string;full_name?:string;role:'customer'|'merchant'|'delivery'|'admin';
  is_super_admin?:boolean;is_active:boolean;is_verified:boolean;created_at:string;
};

export const customer:MockUser={id:'user-customer',phone:'+919284800336',full_name:'Kiran',role:'customer',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const superAdmin:MockUser={id:'user-super',phone:'+917249723727',full_name:'Rushikesh',role:'admin',is_super_admin:true,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const normalAdmin:MockUser={id:'user-admin',phone:'+919111111111',full_name:'Pilot Admin',role:'admin',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};
export const riderCandidate:MockUser={id:'user-rider',phone:'+917774877196',full_name:'Bhushan',role:'customer',is_super_admin:false,is_active:true,is_verified:true,created_at:'2026-08-28T00:00:00Z'};

const overview={
  users:4,villages:1,active_stores:1,
  merchants:{pending:1,approved:0,suspended:0},
  orders:{total:0,by_status:{placed:0,accepted:0,preparing:0,ready:0,out_for_delivery:0,delivered:0,cancelled:0}},
  operations:{low_stock_listings:0,ready_unassigned_deliveries:0,active_delivery_partners:0},
  paid_gmv:'0',gross_order_value:'0',
};

const merchant={id:'merchant-1',owner_user_id:'merchant-owner',business_name:'Nimbu Kirana',gstin:null,status:'pending',created_at:'2026-08-28T00:00:00Z'};

export async function installApiMocks(page:Page,currentUser:MockUser=customer){
  await page.addInitScript(()=>localStorage.setItem('gaonone_token','e2e-token'));
  await page.route('http://localhost:8000/api/v1/**',async route=>{
    const request=route.request();
    const url=new URL(request.url());
    const path=url.pathname.replace('/api/v1','');
    const method=request.method();

    if(path==='/users/me')return route.fulfill({json:currentUser});
    if(path==='/admin/overview')return route.fulfill({json:overview});
    if(path==='/admin/users')return route.fulfill({json:[superAdmin,normalAdmin,riderCandidate,customer]});
    if(path==='/merchants')return route.fulfill({json:[merchant]});
    if(path==='/notifications/flush'&&method==='POST')return route.fulfill({json:{events:0,pushes:0}});
    if(path.startsWith('/admin/users/')&&path.endsWith('/role')&&method==='PATCH'){
      const id=path.split('/')[3];
      const payload=request.postDataJSON() as {role:MockUser['role'];is_active:boolean};
      const source=[superAdmin,normalAdmin,riderCandidate,customer].find(user=>user.id===id)??customer;
      return route.fulfill({json:{...source,role:payload.role,is_active:payload.is_active}});
    }
    if(path.startsWith('/merchants/')&&path.endsWith('/status')&&method==='PATCH')return route.fulfill({json:{...merchant,status:'approved'}});
    if(path==='/merchants/apply'&&method==='POST')return route.fulfill({json:merchant});
    if(path==='/villages'||path==='/service-areas'||path==='/categories'||path==='/stores'||path==='/orders/me'||path==='/notifications/me'||path==='/addresses/me')return route.fulfill({json:[]});
    if(path.startsWith('/products'))return route.fulfill({json:[]});
    return route.fulfill({status:404,json:{detail:`Unmocked E2E API route: ${method} ${path}`}});
  });
}
