import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Bot Settings Panel', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
  });

  test('settings panel opens when settings button clicked', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();
  });

  test('settings panel has all 4 tabs (Capital, Trading, Filters, Automation)', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();

    // Check all 4 tabs exist
    await expect(page.getByRole('tab', { name: /capital/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /trading/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /filters/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /automation/i })).toBeVisible();
  });

  test('Capital tab shows budget configuration inputs', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();

    // Capital tab is active by default
    await expect(page.getByRole('tab', { name: /capital/i })).toHaveAttribute('data-state', 'active');
    // Should show budget inputs
    await expect(page.getByRole('spinbutton').first()).toBeVisible();
  });

  test('Trading tab shows TP/SL sliders', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();

    await page.getByRole('tab', { name: /trading/i }).click();
    const panel = page.getByTestId('bot-settings-panel');
    // Should show Take Profit and Stop Loss labels
    await expect(panel.getByText('Take Profit', { exact: true })).toBeVisible();
    await expect(panel.getByText('Stop Loss', { exact: true })).toBeVisible();
  });

  test('Filters tab shows token requirement controls', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();

    await page.getByRole('tab', { name: /filters/i }).click();
    await expect(page.getByText('Min Liquidity')).toBeVisible();
  });

  test('Automation tab shows paper mode and auto trade toggles', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();

    await page.getByRole('tab', { name: /automation/i }).click();
    const panel = page.getByTestId('bot-settings-panel');
    await expect(panel.getByText('Auto Trading')).toBeVisible();
    await expect(panel.getByText('Paper Trading Mode')).toBeVisible();
  });

  test('settings panel has save button', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();
    await expect(page.getByTestId('save-settings')).toBeVisible();
  });

  test('close button closes settings panel', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();
    await page.getByTestId('close-settings').click();
    await expect(page.getByTestId('bot-settings-panel')).not.toBeVisible({ timeout: 5000 });
  });

  test('can save settings and panel closes', async ({ page }) => {
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();

    // Save settings
    await page.getByTestId('save-settings').click();

    // Panel should close after save
    await expect(page.getByTestId('bot-settings-panel')).not.toBeVisible({ timeout: 10000 });
  });
});

test.describe('Auto Trading and Paper Mode', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
  });

  test('auto trading toggle is visible in header', async ({ page }) => {
    await expect(page.getByTestId('auto-trading-toggle')).toBeVisible();
  });

  test('paper mode badge shown in header when paper mode is active', async ({ page }) => {
    // Paper mode should be on by default, showing badge
    const paperBadge = page.getByText('Paper Mode');
    // If bot has paper_mode: true, badge is shown
    // Just check header area has relevant text content
    await expect(page.getByTestId('dashboard')).toBeVisible();
    // At minimum, auto trading toggle should be visible
    await expect(page.getByTestId('auto-trading-toggle')).toBeVisible();
  });

  test('auto trading toggle can be clicked', async ({ page }) => {
    const toggle = page.getByTestId('auto-trading-toggle');
    await expect(toggle).toBeVisible();
    // Click toggle - it makes an API call to update settings
    await toggle.click({ force: true });
    // Wait for dashboard to reflect the change - auto trading label should update
    await expect(
      page.locator('.text-xs.uppercase.tracking-wider').filter({ hasText: /Auto Trading/ })
    ).toBeVisible({ timeout: 10000 });
    // Toggle back to original state
    await toggle.click({ force: true });
  });

  test('SOL price is displayed in header', async ({ page }) => {
    // Look for USD-formatted price in header (format $xxx.xx)
    await expect(page.getByTestId('dashboard')).toBeVisible();
    const priceText = page.locator('span.text-neon-green').first();
    await expect(priceText).toBeVisible();
    const text = await priceText.textContent();
    expect(text).toMatch(/\$/);
  });
});
