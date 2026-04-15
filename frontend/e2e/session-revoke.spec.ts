import { expect, test } from '@playwright/test'

test.describe('Session revocation', () => {
  test('self-revoking the current session logs out and redirects to login once', async ({ page }) => {
    const uniqueSuffix = Date.now()
    const username = `session_user_${uniqueSuffix}`
    const email = `session_user_${uniqueSuffix}@example.com`
    const password = 'password123'

    await page.goto('/register')
    await page.getByPlaceholder('Username').fill(username)
    await page.getByPlaceholder('Email').fill(email)
    await page.getByPlaceholder('Password').first().fill(password)
    await page.getByPlaceholder('Confirm Password').fill(password)
    await page.getByRole('button', { name: 'Register' }).click()

    await page.waitForURL('**/')
    await page.goto('/profile')
    await page.getByRole('tab', { name: 'My Sessions' }).click()

    const currentSessionRow = page.locator('.el-table__row').filter({ hasText: 'Current' }).first()
    await expect(currentSessionRow).toBeVisible()

    await currentSessionRow.getByRole('button', { name: 'Revoke' }).click()
    await page.getByRole('button', { name: 'Confirm' }).click()

    await page.waitForURL('**/login')
    await expect(page.getByText('Login to PR Ledger')).toBeVisible()

    await page.waitForTimeout(500)
    await expect(page).toHaveURL(/\/login$/)

    const storedTokens = await page.evaluate(() => ({
      accessToken: window.localStorage.getItem('access_token'),
      refreshToken: window.localStorage.getItem('refresh_token'),
    }))

    expect(storedTokens.accessToken).toBeNull()
    expect(storedTokens.refreshToken).toBeNull()
  })
})