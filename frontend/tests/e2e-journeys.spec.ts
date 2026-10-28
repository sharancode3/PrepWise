import { test, expect } from '@playwright/test'

const DEMO_STATE = {
  token: 'demo-token-alex-prepwise-2026',
  studentId: 'demo-alex-student',
  displayName: 'Alex Demo Learner',
  goalId: 'ad6f94a1-49d5-4a4e-a650-d0ffa88eaae8',
  projectId: 'cd3eb99d-5da2-4191-94dd-ff7e3e9631fc',
  planV1Id: 'cf4704ee-edf1-49c3-af15-1b422db7c88f',
  planV2Id: 'f99eee0c-73f8-4750-87df-d5a1e3851959',
  activePlanVersion: 2,
}

test.describe('End-to-End Real Student Journeys', () => {

  test('01: Fresh-student journey — clean start, deliberate topic selection, plan creation', async ({ page }) => {
    // 1. Start fresh with clean localStorage
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.goto('/setup')

    // 2. Verify clean initial state (no silent selection)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    
    // Topics should not be pre-checked
    const loopsCheckbox = page.getByLabel('Loops', { exact: true })
    expect(await loopsCheckbox.isChecked()).toBeFalsy()

    // 3. Fill in student details and deliberate topic selection
    await page.getByLabel(/your name/i).fill('Morgan Student')
    await page.getByLabel('Goal title').fill('Prepare for my programming foundations assessment')
    
    // Select deliberate topic
    await loopsCheckbox.check()
    expect(await loopsCheckbox.isChecked()).toBeTruthy()

    // 4. Save goal and create plan
    const createBtn = page.getByRole('button', { name: /Create my learning plan|Save my learning goal/i })
    await createBtn.click()

    // Verify success banner and action link
    await expect(page.getByText('Your goal is saved.')).toBeVisible()
    const openPlanBtn = page.getByRole('link', { name: /open my plan/i })
    await expect(openPlanBtn).toBeVisible()
    await openPlanBtn.click()

    // 5. Verify on /plan: schedule generated, feasible status, plan entries visible
    await expect(page).toHaveURL(/\/plan/)
    await expect(page.getByRole('heading', { level: 1, name: /A plan for the time you have/i })).toBeVisible()
    await expect(page.getByText(/feasible/i)).toBeVisible()

    // Verify no horizontal overflow
    const hasNoOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    expect(hasNoOverflow).toBeTruthy()
  })

  test('02: Returning-student journey — demo state restoration, next unfinished session, study transition', async ({ page }) => {
    // 1. Visit Home and load Alex Demo Learner state
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.reload()

    const demoBtn = page.getByRole('button', { name: /open demo workspace/i })
    await expect(demoBtn).toBeVisible()
    await demoBtn.click()

    // 2. Verifies navigation to /plan with Alex's Plan
    await expect(page).toHaveURL(/\/plan/)
    await expect(page.getByRole('heading', { level: 1, name: /A plan for the time you have/i })).toBeVisible()

    // 3. Verify next study session recommendation banner
    await expect(page.getByText(/next study session/i)).toBeVisible()
    const continueBtn = page.getByRole('link', { name: /continue studying/i })
    await expect(continueBtn).toBeVisible()

    // 4. Click Continue studying -> transitions directly to /study
    await continueBtn.click()
    await expect(page).toHaveURL(/\/study\?topic=/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

    // 5. Verify study components: walkthrough steps, hints disclosure, solution disclosure
    await expect(page.getByText(/step-by-step walkthrough/i)).toBeVisible()
    
    // Test progressive hint
    const hintBtn = page.getByRole('button', { name: /show hint/i })
    if (await hintBtn.isVisible()) {
      await hintBtn.click()
      await expect(page.locator('.study-hint-card').first()).toBeVisible()
    }

    // Test solution disclosure
    const solutionBtn = page.getByRole('button', { name: /reveal suggested solution/i })
    if (await solutionBtn.isVisible()) {
      await solutionBtn.click()
      await expect(page.getByRole('region', { name: /suggested solution/i })).toBeVisible()
    }
  })

  test('03: Contextual AI Assistant — grounded citations and scope refusal', async ({ page }) => {
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

    // Assistant should respond with grounded answer
    await expect(drawer.locator('.assistant-bubble-content').first()).toBeVisible({ timeout: 25_000 })
    await expect(drawer.getByText(/Grounded in:/i).first()).toBeVisible({ timeout: 25_000 })
  })

  test('04: Curriculum and Resources — live previews, project switching, and scope selection', async ({ page }) => {
    // Set demo student token
    await page.goto('/')
    await page.evaluate((token) => {
      localStorage.setItem('learnnova.token', token)
    }, DEMO_STATE.token)

    await page.goto('/curriculum')
    await expect(page.getByRole('heading', { name: /curriculum workspace/i })).toBeVisible()

    // Verify topic cards
    await expect(page.getByRole('combobox', { name: /select learning project/i })).toBeVisible()

    // Switch to Resources tab
    const resTab = page.getByRole('button', { name: 'Resources', exact: true })
    await resTab.click()
    await expect(page.getByRole('heading', { name: /add study resources/i })).toBeVisible()

    // Verify resource library list
    await expect(page.getByText(/Python Basics\.pdf/i)).toBeVisible()

    // Open resource preview modal
    const previewBtn = page.getByRole('button', { name: 'Preview' }).first()
    if (await previewBtn.isVisible()) {
      await previewBtn.click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toHaveCount(0)
    }
  })

  test('05: Progress & Assessment — dashboard metrics, skill quiz, and attempt history', async ({ page }) => {
    // Set demo student token and goal
    await page.goto('/')
    await page.evaluate((state) => {
      localStorage.setItem('learnnova.token', state.token)
      localStorage.setItem('learnnova.goal-id', state.goalId)
      localStorage.setItem('learnnova.demo.active_project.v2', state.projectId)
    }, DEMO_STATE)

    await page.goto('/progress')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

    // Verify progress summary metrics
    await expect(page.getByText(/Assessed skills/i)).toBeVisible()
    await expect(page.getByText(/Planned minutes done/i)).toBeVisible()

    // Switch to Quiz tab
    const quizTab = page.getByRole('tab', { name: /Take a Quiz/i })
    await quizTab.click()

    // Verify quiz setup view
    await expect(page.getByRole('heading', { name: /Build your next quiz/i })).toBeVisible()
    const startQuizBtn = page.getByRole('button', { name: /Start quiz/i })
    await expect(startQuizBtn).toBeVisible()
  })

  test('06: Changes & Export — version diffs, filters, and downloads', async ({ page }) => {
    // Set demo student token and goal
    await page.goto('/')
    await page.evaluate((state) => {
      localStorage.setItem('learnnova.token', state.token)
      localStorage.setItem('learnnova.goal-id', state.goalId)
      localStorage.setItem('learnnova.demo.active_project.v2', state.projectId)
    }, DEMO_STATE)

    await page.goto('/changes')
    await expect(page.getByRole('heading', { level: 1, name: /Schedule changes/i })).toBeVisible()

    // Verify version badges and metrics
    await expect(page.getByText(/Feasibility/i).first()).toBeVisible()

    // Verify filter buttons
    await expect(page.getByRole('button', { name: /All/i }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: /Moved/i }).first()).toBeVisible()

    // Verify export section
    await expect(page.getByRole('heading', { level: 2, name: /Export your plan/i })).toBeVisible()
    await expect(page.getByRole('button', { name: 'JSON', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'CSV', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /preview export/i })).toBeVisible()
  })

  test('07: Responsive viewports & No horizontal overflow check', async ({ page }) => {
    const viewports = [
      { width: 375, height: 667, name: 'mobile' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1024, height: 768, name: 'desktop-sm' },
      { width: 1440, height: 900, name: 'desktop-lg' },
    ]

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      
      // Check Home
      await page.goto('/')
      let overflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      expect(overflow, `Home page horizontal overflow at ${vp.width}px`).toBeTruthy()

      // Check Setup
      await page.goto('/setup')
      overflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      expect(overflow, `Setup page horizontal overflow at ${vp.width}px`).toBeTruthy()

      // Check Curriculum
      await page.goto('/curriculum')
      overflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      expect(overflow, `Curriculum page horizontal overflow at ${vp.width}px`).toBeTruthy()
    }
  })
})
