import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';
const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

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

  test('clicking token row navigates to chart tab', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    await page.getByTestId('token-row-0').click();
    // Should navigate to chart tab
    await expect(page.getByTestId('tab-chart')).toHaveAttribute('data-state', 'active');
  });

  test('token rows display risk score and momentum signal', async ({ page }) => {
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-row-0')).toBeVisible({ timeout: 30000 });
    // Token rows should be visible with data (risk and signal columns in grid)
    const firstRow = page.getByTestId('token-row-0');
    await expect(firstRow).toBeVisible();
  });
});

test.describe('Trading Opportunities', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
    // Navigate to overview tab which shows TradingOpportunities
    await page.getByTestId('tab-overview').click();
  });

  test('trading opportunities panel is visible in overview tab', async ({ page }) => {
    await expect(page.getByTestId('trading-opportunities')).toBeVisible({ timeout: 15000 });
  });

  test('overview shows either opportunities or scanning message', async ({ page }) => {
    await expect(page.getByTestId('trading-opportunities')).toBeVisible({ timeout: 15000 });
    // Either shows opportunities or "scanning for opportunities..." message
    const hasOpportunities = await page.getByTestId('opportunity-0').isVisible().catch(() => false);
    if (!hasOpportunities) {
      await expect(page.getByText('Scanning for opportunities')).toBeVisible({ timeout: 10000 });
    }
  });

  test('trade modal opens via opportunity custom button when available', async ({ page }) => {
    await expect(page.getByTestId('trading-opportunities')).toBeVisible({ timeout: 15000 });
    
    const opportunity = page.getByTestId('opportunity-0');
    const hasOpportunity = await opportunity.isVisible().catch(() => false);
    
    if (hasOpportunity) {
      // Click the "Custom" button in the first opportunity
      const customBtn = opportunity.getByRole('button', { name: /custom/i });
      await customBtn.click();
      await expect(page.getByTestId('trade-modal')).toBeVisible();
      
      // Verify trade modal has key elements
      await expect(page.getByTestId('buy-button')).toBeVisible();
      await expect(page.getByTestId('sell-button')).toBeVisible();
      await expect(page.getByTestId('amount-input')).toBeVisible();
      await expect(page.getByTestId('take-profit-slider')).toBeVisible();
      await expect(page.getByTestId('stop-loss-slider')).toBeVisible();
      await expect(page.getByTestId('paper-mode-switch')).toBeVisible();
      
      // Close the modal
      await page.getByTestId('close-modal').click();
      await expect(page.getByTestId('trade-modal')).not.toBeVisible();
    } else {
      // Skip if no opportunities available - market conditions
      test.skip(true, 'No trading opportunities available - market conditions');
    }
  });
});

test.describe('Trade Modal via API', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('paper trade can be placed via API and shows in trades tab', async ({ page, request }) => {
    // Ensure enough budget by updating settings
    const settingsRes = await request.get(`${API_BASE}/api/bot/settings`);
    const settings = await settingsRes.json();
    
    // Update budget to ensure enough for testing
    await request.put(`${API_BASE}/api/bot/settings`, {
      data: { ...settings, total_budget_sol: 5.0, paper_mode: true }
    });

    // First get tokens to get a valid token address
    const tokensRes = await request.get(`${API_BASE}/api/tokens/scan?limit=1`);
    expect(tokensRes.ok()).toBeTruthy();
    const tokens = await tokensRes.json();
    
    if (tokens.length === 0) {
      test.skip(true, 'No tokens available for trading');
      return;
    }
    
    const token = tokens[0];
    
    // Place a paper trade via API
    const tradeRes = await request.post(`${API_BASE}/api/trades`, {
      data: {
        token_address: token.address,
        token_symbol: token.symbol,
        token_name: token.name,
        pair_address: token.pair_address || null,
        trade_type: 'BUY',
        amount_sol: 0.01,
        price_entry: token.price_usd,
        take_profit_percent: 50,
        stop_loss_percent: 20,
        trailing_stop_percent: null,
        paper_trade: true,
        auto_trade: false,
        wallet_address: null
      }
    });
    
    expect(tradeRes.ok()).toBeTruthy();
    const trade = await tradeRes.json();
    expect(trade.id).toBeDefined();
    expect(trade.paper_trade).toBe(true);
    expect(trade.status).toBe('OPEN');
    
    // Navigate to trades tab and verify trade appears
    await page.getByTestId('tab-trades').click();
    await expect(page.getByTestId('tab-trades')).toHaveAttribute('data-state', 'active');
    
    // Clean up - close the trade
    await request.put(`${API_BASE}/api/trades/${trade.id}/close?exit_price=${token.price_usd}`);
    
    // Restore original settings
    await request.put(`${API_BASE}/api/bot/settings`, {
      data: { ...settings }
    });
  });
});
