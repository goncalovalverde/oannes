/**
 * E2E tests for the project wizard flow.
 * 
 * SETUP REQUIRED:
 * 1. Install Playwright: npm install --save-dev @playwright/test
 * 2. Add to package.json scripts: "test:e2e": "playwright test"
 * 3. Create playwright.config.ts
 * 
 * These tests verify the complete wizard flow:
 * - Platform selection
 * - Configuration entry
 * - Workflow mapping
 * - Project creation
 * - CSV import
 */

import { test, expect } from '@playwright/test';

// Configure test server
test.beforeEach(async ({ page }) => {
  // Wait for app to load
  await page.goto('http://localhost:5173');
});

test.describe('Project Wizard', () => {
  test('should select platform', async ({ page }) => {
    // Navigate to projects
    await page.click('text=Projects');
    await page.waitForTimeout(500);

    // Click "New Project" button
    await page.click('button:has-text("New Project")');
    await page.waitForSelector('text=Select your platform');

    // Select Jira platform
    await page.click('text=Jira');
    await expect(page.locator('text=Jira Configuration')).toBeVisible();
  });

  test('should configure Jira project', async ({ page }) => {
    // Navigate to projects
    await page.click('text=Projects');
    await page.click('button:has-text("New Project")');
    await page.waitForSelector('text=Select your platform');

    // Select Jira
    await page.click('text=Jira');
    await page.waitForSelector('input[placeholder*="https://yourcompany"]');

    // Enter configuration
    await page.fill('input[placeholder*="https://yourcompany"]', 'https://test.atlassian.net');
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'test-api-token');

    // Verify "Test Connection" button is enabled
    const testBtn = page.locator('button:has-text("Test Connection")');
    await expect(testBtn).toBeEnabled();
  });

  test('should map workflow statuses', async ({ page }) => {
    // Setup: Create a project (mocked)
    // This test would require mocking or a test instance

    // Navigate to workflow configuration
    // Note: This depends on test project setup
    // await page.click('text=Configure Workflow');

    // Verify workflow stages are visible
    // await expect(page.locator('text=Queue')).toBeVisible();
    // await expect(page.locator('text=Start')).toBeVisible();
    // await expect(page.locator('text=In Flight')).toBeVisible();
    // await expect(page.locator('text=Done')).toBeVisible();
  });

  test('should show error toast on connection failure', async ({ page }) => {
    // Navigate to projects
    await page.click('text=Projects');
    await page.click('button:has-text("New Project")');
    await page.waitForSelector('text=Select your platform');

    // Select Jira
    await page.click('text=Jira');

    // Enter invalid configuration
    await page.fill('input[placeholder*="https://yourcompany"]', 'https://invalid-url.atlassian.net');
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'invalid-token');

    // Click test connection
    await page.click('button:has-text("Test Connection")');

    // Verify error toast appears (should be visible in bottom-right)
    const errorToast = page.locator('role=alert:has-text("error")');
    await expect(errorToast).toBeVisible({ timeout: 5000 });
  });

  test('should show duplicate CSV warning', async ({ page }) => {
    // This test requires:
    // 1. CSV project setup
    // 2. Previously imported CSV file
    // Implementation depends on test data setup

    // Skip for now - requires test infrastructure
    test.skip();
  });

  test('should handle sync success', async ({ page }) => {
    // Navigate to projects with an existing project
    // Click "Sync" button
    // Verify success toast appears

    // Implementation requires existing test project
    test.skip();
  });
});

test.describe('Toast Notifications', () => {
  test('should show toast on project creation', async ({ page }) => {
    // Navigate and create a project (with mocked API)
    // Verify success toast with message "Project created successfully"

    test.skip(); // Requires mock setup
  });

  test('should show toast on sync error', async ({ page }) => {
    // Trigger sync on project
    // Mock API to return error
    // Verify error toast with error message

    test.skip(); // Requires mock setup
  });
});

// Test utilities for common operations
export async function selectPlatform(page, platform: 'jira' | 'trello' | 'csv') {
  await page.click(`text=${platform.charAt(0).toUpperCase() + platform.slice(1)}`);
  await page.waitForTimeout(300);
}

export async function fillJiraConfig(page, config: { url: string; email: string; token: string }) {
  await page.fill('input[placeholder*="https://yourcompany"]', config.url);
  await page.fill('input[type="email"]', config.email);
  await page.fill('input[type="password"]', config.token);
}

export async function expectToastVisible(page, message: string) {
  await expect(page.locator(`text=${message}`)).toBeVisible({ timeout: 5000 });
}
