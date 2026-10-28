import { test, expect } from '@playwright/test'

test('assistant: context-aware learning assistant on study page with starter question', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/study?topic=loops')

  // Wait for main page to load
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 25_000 })

  // Trigger button should be visible
  const triggerBtn = page.getByRole('button', { name: /Ask PrepWise/i })
  await expect(triggerBtn).toBeVisible()

  // Open the assistant drawer
  await triggerBtn.click()

  // Drawer should be open
  const drawer = page.getByRole('dialog', { name: /PrepWise Assistant/i })
  await expect(drawer).toBeVisible()

  // Active scope should reflect lesson
  await expect(drawer.getByText(/Lesson:|Loops/i).first()).toBeVisible({ timeout: 10_000 })

  // Starter questions should be rendered
  const starterChip = drawer.getByRole('button', { name: /accumulator variable|simpler terms/i }).first()
  await expect(starterChip).toBeVisible()

  // Click the starter question
  await starterChip.click()

  // Message should appear in user bubble
  await expect(drawer.locator('.user-bubble-content').first()).toBeVisible()

  // Assistant should respond with grounded answer
  await expect(drawer.locator('.assistant-bubble-content').first()).toBeVisible({ timeout: 25_000 })
  await expect(drawer.getByText(/Grounded in:/i).first()).toBeVisible({ timeout: 25_000 })

  // Save desktop assistant screenshot
  await page.screenshot({ path: 'test-results/assistant-desktop.png', fullPage: true })

  // Close drawer with Close button
  const closeBtn = drawer.getByRole('button', { name: /Close assistant/i })
  await closeBtn.click()
  await expect(drawer).not.toBeVisible()
})

test('assistant: responsive mobile drawer layout and scope switching', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/study')

  // Open assistant
  const triggerBtn = page.getByRole('button', { name: /Ask PrepWise/i })
  await expect(triggerBtn).toBeVisible({ timeout: 25_000 })
  await triggerBtn.click()

  const drawer = page.getByRole('dialog', { name: /PrepWise Assistant/i })
  await expect(drawer).toBeVisible()

  // Scope select should be interactive
  const selectElem = drawer.getByRole('combobox', { name: /Select assistant scope/i })
  await expect(selectElem).toBeVisible()

  // Switch to General Learning
  await selectElem.selectOption('general_learning')
  await expect(drawer.getByText(/General Learning/i).first()).toBeVisible({ timeout: 10_000 })

  // Verify mobile width constraints (no horizontal overflow)
  const box = await drawer.boundingBox()
  expect(box).toBeTruthy()
  expect(box!.width).toBeLessThanOrEqual(375)

  // Save mobile screenshot
  await page.screenshot({ path: 'test-results/assistant-mobile.png', fullPage: true })
})
