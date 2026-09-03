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
