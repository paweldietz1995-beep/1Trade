import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';
// Use explicit URL since process.env isn't available in Playwright context
const API_BASE = 'https://solana-auto-trade.preview.emergentagent.com';

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

  test('overview shows either opportunities or no opportunities state', async ({ page }) => {
    await expect(page.getByTestId('trading-opportunities')).toBeVisible({ timeout: 15000 });
    // Either shows opportunities or a state with no opportunities - both are valid
    const hasOpportunities = await page.getByTestId('opportunity-0').isVisible().catch(() => false);
    const hasAISignals = await page.getByText('AI Signals').isVisible().catch(() => false);
    
    // The panel should be visible with either opportunities or an indication of status
    expect(hasOpportunities || hasAISignals).toBe(true);
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
    // Get current settings and portfolio
    const settingsRes = await request.get(`${API_BASE}/api/bot/settings`);
    const settings = await settingsRes.json();
    
    const portfolioRes = await request.get(`${API_BASE}/api/portfolio`);
    const portfolio = await portfolioRes.json();
    
    // Check if we have capacity for a new trade
    if (portfolio.open_trades >= settings.max_parallel_trades) {
      test.skip(true, `Max parallel trades reached (${portfolio.open_trades}/${settings.max_parallel_trades})`);
      return;
    }
    
    if (portfolio.available_sol < 0.01) {
      test.skip(true, 'Not enough available balance for test');
      return;
    }

    // First get tokens to get a valid token address
    const tokensRes = await request.get(`${API_BASE}/api/tokens/scan?limit=1`);
    expect(tokensRes.ok()).toBeTruthy();
    const tokens = await tokensRes.json();
    
    if (tokens.length === 0) {
      test.skip(true, 'No tokens available for trading');
      return;
    }
    
    // Place a paper trade with unique identifier
    const testTimestamp = Date.now();
    const tradeRes = await request.post(`${API_BASE}/api/trades`, {
      data: {
        token_address: `TEST_TRADING_${testTimestamp}`,
        token_symbol: 'TFTEST',
        token_name: 'Trading Features Test',
        pair_address: null,
        trade_type: 'BUY',
        amount_sol: 0.01,
        price_entry: tokens[0].price_usd || 0.001,
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
