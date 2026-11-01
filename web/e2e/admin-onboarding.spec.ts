import {expect, test} from '@playwright/test';
import {installApiMocks, normalAdmin, superAdmin} from './helpers';

const endpoint = 'http://localhost:8000/api/v1/admin/users/onboard';
const configEndpoint = `${endpoint}/config`;

test('super admin can pre-register a rider only when verified phone onboarding is configured', async ({page}) => {
  await installApiMocks(page, superAdmin);
  await page.route(configEndpoint, route => route.fulfill({json: {enabled: true}}));
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
  await expect(page.getByRole('button', {name: 'Pre-register'})).toBeEnabled();
  await page.getByRole('textbox', {name: 'New user name'}).fill('New Rider');
  await page.getByRole('textbox', {name: 'New user phone'}).fill('+919876543210');
  await page.getByRole('combobox', {name: 'New user role'}).selectOption('delivery');
  await page.getByRole('button', {name: 'Pre-register'}).click();

  await expect(page.getByText('Phone account pre-registered. The user must sign in through verified phone authentication; Google sign-in will not link this record.')).toBeVisible();
  expect(submitted).toEqual({phone: '+919876543210', full_name: 'New Rider', role: 'delivery'});
});

test('super admin cannot pre-register a phone account when phone authentication is unavailable', async ({page}) => {
  await installApiMocks(page, superAdmin);
  await page.route(configEndpoint, route => route.fulfill({json: {enabled: false}}));
  let posted = false;
  await page.route(endpoint, route => {posted = true; return route.fulfill({status: 500, json: {detail: 'Should not be called'}})});
  await page.goto('/admin');
  await expect(page.getByRole('heading', {name: 'Pre-register customer, merchant or rider'})).toBeVisible();
  await expect(page.getByText(/Phone pre-registration is unavailable with the configured sign-in method/)).toBeVisible();
  await expect(page.getByRole('button', {name: 'Pre-register'})).toBeDisabled();
  expect(posted).toBe(false);
});

test('normal admin cannot access elevated account creation controls', async ({page}) => {
  await installApiMocks(page, normalAdmin);
  await page.goto('/admin');
  await expect(page.getByRole('heading', {name: 'Admin dashboard'})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Pre-register customer, merchant or rider'})).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Pre-register'})).toHaveCount(0);
});
