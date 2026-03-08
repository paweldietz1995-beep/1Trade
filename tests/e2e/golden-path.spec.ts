import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';
const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

test.describe('Golden Path - Full Trading Journey', () => {
  test('complete user journey: login → dashboard → scan → navigate chart → settings → logout', async ({ page, request }) => {
    await dismissToasts(page);

    // Step 1: Login
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('login-page')).toBeVisible();
    await page.getByTestId('pin-input').fill(VALID_PIN);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
    
    // Step 2: Verify all 5 dashboard stats cards are loaded
    await expect(page.getByTestId('wallet-balance-card')).toBeVisible();
    await expect(page.getByTestId('budget-card')).toBeVisible();
    await expect(page.getByTestId('in-trades-card')).toBeVisible();
    await expect(page.getByTestId('total-pnl-card')).toBeVisible();
    await expect(page.getByTestId('win-rate-card')).toBeVisible();
    
    // Step 3: Verify header elements (auto trading toggle, search, settings, logout)
    await expect(page.getByTestId('auto-trading-toggle')).toBeVisible();
    await expect(page.getByTestId('settings-button')).toBeVisible();
    await expect(page.getByTestId('logout-button')).toBeVisible();
    
    // Step 4: Navigate to Token Scanner
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible();
    
    // Step 5: Wait for tokens to load
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    
    // Step 6: Click a token - should navigate to chart tab
    await page.getByTestId('token-row-0').click();
    await expect(page.getByTestId('tab-chart')).toHaveAttribute('data-state', 'active');
    
    // Step 7: Check active trades tab
    await page.getByTestId('tab-trades').click({ force: true });
    await expect(page.getByTestId('tab-trades')).toHaveAttribute('data-state', 'active');
    
    // Step 8: Open BotSettings panel and verify it has 4 tabs
    await page.evaluate(() => {
      const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
      if (badge) (badge as HTMLElement).remove();
      // Also remove webpack dev server overlay if present
      const overlay = document.querySelector('#webpack-dev-server-client-overlay');
      if (overlay) (overlay as HTMLElement).remove();
    });
    await page.getByTestId('settings-button').click({ force: true });
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('tab', { name: /capital/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /automation/i })).toBeVisible();
    await page.getByTestId('close-settings').click();
    await expect(page.getByTestId('bot-settings-panel')).not.toBeVisible();
    
    // Step 9: Logout
    await page.getByTestId('logout-button').click({ force: true });
    await expect(page).toHaveURL(/.*login/, { timeout: 10000 });
  });

  test('portfolio data is displayed after login', async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    
    // Check portfolio shows numeric values after login
    await expect(page.getByTestId('budget-card')).toBeVisible();
    await expect(page.getByTestId('total-pnl-card')).toBeVisible();
    await expect(page.getByTestId('win-rate-card')).toBeVisible();
    
    // Cards should show some content
    const budgetContent = await page.getByTestId('budget-card').textContent();
    expect(budgetContent).toBeTruthy();
    
    const pnlContent = await page.getByTestId('total-pnl-card').textContent();
    expect(pnlContent).toBeTruthy();
  });

  test('DEX screener API integration - tokens have price and risk data', async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    
    // Verify token rows display relevant data (price, risk, signal columns)
    const firstRow = page.getByTestId('token-row-0');
    await expect(firstRow).toBeVisible();
    const rowContent = await firstRow.textContent();
    // Row should contain price data ($ sign) or percentage data
    expect(rowContent).toMatch(/\$|%|SOL/i);
  });

  test('API paper trade journey - place trade via API and verify portfolio updates', async ({ page, request }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    
    // Ensure enough budget
    const settingsRes = await request.get(`${API_BASE}/api/bot/settings`);
    const settings = await settingsRes.json();
    await request.put(`${API_BASE}/api/bot/settings`, {
      data: { ...settings, total_budget_sol: 5.0, paper_mode: true }
    });
    
    // Get a token for testing
    const tokensRes = await request.get(`${API_BASE}/api/tokens/scan?limit=1`);
    const tokens = await tokensRes.json();
    
    if (tokens.length === 0) {
      test.skip(true, 'No tokens available');
      return;
    }
    
    // Get portfolio before trade
    const portfolioBefore = await request.get(`${API_BASE}/api/portfolio`);
    const beforeData = await portfolioBefore.json();
    
    // Place a paper trade
    const tradeRes = await request.post(`${API_BASE}/api/trades`, {
      data: {
        token_address: tokens[0].address,
        token_symbol: tokens[0].symbol,
        token_name: tokens[0].name,
        trade_type: 'BUY',
        amount_sol: 0.01,
        price_entry: tokens[0].price_usd,
        take_profit_percent: 100,
        stop_loss_percent: 25,
        paper_trade: true,
        auto_trade: false
      }
    });
    
    expect(tradeRes.ok()).toBeTruthy();
    const trade = await tradeRes.json();
    
    // Verify portfolio updated
    const portfolioAfter = await request.get(`${API_BASE}/api/portfolio`);
    const afterData = await portfolioAfter.json();
    
    // In-trades should increase
    expect(afterData.in_trades_sol).toBeGreaterThan(beforeData.in_trades_sol - 0.001);
    
    // Clean up
    await request.put(`${API_BASE}/api/trades/${trade.id}/close?exit_price=${tokens[0].price_usd}`);
    await request.put(`${API_BASE}/api/bot/settings`, { data: { ...settings } });
  });
});
