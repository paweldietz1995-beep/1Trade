import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Debug Panel', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('Debug button is visible in header', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Debug' })).toBeVisible();
  });

  test('clicking Debug button opens the debug panel', async ({ page }) => {
    // Click Debug button
    await page.getByRole('button', { name: 'Debug' }).click();
    
    // Dialog should appear with System Diagnostics title
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
  });

  test('Debug panel shows all component status sections', async ({ page }) => {
    // Open debug panel
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Check for uppercase component section headers inside the panel
    // Use more specific selectors to avoid strict mode issues
    await expect(page.locator('span:text("WALLET")').first()).toBeVisible();
    await expect(page.locator('span:text("RPC")').first()).toBeVisible();
    await expect(page.locator('span:text("SCANNER")').first()).toBeVisible();
    await expect(page.locator('span:text("DATABASE")').first()).toBeVisible();
  });

  test('Debug panel shows Auto Trading Engine status', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Should show auto trading section header
    await expect(page.locator('span:text("AUTO TRADING ENGINE")').first()).toBeVisible();
    // Should show Status label
    await expect(page.getByText('Status:').first()).toBeVisible();
  });

  test('Debug panel shows Live Trading Safety section', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Wait for health check
    await page.waitForTimeout(3000);
    
    // Should show live trading safety section
    await expect(page.locator('span:text("LIVE TRADING SAFETY")').first()).toBeVisible();
  });

  test('Debug panel has Refresh button', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Should have Refresh button
    await expect(page.getByRole('button', { name: 'Refresh' })).toBeVisible();
  });

  test('Debug panel can be closed', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Close the panel
    await page.getByRole('button', { name: 'Close' }).click();
    
    // Panel should be closed
    await expect(page.getByText('System Diagnostics')).not.toBeVisible({ timeout: 3000 });
  });

  test('Debug panel shows Activity Log section', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Should show activity log header
    await expect(page.locator('span:text("ACTIVITY LOG")').first()).toBeVisible();
  });

  test('Debug panel Refresh button updates activity log', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Wait for initial health check
    await page.waitForTimeout(2000);
    
    // Click refresh
    await page.getByRole('button', { name: 'Refresh' }).click();
    
    // Activity log should show health check messages (use first() to avoid strict mode)
    await expect(page.getByText('Checking system health...').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('System Health Integration', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('Debug panel shows overall system status indicator after loading', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Wait for health check to complete (longer timeout)
    await page.waitForTimeout(5000);
    
    // Should show overall status - look for either "All Systems Operational" or specific component statuses
    // The status shows after the API call completes
    const allOperational = await page.getByText('All Systems Operational').isVisible().catch(() => false);
    const issuesDetected = await page.getByText('System Issues Detected').isVisible().catch(() => false);
    const rpcConnected = await page.getByText('Connected').first().isVisible().catch(() => false);
    
    // Either the overall status shows OR component statuses show
    expect(allOperational || issuesDetected || rpcConnected).toBe(true);
  });

  test('Debug panel shows RPC status', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Wait for RPC check to complete
    await page.waitForTimeout(5000);
    
    // RPC section should show Connected or Failed
    const connected = await page.getByText('Connected').first().isVisible().catch(() => false);
    const failed = await page.getByText('Failed').first().isVisible().catch(() => false);
    
    expect(connected || failed).toBe(true);
  });

  test('Debug panel shows wallet Disconnected status', async ({ page }) => {
    await page.getByRole('button', { name: 'Debug' }).click();
    await expect(page.getByText('System Diagnostics')).toBeVisible({ timeout: 5000 });
    
    // Wallet section shows Disconnected (since no wallet extension in test env)
    await expect(page.getByText('Disconnected').first()).toBeVisible();
  });
});

test.describe('TradingView Widget Validation', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('Chart tab can be clicked', async ({ page }) => {
    // Navigate to Chart tab (not Charts)
    await page.getByRole('tab', { name: 'Chart' }).click();
    
    // Should show either the actual chart container or the placeholder
    // Look for the TradingView container
    const chartExists = await page.locator('.tradingview-widget-container').first().isVisible({ timeout: 10000 }).catch(() => false);
    const placeholderExists = await page.getByTestId('tradingview-placeholder').isVisible({ timeout: 2000 }).catch(() => false);
    
    expect(chartExists || placeholderExists).toBe(true);
  });
});
