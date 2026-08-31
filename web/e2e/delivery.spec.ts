import AxeBuilder from '@axe-core/playwright';
import {expect,test} from '@playwright/test';
import {activeRider,installApiMocks} from './helpers';

test('rider sees assigned job, navigation and live GPS controls',async({page,context})=>{
  await installApiMocks(page,activeRider);
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({latitude:20.079,longitude:74.113});
  await page.goto('/delivery');
  await expect(page.getByRole('heading',{name:'Delivery operations'})).toBeVisible();
  await expect(page.getByText('GO260829000002')).toBeVisible();
  await expect(page.getByRole('button',{name:'Share live location'})).toBeVisible();
  await page.getByRole('button',{name:'Share live location'}).click();
  await expect(page.getByText(/Sharing live/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Stop sharing'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Mark picked up'})).toBeVisible();
});

test('an open job offer withholds the customer until it is claimed',async({page})=>{
  await installApiMocks(page,activeRider);
  await page.goto('/delivery');
  // The offer for the unclaimed job renders the offer card, which carries the
  // store, a coarse drop-off and the value — never the customer's identity.
  await expect(page.getByText('GO260829000001')).toBeVisible();
  await expect(page.getByText('Full delivery address is shared once you claim this job.')).toBeVisible();
  await expect(page.getByRole('button',{name:'Claim job'})).toBeVisible();
});

test('rider gets actionable message when geolocation permission is denied',async({page})=>{
  await installApiMocks(page,activeRider);
  await page.addInitScript(()=>{
    Object.defineProperty(navigator,'geolocation',{value:{
      watchPosition:(_ok:unknown,error:(value:{code:number;message:string})=>void)=>{setTimeout(()=>error({code:1,message:'Permission denied'}),0);return 1;},
      clearWatch:()=>{},
    }});
  });
  await page.goto('/delivery');
  await page.getByRole('button',{name:'Share live location'}).click();
  await expect(page.getByText(/Location permission denied/)).toBeVisible();
});

test('@a11y rider workspace has no serious accessibility violations',async({page})=>{
  await installApiMocks(page,activeRider);
  await page.goto('/delivery');
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
});

test('rider workspace avoids horizontal page overflow on mobile',async({page})=>{
  await installApiMocks(page,activeRider);
  await page.setViewportSize({width:390,height:844});
  await page.goto('/delivery');
  const pageOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
  expect(pageOverflow).toBe(false);
});
