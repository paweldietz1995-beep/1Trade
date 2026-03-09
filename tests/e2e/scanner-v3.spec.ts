import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Scanner V3 Features', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('dashboard loads with token scanner tab available', async ({ page }) => {
    await expect(page.getByTestId('tab-scanner')).toBeVisible();
    await expect(page.getByTestId('tab-scanner')).toBeEnabled();
  });

  test('token scanner tab can be clicked and shows scanner', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible({ timeout: 15000 });
  });

  test('token scanner displays search input', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('token-search')).toBeVisible();
  });

  test('token scanner displays refresh button', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('refresh-tokens')).toBeVisible();
  });

  test('refresh tokens button is clickable', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('refresh-tokens')).toBeEnabled();
    await page.getByTestId('refresh-tokens').click();
    // Button should still be visible after click (no crash)
    await expect(page.getByTestId('refresh-tokens')).toBeVisible();
  });

  test('search input accepts text', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible({ timeout: 15000 });
    await page.getByTestId('token-search').fill('SOL');
    await expect(page.getByTestId('token-search')).toHaveValue('SOL');
  });
});

test.describe('Auto Trading Status Display', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('auto trade toggle is visible in header', async ({ page }) => {
    await expect(page.getByTestId('auto-trade-toggle')).toBeVisible();
  });

  test('trading mode toggle is visible', async ({ page }) => {
    await expect(page.getByTestId('trading-mode-toggle')).toBeVisible();
  });

  test('auto trade toggle can be interacted with', async ({ page }) => {
    const toggle = page.getByTestId('auto-trade-toggle');
    await expect(toggle).toBeVisible();
    // Just verify it's interactable (don't actually start trading)
    await expect(toggle).toBeEnabled();
  });
});

test.describe('Dashboard Stats Cards', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('wallet balance card is visible', async ({ page }) => {
    await expect(page.getByTestId('wallet-balance-card')).toBeVisible();
  });

  test('wallet balance display shows value or not connected', async ({ page }) => {
    await expect(page.getByTestId('wallet-balance-display')).toBeVisible();
    const balanceText = await page.getByTestId('wallet-balance-display').textContent();
    // Without wallet connected, shows "Nicht verbunden" (German); with wallet shows SOL balance
    expect(balanceText).toBeTruthy();
    expect(balanceText!.length).toBeGreaterThan(0);
  });

  test('budget card is visible', async ({ page }) => {
    await expect(page.getByTestId('budget-card')).toBeVisible();
  });

  test('in trades card is visible', async ({ page }) => {
    await expect(page.getByTestId('in-trades-card')).toBeVisible();
  });

  test('total PnL card is visible', async ({ page }) => {
    await expect(page.getByTestId('total-pnl-card')).toBeVisible();
  });

  test('win rate card is visible', async ({ page }) => {
    await expect(page.getByTestId('win-rate-card')).toBeVisible();
  });

  test('SOL price is displayed in header', async ({ page }) => {
    await expect(page.getByTestId('sol-price-header')).toBeVisible();
    const priceText = await page.getByTestId('sol-price-header').textContent();
    expect(priceText).toMatch(/\$[\d,.]+/);
  });
});

test.describe('Scanner Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('overview tab is visible', async ({ page }) => {
    await expect(page.getByTestId('tab-overview')).toBeVisible();
  });

  test('scanner tab is visible', async ({ page }) => {
    await expect(page.getByTestId('tab-scanner')).toBeVisible();
  });

  test('trades tab is visible', async ({ page }) => {
    await expect(page.getByTestId('tab-trades')).toBeVisible();
  });

  test('chart tab is visible', async ({ page }) => {
    await expect(page.getByTestId('tab-chart')).toBeVisible();
  });

  test('switching between tabs works', async ({ page }) => {
    // Start on overview
    await expect(page.getByTestId('tab-overview')).toHaveAttribute('data-state', 'active');
    
    // Switch to scanner
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('tab-scanner')).toHaveAttribute('data-state', 'active');
    
    // Switch to trades
    await page.getByTestId('tab-trades').click();
    await expect(page.getByTestId('tab-trades')).toHaveAttribute('data-state', 'active');
    
    // Back to overview
    await page.getByTestId('tab-overview').click();
    await expect(page.getByTestId('tab-overview')).toHaveAttribute('data-state', 'active');
  });
});

test.describe('API Integration Verification', () => {
  test('scanner stats API returns valid data', async ({ request }) => {
    const response = await request.get('/api/scanner/stats');
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data.scanner_version).toBe('v3');
    expect(data.stats).toBeDefined();
    expect(data.config).toBeDefined();
    expect(data.config.cache_ttl_seconds).toBe(2.0);
    expect(data.config.batch_size).toBe(200);
  });

  test('auto-trading status API returns valid data', async ({ request }) => {
    const response = await request.get('/api/auto-trading/status');
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data.is_running).toBeDefined();
    expect(data.high_frequency_mode).toBe(true);
    expect(data.scan_interval_seconds).toBe(1.0);
    expect(data.config).toBeDefined();
  });

  test('health check API returns healthy', async ({ request }) => {
    const response = await request.get('/api/health');
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data.status).toBe('healthy');
    expect(data.timestamp).toBeDefined();
  });

  test('tokens scan API returns list', async ({ request }) => {
    const response = await request.get('/api/tokens/scan?limit=5');
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(Array.isArray(data)).toBe(true);
  });
});
