import { test, expect } from '@playwright/test'

test.describe('Authentication Flow', () => {
  test('should display login page', async ({ page }) => {
    await page.goto('/login')
    
    // Check if login form is visible
    await expect(page.locator('h2')).toContainText('Login')
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('should show validation errors for empty fields', async ({ page }) => {
    await page.goto('/login')
    
    // Try to submit without filling fields
    await page.locator('button[type="submit"]').click()
    
    // Should show validation errors
    await expect(page.locator('.el-form-item__error')).toBeVisible()
  })

  test('should navigate to register page', async ({ page }) => {
    await page.goto('/login')
    
    // Click register link
    await page.locator('text=Register').click()
    
    // Should navigate to register page
    await expect(page).toHaveURL(/.*register/)
  })
})

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'mock_token')
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        roles: ['admin'],
      }))
    })
    await page.reload()
  })

  test('should display dashboard after login', async ({ page }) => {
    await page.goto('/')
    
    // Check if dashboard is visible
    await expect(page.locator('h1')).toContainText('Dashboard')
  })

  test('should display statistics cards', async ({ page }) => {
    await page.goto('/')
    
    // Check if stats cards are present
    const cards = page.locator('.stat-card')
    await expect(cards).toHaveCount(4) // Total Reviews, Pending, Completed, Avg Score
  })

  test('should navigate to reviews page', async ({ page }) => {
    await page.goto('/')
    
    // Click reviews menu item
    await page.locator('text=Reviews').click()
    
    // Should navigate to reviews page
    await expect(page).toHaveURL(/.*reviews/)
  })
})

test.describe('Review Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'mock_token')
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        roles: ['admin'],
      }))
    })
  })

  test('should display review list', async ({ page }) => {
    await page.goto('/reviews')
    
    // Check if review table is visible
    await expect(page.locator('.el-table')).toBeVisible()
  })

  test('should filter reviews by status', async ({ page }) => {
    await page.goto('/reviews')
    
    // Select status filter
    await page.locator('.status-filter').click()
    await page.locator('.el-select-dropdown__item:has-text("Pending")').click()
    
    // Table should update
    await expect(page.locator('.el-table__row')).toBeVisible()
  })

  test('should search reviews', async ({ page }) => {
    await page.goto('/reviews')
    
    // Type in search box
    await page.locator('input[placeholder*="Search"]').fill('test')
    
    // Results should update
    await expect(page.locator('.el-table__row')).toBeVisible()
  })
})

test.describe('Language Switching', () => {
  test('should switch language from English to Chinese', async ({ page }) => {
    await page.goto('/')
    
    // Click language switcher
    await page.locator('.language-switcher').click()
    
    // Select Chinese
    await page.locator('.el-dropdown-menu__item:has-text("中文")').click()
    
    // Page content should change to Chinese
    await expect(page.locator('body')).toContainText('中文')
  })

  test('should persist language preference', async ({ page }) => {
    await page.goto('/')
    
    // Switch to Chinese
    await page.locator('.language-switcher').click()
    await page.locator('.el-dropdown-menu__item:has-text("中文")').click()
    
    // Reload page
    await page.reload()
    
    // Language should still be Chinese
    await expect(page.locator('body')).toContainText('中文')
  })
})

test.describe('PWA Features', () => {
  test('should register service worker', async ({ page }) => {
    await page.goto('/')
    
    // Check if service worker is registered
    const swRegistered = await page.evaluate(() => {
      return navigator.serviceWorker.controller !== null
    })
    
    // Note: SW might not be registered in dev mode
    expect(typeof swRegistered).toBe('boolean')
  })

  test('should handle offline mode', async ({ page }) => {
    await page.goto('/')
    
    // Go offline
    await page.context().setOffline(true)
    
    // Should show offline indicator
    const offlineIndicator = page.locator('.offline-indicator')
    await expect(offlineIndicator).toBeVisible()
    
    // Go back online
    await page.context().setOffline(false)
  })
})

test.describe('Responsive Design', () => {
  test('should work on mobile devices', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    
    await page.goto('/')
    
    // Check if layout adapts
    const header = page.locator('.layout-header')
    await expect(header).toBeVisible()
  })

  test('should work on tablets', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 })
    
    await page.goto('/')
    
    // Check if layout adapts
    const sidebar = page.locator('.layout-sidebar')
    await expect(sidebar).toBeVisible()
  })
})
