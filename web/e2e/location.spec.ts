import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {installApiMocks,merchantUser} from './helpers';

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
  await page.getByPlaceholder(/Search products, categories or stores nearby/i).fill('Rice');
  await expect(page.getByText('Kolam Rice')).toBeVisible();
  await expect(page.getByText('Gaon Fresh • 1 kg')).toBeVisible();
  await expect(page.getByText('0.8 km').first()).toBeVisible();
  await expect(page.getByText('Open now').first()).toBeVisible();
});

test('market applies a location selected without leaving the current page',async({page})=>{
  await installApiMocks(page);
  await page.goto('/market');
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
