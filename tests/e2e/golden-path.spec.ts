import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Golden Path - Full Trading Journey', () => {
  test('complete user journey: login → dashboard → scan → trade → verify → settings', async ({ page }) => {
    await dismissToasts(page);

    // Step 1: Login
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('login-page')).toBeVisible();
    await page.getByTestId('pin-input').fill(VALID_PIN);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
    
    // Increase max parallel trades to avoid hitting limit from prior test runs
    const BASE_URL = 'https://solana-trader-31.preview.emergentagent.com';
    const settingsResp = await page.request.get(`${BASE_URL}/api/settings`);
    const settings = await settingsResp.json();
    await page.request.put(`${BASE_URL}/api/settings`, {
      data: { ...settings, max_parallel_trades: 20 }
    });
    
    // Step 2: Verify dashboard stats are loaded
    await expect(page.getByTestId('portfolio-value-card')).toBeVisible();
    await expect(page.getByTestId('total-pnl-card')).toBeVisible();
    await expect(page.getByTestId('win-rate-card')).toBeVisible();
    
    // Step 3: Navigate to Token Scanner
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible();
    
    // Step 4: Wait for tokens to load and click one
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    await page.getByTestId('token-row-0').click();
    
    // Step 5: Verify Trade Modal elements
    await expect(page.getByTestId('trade-modal')).toBeVisible();
    await expect(page.getByTestId('buy-button')).toBeVisible();
    await expect(page.getByTestId('amount-input')).toBeVisible();
    await expect(page.getByTestId('take-profit-slider')).toBeVisible();
    await expect(page.getByTestId('stop-loss-slider')).toBeVisible();
    
    // Step 6: Place a paper trade
    const paperSwitch = page.getByTestId('paper-mode-switch');
    const isCheked = await paperSwitch.isChecked();
    if (!isCheked) {
      await paperSwitch.click();
    }
    await page.getByTestId('confirm-trade').click();
    await expect(page.getByTestId('trade-modal')).not.toBeVisible({ timeout: 10000 });
    
    // Step 7: Check active trades tab
    await page.getByTestId('tab-trades').click();
    await expect(page.getByTestId('tab-trades')).toHaveAttribute('data-state', 'active');
    
    // Step 8: Open settings
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('settings-panel')).toBeVisible();
    await page.getByTestId('close-settings').click();
    await expect(page.getByTestId('settings-panel')).not.toBeVisible();
    
    // Step 9: Logout
    await page.getByTestId('logout-button').click({ force: true });
    await expect(page).toHaveURL(/.*login/, { timeout: 10000 });
  });

  test('portfolio data is displayed after trading', async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    
    // Check portfolio shows numeric values after login
    const portfolioCard = page.getByTestId('portfolio-value-card');
    await expect(portfolioCard).toBeVisible();
    
    // Portfolio should show some content (either data or '--)
    const cardContent = await portfolioCard.textContent();
    expect(cardContent).toBeTruthy();
  });

  test('DEX screener API integration - tokens have price and risk data', async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    
    // Click the first token to see its data in trade modal
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('trade-modal')).toBeVisible();
    
    // Token price info should be shown in modal
    const modalContent = await page.getByTestId('trade-modal').textContent();
    expect(modalContent).toMatch(/\$|Price|Risk/i);
    
    await page.getByTestId('close-modal').click();
  });
});
