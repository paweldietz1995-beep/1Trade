import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Token Scanner', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('token scanner tab shows scanner component', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible();
  });

  test('token scanner has search input and refresh button', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-search')).toBeVisible();
    await expect(page.getByTestId('refresh-tokens')).toBeVisible();
  });

  test('token scanner loads and displays tokens', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    // Wait for tokens to load
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
  });

  test('token search filters tokens', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    // Wait for tokens to load first
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    
    // Search for something unlikely to match
    await page.getByTestId('token-search').fill('ZZZZUNLIKELYTOMATCH');
    // Should show no tokens or different count
    await expect(page.getByTestId('token-row-0')).not.toBeVisible({ timeout: 5000 });
  });

  test('refresh button reloads tokens', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('refresh-tokens')).toBeVisible();
    await page.getByTestId('refresh-tokens').click();
    // Spinner should appear briefly then stop
    await expect(page.getByTestId('token-scanner')).toBeVisible();
  });
});

test.describe('Trade Modal', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    // Navigate to Token Scanner and wait for tokens
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
  });

  test('clicking token row opens trade modal', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('trade-modal')).toBeVisible();
  });

  test('trade modal has buy and sell buttons', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('buy-button')).toBeVisible();
    await expect(page.getByTestId('sell-button')).toBeVisible();
  });

  test('trade modal has amount input', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('amount-input')).toBeVisible();
  });

  test('trade modal has TP and SL sliders', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('take-profit-slider')).toBeVisible();
    await expect(page.getByTestId('stop-loss-slider')).toBeVisible();
  });

  test('trade modal has paper mode toggle', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('paper-mode-switch')).toBeVisible();
  });

  test('close button closes trade modal', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('trade-modal')).toBeVisible();
    await page.getByTestId('close-modal').click();
    await expect(page.getByTestId('trade-modal')).not.toBeVisible();
  });

  test('switching to SELL changes button state', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await page.getByTestId('sell-button').click();
    await expect(page.getByTestId('sell-button')).toHaveClass(/bg-neon-red/);
  });

  test('can place a paper trade', async ({ page }) => {
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('trade-modal')).toBeVisible();
    
    // Ensure paper mode is on
    const paperSwitch = page.getByTestId('paper-mode-switch');
    const isChecked = await paperSwitch.isChecked();
    if (!isChecked) {
      await paperSwitch.click();
    }
    
    // Confirm trade
    await page.getByTestId('confirm-trade').click();
    
    // Modal should close after successful trade
    await expect(page.getByTestId('trade-modal')).not.toBeVisible({ timeout: 10000 });
  });
});
