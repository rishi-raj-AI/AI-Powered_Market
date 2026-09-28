import {expect,test} from '@playwright/test';
import {installApiMocks} from './helpers';

const cart={id:'cart-quote',store_id:'store-nearby',subtotal:'145.00',items:[{id:'cart-item',store_product_id:'listing-rice',quantity:2,store_product:{id:'listing-rice',store_id:'store-nearby',product_id:'product-rice',price:'72.50',stock_quantity:8,is_available:true,product:{id:'product-rice',category_id:'category-rice',name:'Kolam Rice',unit:'1 kg'}}}]};
const address={id:'address-niphad',village_id:'village-niphad',label:'Home',landmark:'Niphad Main Road',latitude:20.0778,longitude:74.1118,is_default:true};

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
