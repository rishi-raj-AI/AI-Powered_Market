import AxeBuilder from '@axe-core/playwright';
import {expect,test} from '@playwright/test';
import {customer,installApiMocks} from './helpers';

test.beforeEach(async({page})=>{await installApiMocks(page,customer)});

test('customer account exposes merchant onboarding without role confusion',async({page})=>{
  await page.goto('/account');
  await expect(page.getByRole('heading',{name:'Profile & business'})).toBeVisible();
  await expect(page.getByText(customer.phone)).toBeVisible();
  await expect(page.getByText('customer',{exact:true})).toBeVisible();
  await expect(page.getByText('Become a local merchant')).toBeVisible();
  await expect(page.getByRole('button',{name:'Apply as merchant'})).toBeVisible();

  await page.getByRole('button',{name:'Apply as merchant'}).click();
  await expect(page.getByText('Enter your business or shop name.')).toBeVisible();

  await page.getByLabel(/Business \/ shop name/).fill('Nimbu Kirana');
  await page.getByRole('button',{name:'Apply as merchant'}).click();
  await expect(page.getByText('Merchant application submitted. Your account is now waiting for admin approval.')).toBeVisible();
  await expect(page.getByText('Status: pending')).toBeVisible();
});

test('@a11y customer account has no serious accessibility violations',async({page})=>{
  await page.goto('/account');
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
});

test('account layout avoids horizontal overflow on narrow mobile',async({page})=>{
  await page.setViewportSize({width:360,height:800});
  await page.goto('/account');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
  expect(overflow).toBe(false);
});
