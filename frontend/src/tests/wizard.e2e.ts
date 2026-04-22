import { test, expect } from '@playwright/test'

test.describe('ProjectWizard E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto('/')
    // Wait for app to load
    await page.waitForLoadState('networkidle')
  })

  test('should display platform selection on first step', async ({ page }) => {
    // Look for Jira and CSV options (guaranteed to exist)
    const jiraOption = page.locator('button:has-text("Jira")')
    const csvOption = page.locator('button:has-text("CSV")')
    
    await expect(jiraOption).toBeVisible()
    await expect(csvOption).toBeVisible()
  })

  test('should navigate to step 2 after selecting a platform', async ({ page }) => {
    // Select Jira platform
    const jiraButton = page.locator('button:has-text("Jira")')
    await jiraButton.click()

    // Find and click Next button
    const nextButton = page.locator('button:has-text("Next →")')
    await expect(nextButton).toBeEnabled()
    await nextButton.click()

    // Should now show configuration form (look for email input)
    const emailInput = page.locator('input[type="email"]')
    await expect(emailInput).toBeVisible()
  })

  test('should validate required fields', async ({ page }) => {
    // Select Jira
    const jiraButton = page.locator('button:has-text("Jira")')
    await jiraButton.click()
    await page.locator('button:has-text("Next →")').click()

    // Try to proceed without filling form
    const testButton = page.locator('button:has-text("Test Connection")')
    await testButton.click()

    // Should show validation errors
    const errorMessage = page.locator('text=is required')
    await expect(errorMessage).toBeVisible()
  })

  test('should show project name requirement', async ({ page }) => {
    // Select platform
    const jiraButton = page.locator('button:has-text("Jira")')
    await jiraButton.click()
    await page.locator('button:has-text("Next →")').click()

    // Try Next without project name
    const nextButton = page.locator('button:has-text("Next →")')
    await expect(nextButton).toBeDisabled()
  })

  test('should navigate back from step 2 to step 1', async ({ page }) => {
    // Go to step 2
    const jiraButton = page.locator('button:has-text("Jira")')
    await jiraButton.click()
    await page.locator('button:has-text("Next →")').click()

    // Click back
    const backButton = page.locator('button:has-text("← Back")')
    await backButton.click()

    // Should be back at platform selection
    const csvButton = page.locator('button:has-text("CSV")')
    await expect(csvButton).toBeVisible()
  })

  test('should allow CSV platform selection', async ({ page }) => {
    // Select CSV platform
    const csvButton = page.locator('button:has-text("CSV")')
    await csvButton.click()

    // Next button should be enabled
    const nextButton = page.locator('button:has-text("Next →")')
    await expect(nextButton).toBeEnabled()
  })

  test('should display disabled platforms correctly', async ({ page }) => {
    // Linear and Shortcut should be disabled
    const linearButton = page.locator('button:has-text("Linear")')
    const shortcutButton = page.locator('button:has-text("Shortcut")')

    await expect(linearButton).toBeDisabled()
    await expect(shortcutButton).toBeDisabled()
  })
})
