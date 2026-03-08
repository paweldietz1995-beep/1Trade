import { Page, expect } from '@playwright/test';

const BASE_URL = 'https://pump-auto-trade.preview.emergentagent.com';
const API_URL = `${BASE_URL}/api`;

export async function waitForAppReady(page: Page) {
  await page.waitForLoadState('domcontentloaded');
}

export async function dismissToasts(page: Page) {
  await page.addLocatorHandler(
    page.locator('[data-sonner-toast], .Toastify__toast, [role="status"].toast, .MuiSnackbar-root'),
    async () => {
      const close = page.locator('[data-sonner-toast] [data-close], [data-sonner-toast] button[aria-label="Close"], .Toastify__close-button, .MuiSnackbar-root button');
      await close.first().click({ timeout: 2000 }).catch(() => {});
    },
    { times: 10, noWaitAfter: true }
  );
}

export async function loginWithPin(page: Page, pin: string = '1234') {
  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('pin-input')).toBeVisible();
  await page.getByTestId('pin-input').fill(pin);
  await page.getByTestId('login-button').click();
  await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });
}

export async function checkForErrors(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const errorElements = Array.from(
      document.querySelectorAll('.error, [class*="error"], [id*="error"]')
    );
    return errorElements.map(el => el.textContent || '').filter(Boolean);
  });
}
