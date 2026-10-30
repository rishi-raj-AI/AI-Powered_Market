import {expect,test} from '@playwright/test';
import {installApiMocks} from './helpers';

for(const result of ['disabled','no-address'] as const){
 test(`GPS preserves serviceability and landmark when geocoding is ${result}`,async({page})=>{
  await installApiMocks(page);
  await page.addInitScript(()=>{
   Object.defineProperty(navigator,'geolocation',{value:{
    getCurrentPosition:(ok:any)=>ok({coords:{latitude:20.0778,longitude:74.1118}}),
   }});
  });
  await page.route('**/api/v1/location/reverse**',route=>result==='disabled'
   ?route.fulfill({status:503,json:{detail:'Google Maps services are not configured'}})
   :route.fulfill({json:null}));
  await page.goto('/checkout');
  await expect(page.getByRole('button',{name:'Logout'})).toBeVisible();
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.locator('#checkout-landmark').fill('Temple entrance');
  await page.getByRole('button',{name:'Current location',exact:true}).click();
  await expect(page.getByText(/Delivery available in Niphad Local/)).toBeVisible();
  await expect(page.locator('#checkout-landmark')).toHaveValue('Temple entrance');
  await expect(page.getByText(/Keep or enter your landmark manually/)).toBeVisible();
 });
}
