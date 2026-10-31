import {expect, test} from '@playwright/test';
import {installApiMocks, normalAdmin, superAdmin} from './helpers';

const endpoint = 'http://localhost:8000/api/v1/admin/users/onboard';

test('super admin can pre-register a rider without marking the account verified', async ({page}) => {
  await installApiMocks(page, superAdmin);
  let submitted: Record<string, unknown> | null = null;
  await page.route(endpoint, async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({status: 201, json: {
      id: 'new-rider', phone: '+919876543210', full_name: 'New Rider',
      role: 'delivery', is_active: true, is_verified: false,
      created_at: '2026-11-01T00:00:00Z',
    }});
  });

  await page.goto('/admin');
  await expect(page.getByRole('heading', {name: 'Pre-register customer, merchant or rider'})).toBeVisible();
  await page.getByRole('textbox', {name: 'New user name'}).fill('New Rider');
  await page.getByRole('textbox', {name: 'New user phone'}).fill('+919876543210');
  await page.getByRole('combobox', {name: 'New user role'}).selectOption('delivery');
  await page.getByRole('button', {name: 'Pre-register'}).click();

  await expect(page.getByText('Account pre-registered. User must verify their phone at sign-in before accessing GaonOne.')).toBeVisible();
  expect(submitted).toEqual({phone: '+919876543210', full_name: 'New Rider', role: 'delivery'});
});

test('normal admin cannot access elevated account creation controls', async ({page}) => {
  await installApiMocks(page, normalAdmin);
  await page.goto('/admin');
  await expect(page.getByRole('heading', {name: 'Admin dashboard'})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Pre-register customer, merchant or rider'})).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Pre-register'})).toHaveCount(0);
});
