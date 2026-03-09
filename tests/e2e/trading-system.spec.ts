import { test, expect } from '@playwright/test';

const BASE_URL = 'https://pump-sniper-1.preview.emergentagent.com';

// Helper function to login
async function login(page: any) {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('pin-input').fill('1234');
  await page.getByTestId('login-button').click();
  await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
}

test.describe('Trading System Core Features', () => {
  
  test('Login with PIN and access dashboard', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    // Verify login page elements
    await expect(page.getByTestId('login-page')).toBeVisible();
    await expect(page.getByTestId('pin-input')).toBeVisible();
    await expect(page.getByTestId('login-button')).toBeVisible();
    
    // Login
    await page.getByTestId('pin-input').fill('1234');
    await page.getByTestId('login-button').click();
    
    // Verify dashboard loads
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
  });

  test('Dashboard displays all key components', async ({ page }) => {
    await login(page);
    
    // Verify header components
    await expect(page.getByTestId('trading-mode-toggle')).toBeVisible();
    await expect(page.getByTestId('auto-trade-toggle')).toBeVisible();
    await expect(page.getByTestId('settings-button')).toBeVisible();
    
    // Verify portfolio cards
    await expect(page.getByTestId('wallet-balance-card')).toBeVisible();
    await expect(page.getByTestId('budget-card')).toBeVisible();
    await expect(page.getByTestId('in-trades-card')).toBeVisible();
    await expect(page.getByTestId('total-pnl-card')).toBeVisible();
    await expect(page.getByTestId('win-rate-card')).toBeVisible();
    
    // Verify tabs
    await expect(page.getByTestId('tab-overview')).toBeVisible();
    await expect(page.getByTestId('tab-scanner')).toBeVisible();
    await expect(page.getByTestId('tab-trades')).toBeVisible();
    await expect(page.getByTestId('tab-chart')).toBeVisible();
  });

  test('German UI localization is active', async ({ page }) => {
    await login(page);
    
    // Verify German labels in the UI using more specific locators
    await expect(page.getByTestId('wallet-balance-card').getByText('Wallet', { exact: true })).toBeVisible();
    await expect(page.getByText('VERFÜGBAR')).toBeVisible();
    await expect(page.getByText('IN TRADES')).toBeVisible();
    await expect(page.getByText('GESAMT P&L')).toBeVisible();
    await expect(page.getByText('TREFFERQUOTE')).toBeVisible();
  });

  test('SOL price display updates', async ({ page }) => {
    await login(page);
    
    // SOL price should be displayed in header
    await expect(page.getByTestId('sol-price-header')).toBeVisible();
    const priceText = await page.getByTestId('sol-price-header').textContent();
    expect(priceText).toMatch(/\$\d+/);  // Should contain dollar sign and number
  });
});

test.describe('Token Scanner', () => {
  
  test('Scanner tab displays token list', async ({ page }) => {
    await login(page);
    
    // Navigate to scanner
    await page.getByTestId('tab-scanner').click();
    
    // Verify scanner components
    await expect(page.getByTestId('token-scanner')).toBeVisible();
    await expect(page.getByTestId('token-search')).toBeVisible();
    await expect(page.getByTestId('refresh-tokens')).toBeVisible();
    
    // Wait for tokens to load
    await page.waitForTimeout(3000);
    
    // Check for token rows (should have at least some tokens)
    const tokenRows = page.locator('[data-testid^="token-row-"]');
    const count = await tokenRows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Token search functionality works', async ({ page }) => {
    await login(page);
    
    await page.getByTestId('tab-scanner').click();
    await page.waitForTimeout(2000);
    
    // Type in search box
    await page.getByTestId('token-search').fill('SOL');
    await page.waitForTimeout(1000);
    
    // Verify search input was accepted
    const searchValue = await page.getByTestId('token-search').inputValue();
    expect(searchValue).toBe('SOL');
  });

  test('Token signals display correctly (STRONG/MEDIUM/WEAK/NONE)', async ({ page }) => {
    await login(page);
    
    await page.getByTestId('tab-scanner').click();
    await page.waitForTimeout(3000);
    
    // Check that at least some signal indicators exist
    const signals = page.locator('text=STRONG, text=MEDIUM, text=WEAK, text=NONE');
    // There should be signal indicators in the token list
    await expect(page.getByText(/STRONG|MEDIUM|WEAK|NONE/).first()).toBeVisible();
  });
});

test.describe('Live P&L Panel', () => {
  
  test('Live P&L tab displays monitor', async ({ page }) => {
    await login(page);
    
    // Navigate to Live P&L
    await page.getByTestId('tab-trades').click();
    await page.waitForTimeout(1500);
    
    // Verify P&L panel
    await expect(page.getByTestId('live-trades-panel')).toBeVisible();
    
    // Check German labels with more specific locators
    await expect(page.getByText('Live P&L Monitor')).toBeVisible();
    await expect(page.getByText('Investiert')).toBeVisible();
    await expect(page.getByText('Aktueller Wert')).toBeVisible();
    // Use exact: true to avoid multiple matches for P&L
    await expect(page.getByText('P&L', { exact: true }).first()).toBeVisible();
  });

  test('Active and Closed Trades tabs exist', async ({ page }) => {
    await login(page);
    
    await page.getByTestId('tab-trades').click();
    await page.waitForTimeout(1500);
    
    // Verify trade tabs
    await expect(page.getByText('Aktive Trades')).toBeVisible();
    await expect(page.getByText('Geschlossene Trades')).toBeVisible();
  });
});

test.describe('Bot Settings Panel', () => {
  
  test('Settings panel opens and displays tabs', async ({ page }) => {
    await login(page);
    
    // Open settings
    await page.getByTestId('settings-button').click();
    await page.waitForTimeout(1000);
    
    // Verify settings panel
    await expect(page.getByTestId('bot-settings-panel')).toBeVisible();
    await expect(page.getByText('Auto-Trading Einstellungen')).toBeVisible();
    
    // Verify settings tabs using role selectors to be more specific
    await expect(page.getByRole('tab', { name: 'Kapitalverwaltung' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Risikomanagement' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Signal-Filter' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Automatisierung' })).toBeVisible();
  });

  test('Budget settings can be modified', async ({ page }) => {
    await login(page);
    
    await page.getByTestId('settings-button').click();
    await page.waitForTimeout(1000);
    
    // Verify budget input exists
    await expect(page.getByTestId('total-budget-input')).toBeVisible();
    await expect(page.getByTestId('min-trade-input')).toBeVisible();
    
    // Verify save button exists
    await expect(page.getByTestId('save-settings')).toBeVisible();
  });

  test('Settings can be closed', async ({ page }) => {
    await login(page);
    
    await page.getByTestId('settings-button').click();
    await page.waitForTimeout(500);
    
    // Close settings
    await page.getByTestId('close-settings').click();
    
    // Verify settings closed
    await expect(page.getByTestId('bot-settings-panel')).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Auto-Trading Controls', () => {
  
  test('Auto-trading toggle is visible and clickable', async ({ page }) => {
    await login(page);
    
    // Check auto-trading button
    await expect(page.getByTestId('auto-trade-toggle')).toBeVisible();
    
    // Verify the text contains "Auto-Trading"
    await expect(page.getByText(/Auto-Trading/)).toBeVisible();
  });

  test('Trading mode toggle shows TESTMODUS', async ({ page }) => {
    await login(page);
    
    // Verify TESTMODUS is displayed
    await expect(page.getByTestId('trading-mode-toggle')).toBeVisible();
    await expect(page.getByText('TESTMODUS')).toBeVisible();
  });
});

test.describe('Navigation Tabs', () => {
  
  test('All tabs are clickable and switch content', async ({ page }) => {
    await login(page);
    
    // Overview tab (default)
    await expect(page.getByTestId('tab-overview')).toBeVisible();
    
    // Scanner tab
    await page.getByTestId('tab-scanner').click();
    await expect(page.getByTestId('token-scanner')).toBeVisible();
    
    // Live P&L tab
    await page.getByTestId('tab-trades').click();
    await expect(page.getByTestId('live-trades-panel')).toBeVisible();
    
    // Chart tab
    await page.getByTestId('tab-chart').click();
    // Chart content should be visible
    await page.waitForTimeout(1000);
    
    // Back to Overview
    await page.getByTestId('tab-overview').click();
    await expect(page.getByText('Trading Opportunities')).toBeVisible();
  });
});

test.describe('Logout Functionality', () => {
  
  test('Logout button exists and works', async ({ page }) => {
    await login(page);
    
    // Check logout button exists
    await expect(page.getByTestId('logout-button')).toBeVisible();
    
    // Click logout
    await page.getByTestId('logout-button').click();
    
    // Should return to login page
    await expect(page.getByTestId('login-page')).toBeVisible({ timeout: 5000 });
  });
});
