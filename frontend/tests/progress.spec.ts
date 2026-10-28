import { test, expect } from '@playwright/test'

test.describe('Progress and assessment workspace suite', () => {
  test('desktop persistent sidebar navigates to progress and displays correct destinations', async ({ page, isMobile }) => {
    test.skip(isMobile, 'Desktop sidebar test only for desktop viewports')
    await page.goto('/')

    // Verify persistent sidebar presence
    const sidebar = page.locator('.app-sidebar')
    await expect(sidebar).toBeVisible()

    // Verify classified destinations in the sidebar
    await expect(sidebar.getByRole('link', { name: 'Home', exact: true })).toBeVisible()
    await expect(sidebar.getByRole('link', { name: 'Goals & availability' })).toBeVisible()
    await expect(sidebar.getByRole('link', { name: 'Resources' })).toBeVisible()
    await expect(sidebar.getByRole('link', { name: 'My Plan' })).toBeVisible()
    await expect(sidebar.getByRole('link', { name: 'Study' })).toBeVisible()
    await expect(sidebar.getByRole('link', { name: 'Progress' })).toBeVisible()
    await expect(sidebar.getByRole('link', { name: 'Changes & export' })).toBeVisible()

    // Navigate to Progress
    await sidebar.getByRole('link', { name: 'Progress' }).click()
    await expect(page).toHaveURL(/\/progress/)

    // Progress page should be visible
    await expect(page.locator('.page-title')).toBeVisible()
  })

  test('progress page displays honest empty state when no goal exists', async ({ page }) => {
    // Clear any existing goal
    await page.addInitScript(() => {
      localStorage.removeItem('learnnova.goal-id')
    })

    await page.goto('/progress')
    await expect(page.getByText(/No active learning goal found/i)).toBeVisible()
    await expect(page.getByRole('link', { name: /Set up a goal/i })).toBeVisible()
  })

  test('student can save goal and view progress dashboard with assessment quiz tab', async ({ page, isMobile }) => {
    test.skip(isMobile, 'Full quiz flow verified on desktop project')
    await page.goto('/')
    await page.getByRole('link', { name: 'Start with your goal' }).click()
    await page.getByLabel(/your name/i).fill('Progress Student')
    await page.getByLabel('Goal title').fill('Mastery Verification')
    await page.getByLabel('Loops', { exact: true }).check()
    await page.getByRole('button', { name: 'Save my learning goal' }).click()
    await expect(page.getByText('Your goal is saved.')).toBeVisible()

    // Navigate to Progress
    const sidebar = page.locator('.app-sidebar')
    await sidebar.getByRole('link', { name: 'Progress' }).click()
    await expect(page).toHaveURL(/\/progress/)
    await expect(page.getByText(/Your Learning Progress|Mastery Verification/i)).toBeVisible()

    // Verify tab switcher
    const quizTabBtn = page.getByRole('tab', { name: /Take a Quiz/i })
    await expect(quizTabBtn).toBeVisible()
    await quizTabBtn.click()

    // Verify Quiz Setup appears with dynamic topics
    await expect(page.getByText(/Build your next quiz/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /Start quiz/i })).toBeVisible()
  })

  test('mobile drawer opens, lists destinations, and closes on selection', async ({ page, isMobile }) => {
    test.skip(!isMobile, 'Mobile drawer test is only for mobile viewports')

    await page.goto('/')
    const menuBtn = page.getByRole('button', { name: /Open navigation menu/i })
    await expect(menuBtn).toBeVisible()
    await menuBtn.click()

    const drawer = page.getByRole('dialog', { name: /Mobile navigation/i })
    await expect(drawer).toBeVisible()

    const progressLink = drawer.getByRole('link', { name: 'Progress' })
    await expect(progressLink).toBeVisible()
    await progressLink.click()

    await expect(page).toHaveURL(/\/progress/)
    await expect(drawer).not.toBeVisible()
  })
})
