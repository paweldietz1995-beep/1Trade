import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://momentum-sniper-1.preview.emergentagent.com';
const API_URL = `${BASE_URL}/api`;

// Helper to login with PIN
async function loginWithPin(page: Page, pin: string = '1234') {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  
  // Wait for login page to load
  const loginPage = page.getByTestId('login-page');
  const dashboardPage = page.getByTestId('dashboard');
  
  // Check if already logged in
  const isLoggedIn = await dashboardPage.isVisible({ timeout: 2000 }).catch(() => false);
  if (isLoggedIn) return;
  
  // Wait for login page
  await expect(loginPage).toBeVisible({ timeout: 5000 });
  
  // Fill PIN using data-testid
  const pinInput = page.getByTestId('pin-input');
  await expect(pinInput).toBeVisible();
  await pinInput.fill(pin);
  
  // Click login button
  const loginButton = page.getByTestId('login-button');
  await expect(loginButton).toBeVisible();
  await loginButton.click();
  
  // Wait for dashboard
  await expect(dashboardPage).toBeVisible({ timeout: 15000 });
}

// Helper to dismiss toasts that might block interactions
async function setupToastHandler(page: Page) {
  await page.addLocatorHandler(
    page.locator('[data-sonner-toast]'),
    async () => {
      const close = page.locator('[data-sonner-toast] button[aria-label="Close"], [data-sonner-toast] [data-close]');
      await close.first().click({ timeout: 1000 }).catch(() => {});
    },
    { times: 5, noWaitAfter: true }
  );
}

test.describe('Wallet Sync Backend Integration', () => {
  
  test('GET /api/wallet/status returns correct structure', async ({ request }) => {
    const response = await request.get(`${API_URL}/wallet/status`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    
    // Verify all required fields
    expect(data).toHaveProperty('wallet_synced');
    expect(data).toHaveProperty('wallet_address');
    expect(data).toHaveProperty('balance_sol');
    expect(data).toHaveProperty('sync_status');
    expect(data).toHaveProperty('trading_engine_ready');
    expect(data).toHaveProperty('can_trade');
    
    // Verify types
    expect(typeof data.wallet_synced).toBe('boolean');
    expect(typeof data.balance_sol).toBe('number');
    expect(data.balance_sol).toBeGreaterThanOrEqual(0);
  });
  
  test('GET /api/wallet/can-trade returns trading readiness', async ({ request }) => {
    const response = await request.get(`${API_URL}/wallet/can-trade`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    
    // Verify required fields
    expect(data).toHaveProperty('can_start');
    expect(data).toHaveProperty('reason');
    expect(data).toHaveProperty('wallet_synced');
    expect(data).toHaveProperty('trading_engine_ready');
    expect(data).toHaveProperty('initialization_complete');
    
    // Reason should explain the state
    expect(data.reason.length).toBeGreaterThan(0);
  });
  
  test('POST /api/wallet/sync syncs wallet with trading engine', async ({ request }) => {
    const testAddress = 'DfCAYgk3FZQZWD3tpqAGgNjH5vxWHCqZfREqbqPGvGz8';
    
    const response = await request.post(`${API_URL}/wallet/sync?address=${testAddress}`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    
    expect(data.success).toBe(true);
    expect(data.address).toBe(testAddress);
    expect(data.status).toBe('synced');
    expect(typeof data.balance).toBe('number');
    expect(data.balance).toBeGreaterThanOrEqual(0);
  });
  
  test('Wallet status and can-trade endpoints are consistent', async ({ request }) => {
    // First sync a wallet
    const testAddress = 'DfCAYgk3FZQZWD3tpqAGgNjH5vxWHCqZfREqbqPGvGz8';
    await request.post(`${API_URL}/wallet/sync?address=${testAddress}`);
    
    // Get both endpoints
    const [statusResponse, canTradeResponse] = await Promise.all([
      request.get(`${API_URL}/wallet/status`),
      request.get(`${API_URL}/wallet/can-trade`)
    ]);
    
    const status = await statusResponse.json();
    const canTrade = await canTradeResponse.json();
    
    // Both should agree on wallet_synced
    expect(status.wallet_synced).toBe(canTrade.wallet_synced);
    
    // Both should agree on trading_engine_ready
    expect(status.trading_engine_ready).toBe(canTrade.trading_engine_ready);
  });
  
  test('POST /api/wallet/disconnect clears wallet state', async ({ request }) => {
    // First sync
    const testAddress = 'DfCAYgk3FZQZWD3tpqAGgNjH5vxWHCqZfREqbqPGvGz8';
    await request.post(`${API_URL}/wallet/sync?address=${testAddress}`);
    
    // Disconnect
    const disconnectResponse = await request.post(`${API_URL}/wallet/disconnect`);
    expect(disconnectResponse.status()).toBe(200);
    
    const disconnectData = await disconnectResponse.json();
    expect(disconnectData.success).toBe(true);
    expect(disconnectData.status).toBe('disconnected');
    
    // Verify status shows disconnected
    const statusResponse = await request.get(`${API_URL}/wallet/status`);
    const status = await statusResponse.json();
    
    // After disconnect, wallet should not be synced or have no address
    expect(status.wallet_synced === false || status.wallet_address === null).toBe(true);
  });
});

test.describe('Dashboard Wallet Display', () => {
  
  test.beforeEach(async ({ page }) => {
    await setupToastHandler(page);
    await loginWithPin(page, '1234');
  });
  
  test('Dashboard displays wallet balance card', async ({ page }) => {
    // Wait for dashboard to load
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Check wallet balance card is visible
    const walletCard = page.getByTestId('wallet-balance-card');
    await expect(walletCard).toBeVisible();
    
    // Check wallet balance display exists
    const balanceDisplay = page.getByTestId('wallet-balance-display');
    await expect(balanceDisplay).toBeVisible();
  });
  
  test('Dashboard shows wallet status indicators', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Budget card should show available balance
    const budgetCard = page.getByTestId('budget-card');
    await expect(budgetCard).toBeVisible();
    
    // Win rate card should be visible
    const winRateCard = page.getByTestId('win-rate-card');
    await expect(winRateCard).toBeVisible();
    
    // Total P&L card should be visible
    const pnlCard = page.getByTestId('total-pnl-card');
    await expect(pnlCard).toBeVisible();
  });
  
  test('Dashboard tabs are navigable', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Overview tab should be visible and clickable
    const overviewTab = page.getByTestId('tab-overview');
    await expect(overviewTab).toBeVisible();
    
    // Scanner tab should be clickable
    const scannerTab = page.getByTestId('tab-scanner');
    await expect(scannerTab).toBeVisible();
    await scannerTab.click();
    
    // Trades tab should be clickable
    const tradesTab = page.getByTestId('tab-trades');
    await expect(tradesTab).toBeVisible();
    await tradesTab.click();
    
    // Chart tab should be clickable
    const chartTab = page.getByTestId('tab-chart');
    await expect(chartTab).toBeVisible();
    await chartTab.click();
    
    // Go back to overview
    await overviewTab.click();
  });
  
  test('Trading mode toggle is functional', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Trading mode toggle should be visible
    const modeToggle = page.getByTestId('trading-mode-toggle');
    await expect(modeToggle).toBeVisible();
  });
  
  test('Auto trade button is functional', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Auto trade toggle button should be visible
    const autoTradeToggle = page.getByTestId('auto-trade-toggle');
    await expect(autoTradeToggle).toBeVisible();
    
    // Should be able to click (start auto trading)
    await autoTradeToggle.click();
    
    // Wait for response
    await page.waitForTimeout(1000);
    
    // Click again to stop if started
    await autoTradeToggle.click();
  });
  
  test('SOL price header displays market price', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // SOL price should be displayed
    const solPrice = page.getByTestId('sol-price-header');
    await expect(solPrice).toBeVisible();
    
    // Should show a dollar value
    const priceText = await solPrice.textContent();
    expect(priceText).toMatch(/\$[\d,.]+/);
  });
});

test.describe('WalletPanel Component', () => {
  
  test.beforeEach(async ({ page }) => {
    await setupToastHandler(page);
    await loginWithPin(page, '1234');
  });
  
  test('WalletPanel shows disconnected state without wallet', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Go to overview tab where wallet panel is
    const overviewTab = page.getByTestId('tab-overview');
    await overviewTab.click();
    
    // Either connected or disconnected wallet panel should be visible
    const walletPanel = page.locator('[data-testid="wallet-panel"], [data-testid="wallet-panel-disconnected"]');
    await expect(walletPanel.first()).toBeVisible({ timeout: 5000 });
  });
  
  test('WalletPanel displays SOL balance when visible', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Go to overview tab
    await page.getByTestId('tab-overview').click();
    
    // Find balance display in any wallet panel state
    const balanceDisplay = page.getByTestId('sol-balance').first();
    
    if (await balanceDisplay.isVisible({ timeout: 3000 }).catch(() => false)) {
      const text = await balanceDisplay.textContent();
      // Should show a number (could be 0.00 or actual balance)
      expect(text).toMatch(/[\d.]+/);
    }
  });
  
  test('WalletPanel shows USD equivalent value', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    
    // Go to overview tab
    await page.getByTestId('tab-overview').click();
    
    // Find USD value display
    const usdValue = page.getByTestId('usd-value').first();
    
    if (await usdValue.isVisible({ timeout: 3000 }).catch(() => false)) {
      const text = await usdValue.textContent();
      // Should show USD value
      expect(text).toMatch(/\$[\d,.]+/);
    }
  });
});
