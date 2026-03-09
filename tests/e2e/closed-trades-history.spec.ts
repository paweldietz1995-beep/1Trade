import { test, expect } from '@playwright/test';
import { dismissToasts, loginWithPin } from '../fixtures/helpers';

const VALID_PIN = '1234';

test.describe('Closed Trades History Feature', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('Live P&L tab shows both active and closed trades tabs', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    await expect(page.getByTestId('live-trades-panel')).toBeVisible({ timeout: 10000 });
    
    // Verify tabs exist - using German text within the panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel.getByText(/Aktive Trades/)).toBeVisible();
    await expect(panel.getByText(/Geschlossene Trades/)).toBeVisible();
  });

  test('Closed trades tab displays statistics summary (German)', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify summary statistics are visible (German labels) within the panel
    await expect(panel.getByText('Gesamtgewinn')).toBeVisible({ timeout: 5000 });
    await expect(panel.getByText('Gesamtverlust')).toBeVisible({ timeout: 5000 });
    // Trefferquote appears in both dashboard and panel - use panel scope
    await expect(panel.getByText('Trefferquote')).toBeVisible({ timeout: 5000 });
    await expect(panel.getByText('Ø Gewinn')).toBeVisible({ timeout: 5000 });
    await expect(panel.getByText('Ø Verlust')).toBeVisible({ timeout: 5000 });
  });

  test('Closed trades table has correct German column headers', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify table headers are in German - use thead within panel
    const thead = panel.locator('thead');
    await expect(thead.getByText('TOKEN')).toBeVisible({ timeout: 5000 });
    await expect(thead.getByText('EINSTIEG')).toBeVisible();
    await expect(thead.getByText('AUSSTIEG')).toBeVisible();
    // Column names may be different - check actual text
    await expect(thead.getByText('P&L')).toBeVisible();
    await expect(thead.getByText('ROI')).toBeVisible();
  });

  test('Clicking on closed trade row opens detail modal', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Click on first trade row in the panel's table
    const firstRow = panel.locator('tbody tr').first();
    await firstRow.click();
    
    // Verify modal opens - look for modal-specific content (Dauer = Duration)
    await expect(page.getByText('Dauer')).toBeVisible({ timeout: 5000 });
  });

  test('Trade detail modal shows all required fields', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Click on first trade row
    await panel.locator('tbody tr').first().click();
    
    // Modal is rendered outside the panel - check for modal dialog
    const modal = page.locator('.fixed.inset-0');
    await expect(modal).toBeVisible({ timeout: 5000 });
    
    // Verify all required modal fields are visible (German)
    await expect(modal.getByText('Dauer')).toBeVisible(); // Duration - unique to modal
    await expect(modal.getByText('Einstieg')).toBeVisible();
    await expect(modal.getByText('Ausstieg')).toBeVisible();
    await expect(modal.getByText('Eröffnet')).toBeVisible(); // Opened
    // "Geschlossen" appears in both label and badge - use first() for label
    await expect(modal.locator('div').filter({ hasText: /^Geschlossen$/ })).toBeVisible(); // Closed label
    await expect(modal.getByText('Grund')).toBeVisible(); // Close reason
  });

  test('Trade detail modal can be closed with X button', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Click on first trade row
    await panel.locator('tbody tr').first().click();
    
    // Modal should be visible
    const modal = page.locator('.fixed.inset-0');
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal.getByText('Dauer')).toBeVisible();
    
    // Close modal by clicking X button inside modal
    await modal.locator('button').first().click();
    
    // Modal should be closed - modal overlay gone
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('P&L shows green color for profits in closed trades', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Look for green text (profit indicators) - neon-green class within panel
    const profitElements = panel.locator('.text-neon-green');
    const count = await profitElements.count();
    
    // Should have at least one green element (total profit header)
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('P&L shows red color for losses in closed trades', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Click on Closed Trades tab
    await panel.getByText(/Geschlossene Trades/).click();
    await page.waitForLoadState('domcontentloaded');
    
    // Look for red text (loss indicators) - neon-red class within panel
    const lossElements = panel.locator('.text-neon-red');
    const count = await lossElements.count();
    
    // Should have at least one red element (total loss header)
    expect(count).toBeGreaterThanOrEqual(1);
  });
});

test.describe('Active Trades Feature', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('Active trades tab shows trade list', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Active trades tab should be default and visible
    await expect(panel.getByText(/Aktive Trades/)).toBeVisible();
  });

  test('Active trades table has correct German headers or empty state', async ({ page }) => {
    // Navigate to Live P&L tab
    await page.getByTestId('tab-trades').click();
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for live trades panel
    const panel = page.getByTestId('live-trades-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    
    // Check for either table headers (if trades exist) or empty state message
    const hasTradesTable = await panel.locator('thead').count() > 0;
    
    if (hasTradesTable) {
      // Verify table headers if table exists
      const thead = panel.locator('thead');
      await expect(thead.getByText('TOKEN')).toBeVisible({ timeout: 5000 });
    } else {
      // Verify empty state message (German: "Keine aktiven Trades")
      await expect(panel.getByText('Keine aktiven Trades')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Dashboard Win Rate and Portfolio Stats', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await loginWithPin(page, VALID_PIN);
  });

  test('Dashboard shows win rate card with German label', async ({ page }) => {
    // Win rate card should be visible on dashboard
    const winRateCard = page.getByTestId('win-rate-card');
    await expect(winRateCard).toBeVisible({ timeout: 10000 });
    
    // Should contain "Trefferquote" (Win Rate in German) - title case in CSS
    await expect(winRateCard).toContainText('Trefferquote');
    
    // Should show percentage
    await expect(winRateCard.getByText(/%/)).toBeVisible();
  });

  test('Dashboard shows Total P&L card', async ({ page }) => {
    const pnlCard = page.getByTestId('total-pnl-card');
    await expect(pnlCard).toBeVisible({ timeout: 10000 });
    
    // Should contain P&L label (may be "GESAMT P&L" or similar)
    await expect(pnlCard).toContainText('P&L');
  });

  test('Dashboard stats cards show SOL values', async ({ page }) => {
    // Budget card
    const budgetCard = page.getByTestId('budget-card');
    await expect(budgetCard).toBeVisible({ timeout: 10000 });
    await expect(budgetCard.getByText(/SOL/).first()).toBeVisible();
    
    // In trades card
    const inTradesCard = page.getByTestId('in-trades-card');
    await expect(inTradesCard).toBeVisible();
    await expect(inTradesCard.getByText(/SOL/).first()).toBeVisible();
  });
});
