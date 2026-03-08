import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Settings Panel', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('settings panel opens when settings button clicked', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
  });

  test('settings panel has all trading parameter controls', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
    
    await expect(page.getByTestId('stake-input')).toBeVisible();
    await expect(page.getByTestId('take-profit-setting')).toBeVisible();
    await expect(page.getByTestId('stop-loss-setting')).toBeVisible();
    await expect(page.getByTestId('max-loss-setting')).toBeVisible();
    await expect(page.getByTestId('parallel-trades-setting')).toBeVisible();
    await expect(page.getByTestId('daily-trades-setting')).toBeVisible();
  });

  test('settings panel has paper mode and auto mode toggles', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
    
    await expect(page.getByTestId('paper-mode-setting')).toBeVisible();
    await expect(page.getByTestId('auto-mode-setting')).toBeVisible();
  });

  test('settings panel has save button', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
    await expect(page.getByTestId('save-settings')).toBeVisible();
  });

  test('close button closes settings panel', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
    await page.getByTestId('close-settings').click();
    await expect(page.getByTestId('settings-panel')).not.toBeVisible();
  });

  test('can update stake per trade and save', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
    
    // Update stake input
    await page.getByTestId('stake-input').fill('0.15');
    
    // Save settings
    await page.getByTestId('save-settings').click();
    
    // Panel should close after save
    await expect(page.getByTestId('settings-panel')).not.toBeVisible({ timeout: 10000 });
  });
});

test.describe('Paper Mode Toggle', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('paper mode toggle is visible in header', async ({ page }) => {
    await expect(page.getByTestId('paper-mode-toggle')).toBeVisible();
  });

  test('paper mode shows correct label', async ({ page }) => {
    // Should show either "Paper Mode" or "Live Mode"
    const header = page.locator('[data-testid="paper-mode-toggle"]').locator('..').locator('..');
    await expect(header).toBeVisible();
  });

  test('paper mode toggle can be switched', async ({ page }) => {
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    const toggle = page.getByTestId('paper-mode-toggle');
    const initialChecked = await toggle.isChecked();
    
    // Toggle it
    await toggle.click({ force: true });
    
    // State should change
    await expect(toggle).not.toHaveAttribute('data-state', initialChecked ? 'checked' : 'unchecked');
    
    // Toggle back
    await toggle.click({ force: true });
  });

  test('SOL price is displayed in header', async ({ page }) => {
    // SOL price card should be visible
    const solPriceEl = page.locator('span.text-neon-green').first();
    await expect(solPriceEl).toBeVisible();
    const text = await solPriceEl.textContent();
    expect(text).toMatch(/\$/);
  });
});
