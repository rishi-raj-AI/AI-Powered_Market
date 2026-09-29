import {expect,test} from '@playwright/test';
import {installApiMocks} from './helpers';

const cart={id:'cart-quote',store_id:'store-nearby',subtotal:'145.00',items:[{id:'cart-item',store_product_id:'listing-rice',quantity:2,store_product:{id:'listing-rice',store_id:'store-nearby',product_id:'product-rice',price:'72.50',stock_quantity:8,is_available:true,product:{id:'product-rice',category_id:'category-rice',name:'Kolam Rice',unit:'1 kg'}}}]};
const address={id:'address-niphad',village_id:'village-niphad',label:'Home',landmark:'Niphad Main Road',latitude:20.0778,longitude:74.1118,is_default:true};

test('cart serializes mutations while an authoritative update is pending',async({page})=>{
  await installApiMocks(page);
  const flour={id:'cart-item-flour',store_product_id:'listing-flour',quantity:1,store_product:{id:'listing-flour',store_id:'store-nearby',product_id:'product-flour',price:'32.50',stock_quantity:6,is_available:true,product:{id:'product-flour',category_id:'category-flour',name:'Fresh Flour',unit:'1 kg'}}};
  const initial={...cart,subtotal:'105.00',items:[{...cart.items[0],quantity:1},flour]};
  const afterRice={...initial,subtotal:'177.50',items:[{...initial.items[0],quantity:2},flour]};
  let releaseRice!:()=>void;
  let riceUpdateRequested!:()=>void;
  const riceResponse=new Promise<void>(resolve=>{releaseRice=resolve});
  const riceRequest=new Promise<void>(resolve=>{riceUpdateRequested=resolve});
  await page.route('http://localhost:8000/api/v1/cart',route=>route.fulfill({json:initial}));
  await page.route('http://localhost:8000/api/v1/cart/items',async route=>{
    const payload=route.request().postDataJSON() as {store_product_id:string;quantity:number};
    if(payload.store_product_id==='listing-rice'){
      riceUpdateRequested();
      await riceResponse;
      await route.fulfill({json:afterRice});
      return;
    }
    await route.fulfill({json:initial});
  });

  await page.goto('/cart');
  const riceIncrease=page.getByRole('button',{name:'Increase Kolam Rice quantity'});
  const flourIncrease=page.getByRole('button',{name:'Increase Fresh Flour quantity'});
  await riceIncrease.click();
  await riceRequest;
  await expect(page.locator('main')).toHaveAttribute('aria-busy','true');
  await expect(riceIncrease).toBeDisabled();
  await expect(flourIncrease).toBeDisabled();
  await expect(page.getByRole('button',{name:'Clear cart'})).toBeDisabled();
  await expect(page.getByRole('button',{name:'Updating cart…'})).toBeDisabled();
  releaseRice();
  await expect(page.locator('main')).toHaveAttribute('aria-busy','false');
  await expect(page.getByLabel('Kolam Rice quantity',{exact:true})).toHaveText('2');
  await expect(page.getByLabel('Fresh Flour quantity',{exact:true})).toHaveText('1');
});

test('cart and checkout never invent a client-side delivery fee',async({page})=>{
  await installApiMocks(page);
  await page.route('http://localhost:8000/api/v1/cart',route=>route.fulfill({json:cart}));
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>route.fulfill({json:[address]}));
  await page.route('http://localhost:8000/api/v1/cart/quote**',route=>route.fulfill({json:{store_id:'store-nearby',address_id:address.id,subtotal:'145.00',delivery_fee:'37.50',total:'182.50',serviceable:true,inventory_valid:true,store_open:true,checkout_ready:true,blockers:[]}}));

  await page.goto('/cart');
  await expect(page.getByText('Calculated at checkout')).toBeVisible();
  await expect(page.getByText('₹20.00')).toHaveCount(0);

  await page.goto('/checkout');
  await expect(page.getByText('₹37.50')).toBeVisible();
  await expect(page.getByText('₹182.50')).toBeVisible();
  await expect(page.getByRole('button',{name:'Place order'})).toBeEnabled();
});

test('checkout keeps the quote for the currently selected address when an older quote resolves late',async({page})=>{
  await installApiMocks(page);
  const workAddress={...address,id:'address-work',label:'Work',landmark:'Niphad Bus Stand',is_default:false};
  let releaseHome!:()=>void;
  let homeQuoteSeen!:()=>void;
  let homeQuoteFinished!:()=>void;
  const homeQuote=new Promise<void>(resolve=>{releaseHome=resolve});
  const homeQuoteRequested=new Promise<void>(resolve=>{homeQuoteSeen=resolve});
  const homeQuoteCompleted=new Promise<void>(resolve=>{homeQuoteFinished=resolve});
  await page.route('http://localhost:8000/api/v1/cart',route=>route.fulfill({json:cart}));
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>route.fulfill({json:[address,workAddress]}));
  await page.route('http://localhost:8000/api/v1/cart/quote**',async route=>{
    const addressId=new URL(route.request().url()).searchParams.get('address_id');
    if(addressId===address.id){
      homeQuoteSeen();
      await homeQuote;
      await route.fulfill({json:{store_id:'store-nearby',address_id:address.id,subtotal:'145.00',delivery_fee:'37.50',total:'182.50',serviceable:true,inventory_valid:true,store_open:true,checkout_ready:true,blockers:[]}});
      homeQuoteFinished();
      return;
    }
    await route.fulfill({json:{store_id:'store-nearby',address_id:workAddress.id,subtotal:'145.00',delivery_fee:'25.00',total:'170.00',serviceable:true,inventory_valid:true,store_open:true,checkout_ready:true,blockers:[]}});
  });

  await page.goto('/checkout');
  await homeQuoteRequested;
  await page.locator('input[name="address"]').nth(1).check();
  await expect(page.getByText('₹25.00')).toBeVisible();
  await expect(page.getByText('₹170.00')).toBeVisible();
  releaseHome();
  await homeQuoteCompleted;
  await expect(page.getByText('₹37.50')).toHaveCount(0);
  await expect(page.getByText('₹25.00')).toBeVisible();
  await expect(page.getByRole('button',{name:'Place order'})).toBeEnabled();
});

test('checkout serializes a pending address save',async({page})=>{
  await installApiMocks(page);
  await page.addInitScript(()=>{
    const fetch=window.fetch.bind(window);
    (window as typeof window&{addressSaveServiceabilityRequests:number}).addressSaveServiceabilityRequests=0;
    window.fetch=(input,init)=>{
      const url=typeof input==='string'?input:input instanceof Request?input.url:String(input);
      if(url.includes('/api/v1/location/serviceability'))(window as typeof window&{addressSaveServiceabilityRequests:number}).addressSaveServiceabilityRequests+=1;
      return fetch(input,init);
    };
  });
  const savedAddress={...address,id:'address-saved',landmark:'Temple gate'};
  let currentAddresses:typeof address[]=[];
  let createAttempts=0;
  let releaseCreate!:()=>void;
  let createStarted!:()=>void;
  const createRequest=new Promise<void>(resolve=>{createStarted=resolve});
  const createGate=new Promise<void>(resolve=>{releaseCreate=resolve});
  await page.route('http://localhost:8000/api/v1/cart',route=>route.fulfill({json:cart}));
  await page.route('http://localhost:8000/api/v1/addresses/me',async route=>{
    if(route.request().method()==='GET')return route.fulfill({json:currentAddresses});
    if(route.request().method()==='POST'){
      createAttempts+=1;
      createStarted();
      await createGate;
      currentAddresses=[savedAddress];
      await route.fulfill({status:201,json:savedAddress});
      return;
    }
    await route.fulfill({status:405});
  });
  await page.route('http://localhost:8000/api/v1/cart/quote**',route=>route.fulfill({json:{store_id:'store-nearby',address_id:savedAddress.id,subtotal:'145.00',delivery_fee:'37.50',total:'182.50',serviceable:true,inventory_valid:true,store_open:true,checkout_ready:true,blockers:[]}}));

  await page.goto('/checkout');
  const addAddress=page.getByRole('button',{name:'+ Add address'});
  await addAddress.click();
  await page.locator('#checkout-village').selectOption('village-niphad');
  await page.locator('#checkout-landmark').fill('Temple gate');
  const form=page.locator('form.formInset');
  const save=page.getByRole('button',{name:'Save address'});
  await save.click();
  await createRequest;
  await expect(form).toHaveAttribute('aria-busy','true');
  await expect(page.getByRole('button',{name:'Saving address…'})).toBeDisabled();
  await expect(addAddress).toBeDisabled();
  const secondSubmitWasPrevented=await form.evaluate(element=>!element.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  expect(secondSubmitWasPrevented).toBe(true);
  expect(await page.evaluate(()=>((window as typeof window&{addressSaveServiceabilityRequests:number}).addressSaveServiceabilityRequests))).toBe(1);
  expect(createAttempts).toBe(1);
  releaseCreate();
  await expect(addAddress).toBeEnabled();
  await expect(page.getByText('Temple gate')).toBeVisible();
  expect(createAttempts).toBe(1);
});

test('checkout reuses its idempotency key after an uncertain network failure',async({page})=>{
  await installApiMocks(page);
  const order={id:'order-idempotent',order_number:'GO260928COD01',user_id:'user-customer',store_id:'store-nearby',address_id:address.id,status:'placed',payment_method:'cod',payment_status:'pending',subtotal:'145.00',delivery_fee:'37.50',total:'182.50',created_at:'2026-09-28T16:00:00Z',updated_at:'2026-09-28T16:00:00Z'};
  const keys:string[]=[];
  let attempts=0;
  let releaseFirst!:()=>void;
  let firstStarted!:()=>void;
  const firstRequest=new Promise<void>(resolve=>{firstStarted=resolve});
  const firstGate=new Promise<void>(resolve=>{releaseFirst=resolve});
  await page.route('http://localhost:8000/api/v1/cart',route=>route.fulfill({json:cart}));
  await page.route('http://localhost:8000/api/v1/addresses/me',route=>route.fulfill({json:[address]}));
  await page.route('http://localhost:8000/api/v1/cart/quote**',route=>route.fulfill({json:{store_id:'store-nearby',address_id:address.id,subtotal:'145.00',delivery_fee:'37.50',total:'182.50',serviceable:true,inventory_valid:true,store_open:true,checkout_ready:true,blockers:[]}}));
  await page.route('http://localhost:8000/api/v1/orders/checkout',async route=>{
    keys.push(route.request().headers()['idempotency-key']||'');
    expect(route.request().postDataJSON()).toEqual({address_id:address.id,payment_method:'cod'});
    attempts+=1;
    if(attempts===1){firstStarted();await firstGate;await route.abort('connectionreset');return}
    await route.fulfill({status:201,json:order});
  });
  await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[order]}));

  await page.goto('/checkout');
  const place=page.getByRole('button',{name:'Place order'});
  await expect(place).toBeEnabled();
  await place.click();
  await firstRequest;
  await expect(page.getByRole('button',{name:'Placing order…'})).toBeDisabled();
  releaseFirst();
  await expect(place).toBeEnabled();
  await place.click();
  await page.waitForURL(/\/orders\?placed=GO260928COD01$/);
  await expect(page.getByText('Order GO260928COD01 placed successfully.')).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe('');
  expect(keys[1]).toBe(keys[0]);
});
