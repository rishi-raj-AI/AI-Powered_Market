import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {installApiMocks,merchantUser} from './helpers';

test('customer can discover and verify an exact delivery location',async({page})=>{
  await installApiMocks(page);
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  await page.getByLabel(/Service-area fallback/).selectOption('village-niphad');
  const search=page.getByPlaceholder(/Search area, road, landmark or address/i);
  await search.fill('Niphad');
  await expect(page.getByRole('button',{name:/Niphad.*Maharashtra/i})).toBeVisible();
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page.getByText(/Delivery available in Niphad Local/i)).toBeVisible();
  await expect(page.getByText(/Pinned coordinates:/i)).toBeVisible();
});

test('approved merchant can resolve a storefront and auto-select service area',async({page})=>{
  await installApiMocks(page,merchantUser);
  await page.goto('/merchant');
  await page.getByLabel('Store name').fill('Nimbu Kirana Niphad');
  await page.getByLabel('Village').selectOption('village-niphad');
  const search=page.getByPlaceholder(/Search area, road, landmark or address/i);
  await search.fill('Niphad');
  await page.getByRole('button',{name:/Niphad.*Maharashtra/i}).click();
  await expect(page.getByText(/Store is inside Niphad Local/i)).toBeVisible();
  await expect(page.getByLabel('Service area')).toHaveValue('area-niphad');
  await expect(page.getByLabel(/Landmark/)).toHaveValue(/Niphad, Nashik/i);
});

test('@a11y location picker has no serious or critical accessibility violations',async({page})=>{
  await installApiMocks(page);
  await page.goto('/checkout');
  await page.getByRole('button',{name:/Add address/i}).click();
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  expect(results.violations.filter(v=>['serious','critical'].includes(v.impact||''))).toEqual([]);
});
