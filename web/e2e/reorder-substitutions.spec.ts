import {expect,test} from '@playwright/test';
import {installApiMocks} from './helpers';

test('customer explicitly chooses a same-store alternative',async({page})=>{
  await installApiMocks(page);
  const store={id:'store-nearby',merchant_id:'merchant-approved',village_id:'village-niphad',name:'Niphad Daily Needs',slug:'niphad-daily-needs',landmark:'Bus Stand',delivery_enabled:true,pickup_enabled:true,is_active:true,is_open_now:true};
  const product={id:'listing-rice',store_id:store.id,product_id:'product-rice',price:'72.50',stock_quantity:2,is_available:true,product:{id:'product-rice',category_id:'category-rice',name:'Kolam Rice',unit:'1 kg'}};
  await page.route('http://localhost:8000/api/v1/stores/store-nearby',route=>route.fulfill({json:store}));
  await page.route('http://localhost:8000/api/v1/stores/store-nearby/products',route=>route.fulfill({json:[product]}));
  await page.route('http://localhost:8000/api/v1/store-products/listing-rice/substitutions',route=>route.fulfill({json:[{listing_id:'listing-basmati',product_id:'product-basmati',name:'Basmati Rice',unit:'1 kg',price:'80.00',price_delta:'7.50',score:0.9}]}));
  await page.route('http://localhost:8000/api/v1/cart/items',route=>route.fulfill({json:{id:'cart-1',store_id:store.id,subtotal:'80.00',items:[]}}));
  await page.goto('/market/store-nearby');
  await page.getByRole('button',{name:'Alternatives'}).click();
  await expect(page.getByText('Nothing is substituted automatically.')).toBeVisible();
  await expect(page.getByText('Basmati Rice')).toBeVisible();
  await page.getByRole('button',{name:'Choose'}).click();
  await expect(page.getByText('Chosen alternative added to cart.')).toBeVisible();
});

test('delivered order exposes current-stock reorder preview before cart mutation',async({page})=>{
  await installApiMocks(page);
  const order={id:'order-delivered',order_number:'GO-DELIVERED',user_id:'user-customer',store_id:'store-nearby',address_id:'address-niphad',status:'delivered',payment_method:'cod',payment_status:'paid',subtotal:'145.00',delivery_fee:'37.50',total:'182.50',created_at:'2026-08-30T10:00:00Z',updated_at:'2026-08-30T11:00:00Z'};
  await page.route('http://localhost:8000/api/v1/orders/me',route=>route.fulfill({json:[order]}));
  await page.route('http://localhost:8000/api/v1/orders/order-delivered',route=>route.fulfill({json:{...order,store_name:'Niphad Daily Needs',customer_landmark:'Main Road',items:[{id:'item-1',product_id:'product-rice',product_name:'Kolam Rice',unit:'1 kg',unit_price:'72.50',quantity:2,line_total:'145.00'}]}}));
  await page.route('http://localhost:8000/api/v1/orders/order-delivered/refund',route=>route.fulfill({status:404,json:{detail:'Not found'}}));
  await page.route('http://localhost:8000/api/v1/orders/order-delivered/reorder-preview',route=>route.fulfill({json:{order_id:order.id,store_id:order.store_id,store_available:true,available_items:1,unavailable_items:0,estimated_subtotal:'160.00',items:[{product_id:'product-rice',product_name:'Kolam Rice',requested_quantity:2,available_quantity:2,listing_id:'listing-rice',previous_unit_price:'72.50',current_unit_price:'80.00',available:true}]}}));
  await page.goto('/orders');
  await page.getByLabel('Toggle order detail').click();
  await expect(page.getByText('Buy this basket again')).toBeVisible();
  await page.getByRole('button',{name:'Preview reorder'}).click();
  await expect(page.getByText(/1 available.*estimated subtotal ₹160.00/)).toBeVisible();
});
