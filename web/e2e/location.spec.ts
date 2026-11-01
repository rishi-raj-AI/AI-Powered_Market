import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {installApiMocks,merchantUser} from './helpers';

test('map initialization never silently chooses a delivery pin; a deliberate drag does',async({page})=>{
  await page.addInitScript(()=>{
    const callbacks:Record<string,()=>void>={};
    class FakeMap {
      center:{lat:number;lng:number};
      constructor(_element:unknown,options:{center:{lat:number;lng:number}}){
        this.center=options.center;
        (window as any).__mapCallbacks=callbacks;
      }
      addListener(event:string,callback:()=>void){
        callbacks[event]=callback;
        return {remove(){}};
      }
      getCenter(){return {lat:()=>this.center.lat,lng:()=>this.center.lng}}
      panTo(point:{lat:number;lng:number}){this.center=point}
    }
    (window as any).google={maps:{Map:FakeMap}};
  });
  await installApiMocks(page);
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await expect.poll(()=>page.evaluate(()=>Boolean((window as any).__mapCallbacks?.dragend))).toBe(true);
  // A map ready/idle event must never fabricate the default map centre as
  // a customer-confirmed entrance.
  await page.evaluate(()=>(window as any).__mapCallbacks.idle?.());
  await expect(page.getByText(/Pinned coordinates:/)).toHaveCount(0);
  await page.evaluate(()=>(window as any).__mapCallbacks.dragend());
  await expect(page.getByText(/Pinned coordinates:/)).toBeVisible();
});

test('customer can discover and verify an exact delivery location',async({page})=>{
  await installApiMocks(page);
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.getByLabel('Area / locality *').selectOption('village-niphad');
  const search=page.getByPlaceholder(/Search area, road, landmark or address/i);
  await search.fill('Niphad');
  await expect(page.getByRole('button',{name:/Niphad.*Maharashtra/i})).toBeVisible();
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page.getByText(/Delivery available in Niphad Local/i)).toBeVisible();
  await expect(page.getByText(/Pinned coordinates:/i)).toBeVisible();
});

test('approved merchant can resolve a storefront with area-first location language',async({page})=>{
  await installApiMocks(page,merchantUser);
  await page.goto('/merchant');
  const locality=page.getByLabel('Area / locality');
  await expect(locality).toBeVisible();
  await expect(page.getByLabel('Village')).toHaveCount(0);
  await expect(locality.locator('option').first()).toHaveText('Select area / locality');
  await page.getByLabel('Store name').fill('Nimbu Kirana Niphad');
  await locality.selectOption('village-niphad');
  const search=page.getByPlaceholder(/Search area, road, landmark or address/i);
  await search.fill('Niphad');
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page.getByText(/Store is inside Niphad Local/i)).toBeVisible();
  await expect(page.getByLabel('Service area')).toHaveValue('area-niphad');
  await expect(page.getByLabel(/Landmark/)).toHaveValue(/Niphad, Nashik/i);
});

test('market preserves location context and searches nearby live inventory',async({page})=>{
  await installApiMocks(page);
  await page.goto('/market?lat=20.0778&lng=74.1118&location=Niphad%20Local&serviceable=1&service_area=Niphad%20Local');
  await expect(page.getByText('Serviceable through')).toBeVisible();
  await expect(page.getByText('Niphad Local',{exact:true}).last()).toBeVisible();
  await expect(page.getByText('Niphad Daily Needs',{exact:true})).toBeVisible();
  await page.getByPlaceholder(/Search products, categories or stores nearby/i).fill('Rice');
  await expect(page.getByText('Kolam Rice')).toBeVisible();
  await expect(page.getByText('Gaon Fresh • 1 kg')).toBeVisible();
  await expect(page.getByText('0.8 km').first()).toBeVisible();
  await expect(page.getByText('Open now').first()).toBeVisible();
});

test('market applies a location selected without leaving the current page',async({page})=>{
  await installApiMocks(page);
  await page.goto('/market');
  await expect(page.getByRole('button',{name:'Logout'})).toBeVisible();
  const search=page.getByLabel('Search location');
  await search.fill('Niphad');
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page).toHaveURL(/\/market\?lat=20\.0778&lng=74\.1118/);
  await expect(page.getByText('Serviceable through')).toBeVisible();
  await expect(page.getByText('Niphad Local',{exact:true}).last()).toBeVisible();
});

test('market location autocomplete ignores an older response after input changes',async({page})=>{
  await installApiMocks(page);
  let releaseOlder!:()=>void;
  let olderRequested!:()=>void;
  let olderFinished!:()=>void;
  const olderResponse=new Promise<void>(resolve=>{releaseOlder=resolve});
  const olderRequest=new Promise<void>(resolve=>{olderRequested=resolve});
  const olderComplete=new Promise<void>(resolve=>{olderFinished=resolve});
  await page.route('**/api/v1/location/autocomplete**',async route=>{
    const query=new URL(route.request().url()).searchParams.get('q');
    if(query==='Nip'){
      olderRequested();
      await olderResponse;
      await route.fulfill({json:[{place_id:'older',text:'Older locality, Maharashtra',main_text:'Older locality',secondary_text:'Maharashtra'}]});
      olderFinished();
      return;
    }
    await route.fulfill({json:[{place_id:'latest',text:'Latest Niphad locality, Maharashtra',main_text:'Latest Niphad locality',secondary_text:'Maharashtra'}]});
  });
  await page.goto('/market');
  await expect(page.getByRole('button',{name:'Logout'})).toBeVisible();
  const search=page.getByLabel('Search location');
  await search.fill('Nip');
  await olderRequest;
  await search.fill('Niphad');
  await expect(page.getByRole('button',{name:/Latest Niphad locality, Maharashtra/i})).toBeVisible();
  releaseOlder();
  await olderComplete;
  await expect(page.getByRole('button',{name:/Older locality, Maharashtra/i})).toHaveCount(0);
});

test('market keeps newly typed intent when an older selected place resolves late',async({page})=>{
  await installApiMocks(page);
  let releasePlace!:()=>void;
  let placeRequested!:()=>void;
  let placeFinished!:()=>void;
  const placeResponse=new Promise<void>(resolve=>{releasePlace=resolve});
  const placeRequest=new Promise<void>(resolve=>{placeRequested=resolve});
  const placeComplete=new Promise<void>(resolve=>{placeFinished=resolve});
  await page.route('**/api/v1/location/place/place-niphad**',async route=>{
    placeRequested();
    await placeResponse;
    await route.fulfill({json:{place_id:'place-niphad',formatted_address:'Niphad, Nashik, Maharashtra 422303, India',latitude:20.0778,longitude:74.1118}});
    placeFinished();
  });
  await page.goto('/market');
  await expect(page.getByRole('button',{name:'Logout'})).toBeVisible();
  const search=page.getByLabel('Search location');
  await search.fill('Niphad');
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await placeRequest;
  await search.fill('Nashik');
  releasePlace();
  await placeComplete;
  await expect(page).toHaveURL(/\/market$/);
});

test('customer address autocomplete ignores an older response after input changes',async({page})=>{
  await installApiMocks(page);
  let releaseOlder!:()=>void;
  let olderRequested!:()=>void;
  let olderFinished!:()=>void;
  const olderResponse=new Promise<void>(resolve=>{releaseOlder=resolve});
  const olderRequest=new Promise<void>(resolve=>{olderRequested=resolve});
  const olderComplete=new Promise<void>(resolve=>{olderFinished=resolve});
  await page.route('**/api/v1/location/autocomplete**',async route=>{
    const query=new URL(route.request().url()).searchParams.get('q');
    if(query==='Nip'){
      olderRequested();
      await olderResponse;
      await route.fulfill({json:[{place_id:'older',text:'Older delivery locality, Maharashtra',main_text:'Older delivery locality',secondary_text:'Maharashtra'}]});
      olderFinished();
      return;
    }
    await route.fulfill({json:[{place_id:'latest',text:'Latest Niphad delivery locality, Maharashtra',main_text:'Latest Niphad delivery locality',secondary_text:'Maharashtra'}]});
  });
  await page.goto('/checkout');
  await expect(page.getByRole('button',{name:'Logout'})).toBeVisible();
  await page.getByRole('button',{name:/Add address/i}).click();
  const search=page.getByLabel('Search delivery location');
  await search.fill('Nip');
  await olderRequest;
  await search.fill('Niphad');
  await expect(page.getByRole('button',{name:/Latest Niphad delivery locality/i})).toBeVisible();
  releaseOlder();
  await olderComplete;
  await expect(page.getByRole('button',{name:/Older delivery locality/i})).toHaveCount(0);
});

test('market keeps the latest nearby discovery when an older search resolves late',async({page})=>{
  await installApiMocks(page);
  let releaseRice!:()=>void;
  let riceRequested!:()=>void;
  let riceFinished!:()=>void;
  const riceResponse=new Promise<void>(resolve=>{releaseRice=resolve});
  const riceRequest=new Promise<void>(resolve=>{riceRequested=resolve});
  const riceComplete=new Promise<void>(resolve=>{riceFinished=resolve});
  await page.route('**/api/v1/discovery/search**',async route=>{
    const query=new URL(route.request().url()).searchParams.get('q')||'';
    const result=(name:string,listingId:string)=>({query,latitude:20.0778,longitude:74.1118,radius_km:20,stores:[{id:'store-nearby',name:'Niphad Daily Needs',delivery_enabled:true,distance_km:0.8,match_score:4.9}],categories:[],products:[{listing_id:listingId,product_id:`product-${listingId}`,store_id:'store-nearby',store_name:'Niphad Daily Needs',name,unit:'1 kg',price:'72.50',distance_km:0.8,match_score:4.9}]});
    if(query==='Rice'){
      riceRequested();
      await riceResponse;
      await route.fulfill({json:result('Stale Rice','stale-rice')});
      riceFinished();
      return;
    }
    await route.fulfill({json:result('Fresh Flour','fresh-flour')});
  });
  await page.goto('/market?lat=20.0778&lng=74.1118&location=Niphad%20Local&serviceable=1&service_area=Niphad%20Local');
  await expect(page.getByRole('button',{name:'Logout'})).toBeVisible();
  const search=page.getByPlaceholder(/Search products, categories or stores nearby/i);
  await search.fill('Rice');
  await riceRequest;
  await search.fill('Flour');
  await expect(page.getByText('Fresh Flour',{exact:true})).toBeVisible();
  releaseRice();
  await riceComplete;
  await expect(page.getByText('Stale Rice',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Fresh Flour',{exact:true})).toBeVisible();
});

test('storefront exposes backend-computed India-local availability',async({page})=>{
  await installApiMocks(page);
  await page.goto('/market/store-nearby');
  await expect(page.getByText('Open now')).toBeVisible();
  await expect(page.getByText(/IST/)).toBeVisible();
  await expect(page.getByText(/village/i)).toHaveCount(0);
});

test('@a11y location picker has no serious or critical accessibility violations',async({page})=>{
  await installApiMocks(page);
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(v=>['serious','critical'].includes(v.impact||''))).toEqual([]);
});


test('selecting a locality does not silently use its hub as the delivery entrance',async({page})=>{
  await installApiMocks(page);
  let created=0;
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>{
    if(route.request().method()==='POST')created++;
    return route.fulfill({json:[]});
  });
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.getByLabel('Area / locality *').selectOption('village-niphad');
  await page.locator('#checkout-landmark').fill('Temple gate');
  await expect(page.getByText(/Pinned coordinates:/)).toHaveCount(0);
  await page.getByRole('button',{name:'Save address'}).click();
  await expect(page.getByText('Pin the exact delivery location before saving.')).toBeVisible();
  expect(created).toBe(0);
});


test('changing locality invalidates a previously pinned entrance',async({page})=>{
  await installApiMocks(page);
  await page.route('http://localhost:8000/api/v1/villages',route=>route.fulfill({json:[
    {id:'village-niphad',name:'Niphad',district:'Nashik',state:'Maharashtra',pincode:'422303',latitude:20.0778,longitude:74.1118,is_active:true},
    {id:'village-other',name:'Other Locality',district:'Nashik',state:'Maharashtra',pincode:'422304',latitude:20.15,longitude:74.20,is_active:true},
  ]}));
  let created=0;
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>{
    if(route.request().method()==='POST')created++;
    return route.fulfill({json:[]});
  });
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.getByLabel('Area / locality *').selectOption('village-niphad');
  await page.getByLabel('Search delivery location').fill('Niphad');
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page.getByText(/Pinned coordinates:/)).toBeVisible();
  await page.getByLabel('Area / locality *').selectOption('village-other');
  await expect(page.getByText(/Pinned coordinates:/)).toHaveCount(0);
  await page.locator('#checkout-landmark').fill('New entrance');
  await page.getByRole('button',{name:'Save address'}).click();
  await expect(page.getByText('Pin the exact delivery location before saving.')).toBeVisible();
  expect(created).toBe(0);
});


test('a delayed old-locality geocode cannot restore a stale checkout pin',async({page})=>{
  await installApiMocks(page);
  await page.route('http://localhost:8000/api/v1/villages',route=>route.fulfill({json:[
    {id:'village-niphad',name:'Niphad',district:'Nashik',state:'Maharashtra',pincode:'422303',latitude:20.0778,longitude:74.1118,is_active:true},
    {id:'village-other',name:'Other Locality',district:'Nashik',state:'Maharashtra',pincode:'422304',latitude:20.15,longitude:74.20,is_active:true},
  ]}));
  let releasePlace!:()=>void;
  const holdPlace=new Promise<void>(resolve=>{releasePlace=resolve});
  let signalPlace!:()=>void;
  const placeStarted=new Promise<void>(resolve=>{signalPlace=resolve});
  let signalPlaceFinished!:()=>void;
  const placeFinished=new Promise<void>(resolve=>{signalPlaceFinished=resolve});
  await page.route('**/api/v1/location/place/place-niphad**',async route=>{
    signalPlace();
    await holdPlace;
    await route.fulfill({json:{place_id:'place-niphad',formatted_address:'Niphad, Nashik, Maharashtra 422303, India',latitude:20.0778,longitude:74.1118}});
    signalPlaceFinished();
  });
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.getByLabel('Area / locality *').selectOption('village-niphad');
  await page.getByLabel('Search delivery location').fill('Niphad');
  const suggestion=page.getByRole('button',{name:/Niphad.*Maharashtra/i});
  await expect(suggestion).toBeVisible();
  await suggestion.click();
  await placeStarted;
  await page.getByLabel('Area / locality *').selectOption('village-other');
  releasePlace();
  await placeFinished;
  await expect(page.getByText(/Pinned coordinates:/)).toHaveCount(0);
});

test('searched place centroid is not a confirmed doorstep until a deliberate map drag',async({page})=>{
  await page.addInitScript(()=>{
    const callbacks:Record<string,()=>void>={};
    class FakeMap {
      center:{lat:number;lng:number};
      constructor(_element:unknown,options:{center:{lat:number;lng:number}}){
        this.center=options.center;
        (window as any).__mapCallbacks=callbacks;
      }
      addListener(event:string,callback:()=>void){callbacks[event]=callback;return {remove(){}}}
      getCenter(){return {lat:()=>this.center.lat,lng:()=>this.center.lng}}
      panTo(point:{lat:number;lng:number}){this.center=point}
    }
    (window as any).google={maps:{Map:FakeMap}};
  });
  await installApiMocks(page);
  let writes=0;
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>{
    if(route.request().method()!=='POST')return route.fulfill({json:[]});
    writes++;
    const payload=route.request().postDataJSON();
    return route.fulfill({status:201,json:{...payload,id:'confirmed-address',user_id:'user-customer',created_at:'2026-11-02T00:00:00Z',updated_at:'2026-11-02T00:00:00Z'}});
  });
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.getByLabel('Area / locality *').selectOption('village-niphad');
  await page.getByLabel('Search delivery location').fill('Niphad');
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page.getByText(/Search results are approximate/)).toBeVisible();
  await page.getByRole('button',{name:'Save address'}).click();
  await expect(page.getByText(/Move the map to your doorstep or use GPS to confirm before saving/)).toBeVisible();
  expect(writes).toBe(0);
  await expect.poll(()=>page.evaluate(()=>Boolean((window as any).__mapCallbacks?.dragend))).toBe(true);
  await page.evaluate(()=>(window as any).__mapCallbacks.dragend());
  await expect(page.getByText('Delivery pin confirmed by map selection.')).toBeVisible();
  await page.getByRole('button',{name:'Save address'}).click();
  await expect.poll(()=>writes).toBe(1);
});

test('legacy coordinates are never labelled as a confirmed customer pin',async({page})=>{
  await installApiMocks(page);
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>route.fulfill({json:[{
    id:'legacy-address',village_id:'village-niphad',label:'Home',landmark:'School',
    latitude:20.0778,longitude:74.1118,is_default:true,location_source:null,
    location_confirmed_at:null,
  }]}));
  await page.goto('/checkout');
  await expect(page.getByText('Saved coordinates (confirmation unrecorded)')).toBeVisible();
  await expect(page.getByText('Confirmed delivery pin')).toHaveCount(0);
});
