import { test, expect } from '@playwright/test'

test('study experience: grounded learning journey, progressive hints, and diagram on desktop', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/study')

  // Check header & title
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 25_000 })
  await expect(page.getByText(/Session Overview/i)).toBeVisible()
  await expect(page.getByText(/Grounded Concept Explanation/i)).toBeVisible()
  await expect(page.getByText(/Worked Demonstration/i)).toBeVisible()
  await expect(page.getByText(/Guided Practice & Progressive Hints/i)).toBeVisible()

  // Verify custom SVG diagram exists and is visible if diagram was rendered
  const diagram = page.locator('.study-diagram-panel svg')
  if (await diagram.count() > 0) {
    await expect(diagram).toBeVisible()
  }

  // Verify progressive hint interaction
  const hintBtn = page.getByRole('button', { name: /Show hint/i })
  await expect(hintBtn).toBeVisible()
  await hintBtn.scrollIntoViewIfNeeded()
  await hintBtn.click()
  await expect(page.locator('.study-hint-badge').first()).toBeVisible()

  // Verify solution disclosure
  const solutionBtn = page.getByRole('button', { name: /Reveal Suggested Solution/i })
  await expect(solutionBtn).toBeVisible()
  await solutionBtn.scrollIntoViewIfNeeded()
  await solutionBtn.click()
  await expect(page.getByRole('region', { name: /Suggested Solution/i })).toBeVisible()

  // Verify desktop width has no horizontal overflow
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()

  // Save desktop screenshot
  await page.screenshot({ path: 'test-results/study-desktop.png', fullPage: true })
})

test('study experience: responsive mobile layout at 375px', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/study')

  // Wait for content
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 25_000 })

  // Verify no horizontal overflow on mobile
  const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  expect(noOverflow).toBeTruthy()

  // Verify interactive controls remain accessible on mobile
  const hintBtn = page.getByRole('button', { name: /Show hint/i })
  await expect(hintBtn).toBeVisible()
  await hintBtn.scrollIntoViewIfNeeded()
  await hintBtn.click()
  await expect(page.locator('.study-hint-badge').first()).toBeVisible()

  // Save mobile screenshot
  await page.screenshot({ path: 'test-results/study-mobile.png', fullPage: true })
})

test('study experience: topic query parameter resolution', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/study?topic=loops')

  // Content should load topic objective or title
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 25_000 })
  await expect(page.getByText(/Session Overview/i)).toBeVisible()
  await expect(page.getByText(/Track assignment|Trace range bounds/i).first()).toBeVisible()
})
