import { test, expect } from '@playwright/test';
import { dismissToasts } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    // Navigate first then clear auth state
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => localStorage.removeItem('auth_token'));
    await page.reload({ waitUntil: 'domcontentloaded' });
  });

  test('login page loads correctly', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('login-page')).toBeVisible();
    await expect(page.getByTestId('pin-input')).toBeVisible();
    await expect(page.getByTestId('login-button')).toBeVisible();
  });

  test('login button disabled when PIN is less than 4 digits', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('pin-input').fill('123');
    await expect(page.getByTestId('login-button')).toBeDisabled();
  });

  test('login button enabled when PIN is 4+ digits', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('pin-input').fill('1234');
    await expect(page.getByTestId('login-button')).toBeEnabled();
  });

  test('invalid PIN shows error message', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('pin-input').fill('9999');
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('error-message')).toBeVisible({ timeout: 10000 });
  });

  test('valid PIN logs in and redirects to dashboard', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('pin-input').fill(VALID_PIN);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
  });

  test('unauthenticated user redirected to login', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/.*login/);
  });
});

test.describe('Dashboard Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    // Login first
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('pin-input').fill(VALID_PIN);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
  });

  test('dashboard header is visible with key elements', async ({ page }) => {
    await expect(page.getByTestId('paper-mode-toggle')).toBeVisible();
    await expect(page.getByTestId('settings-button')).toBeVisible();
    await expect(page.getByTestId('logout-button')).toBeVisible();
  });

  test('dashboard shows stats cards', async ({ page }) => {
    await expect(page.getByTestId('wallet-balance-card')).toBeVisible();
    await expect(page.getByTestId('portfolio-value-card')).toBeVisible();
    await expect(page.getByTestId('total-pnl-card')).toBeVisible();
    await expect(page.getByTestId('win-rate-card')).toBeVisible();
  });

  test('tab navigation works - Token Scanner', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible({ timeout: 10000 });
  });

  test('tab navigation works - Active Trades', async ({ page }) => {
    await page.getByTestId('tab-trades').click();
    // The active trades tab should show content
    await expect(page.getByTestId('tab-trades')).toHaveAttribute('data-state', 'active');
  });

  test('logout button works', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) badge.remove();
    });
    await page.getByTestId('logout-button').click({ force: true });
    await expect(page).toHaveURL(/.*login/, { timeout: 10000 });
  });
});
