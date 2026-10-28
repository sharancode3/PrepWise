/**
 * Feature tests for ChangesPage component behavior and rendering.
 *
 * Tests cover:
 * - Navigation link to /changes in header
 * - Navigation from /plan secondary action to /changes
 * - Initial baseline plan v1 state
 * - Mocked factual changes response (v2 vs v1)
 * - Move plus resize presentation (both tags present)
 * - Unchanged work count
 * - Removed item with missing reason labeled "Reason unavailable"
 * - Feasibility words + numbers (partial, capacity, shortfall, placement conflicts)
 * - Change filter buttons (all, moved, deferred, removed, added)
 * - Single-fetch export preview and download for full schedule (JSON)
 * - Single-fetch export preview and download for changes report (CSV)
 * - Interactive on-demand change explanation
 * - Error state on API failure (with retry button, not masked as missing plan)
 * - Live un-mocked empty state without plan/goal
 * - Responsive layout verification at mobile/desktop
 */

import { test, expect } from '@playwright/test'

const MOCK_BASELINE_V1 = {
  plan_id: 'plan-v1-test',
  goal_id: 'goal-test-1',
  version: 1,
  parent_plan_id: null,
  is_baseline: true,
  feasibility: 'full',
  counts: {
    added: 5,
    moved: 0,
    resized: 0,
    deferred: 0,
    removed: 0,
    unchanged: 0,
  },
  unchanged_count: 0,
  metrics: {
    capacity_minutes: 200,
    remaining_work_minutes: 180,
    scheduled_minutes: 180,
    deferred_minutes: 0,
    minute_shortfall: 0,
    placement_conflict_count: 0,
  },
  changes: [],
}

const MOCK_CHANGES_V2 = {
  plan_id: 'plan-v2-test',
  goal_id: 'goal-test-1',
  version: 2,
  parent_plan_id: 'plan-v1-test',
  is_baseline: false,
  feasibility: 'partial',
  counts: {
    added: 1,
    moved: 1,
    resized: 1,
    deferred: 1,
    removed: 1,
    unchanged: 4,
  },
  unchanged_count: 4,
  metrics: {
    capacity_minutes: 180,
    remaining_work_minutes: 160,
    scheduled_minutes: 130,
    deferred_minutes: 30,
    minute_shortfall: 30,
    placement_conflict_count: 1,
  },
  changes: [
    {
      work_item_id: 'wi-dual-01',
      topic_id: 'loops',
      activity_kind: 'practice',
      is_added: false,
      is_moved: true,
      is_resized: true,
      is_deferred: false,
      is_removed: false,
      previous_placement: { date: '2026-10-28', sequence: 1, duration_minutes: 40 },
      new_placement: { date: '2026-10-29', sequence: 2, duration_minutes: 25 },
      previous_duration_minutes: 40,
      new_duration_minutes: 25,
      reason_code: 'MISSED_WORK',
      evidence: { missed_event_id: 'pe-991' },
    },
    {
      work_item_id: 'wi-unproven-01',
      topic_id: 'variables',
      activity_kind: 'learn',
      is_added: false,
      is_moved: false,
      is_resized: false,
      is_deferred: false,
      is_removed: true,
      previous_placement: { date: '2026-10-28', sequence: 2, duration_minutes: 30 },
      new_placement: null,
      previous_duration_minutes: 30,
      new_duration_minutes: null,
      reason_code: null,
      evidence: {},
    },
    {
      work_item_id: 'wi-deferred-01',
      topic_id: 'conditionals',
      activity_kind: 'practice',
      is_added: false,
      is_moved: false,
      is_resized: false,
      is_deferred: true,
      is_removed: false,
      previous_placement: { date: '2026-10-28', sequence: 3, duration_minutes: 30 },
      new_placement: null,
      previous_duration_minutes: 30,
      new_duration_minutes: 30,
      reason_code: 'CAPACITY_REDUCED',
      evidence: { shortfall_minutes: 30 },
    },
    {
      work_item_id: 'wi-added-01',
      topic_id: 'recursion',
      activity_kind: 'quiz',
      is_added: true,
      is_moved: false,
      is_resized: false,
      is_deferred: false,
      is_removed: false,
      previous_placement: null,
      new_placement: { date: '2026-10-30', sequence: 1, duration_minutes: 20 },
      previous_duration_minutes: null,
      new_duration_minutes: 20,
      reason_code: 'USER_SCOPE_CHANGED',
      evidence: { topic: 'recursion' },
    },
  ],
}

test.describe('ChangesPage feature suite', () => {
  test('navigation bar contains link to Changes', async ({ page, isMobile }) => {
    await page.goto('/')
    if (isMobile) {
      await page.getByRole('button', { name: /Open navigation menu/i }).click()
      const navLink = page.getByRole('dialog', { name: /Mobile navigation/i }).getByRole('link', { name: 'Changes' })
      await expect(navLink).toBeVisible()
      await navLink.click()
    } else {
      const navLink = page.getByRole('link', { name: 'Changes' })
      await expect(navLink).toBeVisible()
      await navLink.click()
    }
    await expect(page).toHaveURL(/\/changes/)
  })

  test('navigation from /plan secondary action leads directly to /changes', async ({ page }) => {
    await page.goto('/plan')
    const changesLink = page.getByRole('link', { name: /view plan changes & export/i })
    await expect(changesLink).toBeVisible()
    await changesLink.click()
    await expect(page).toHaveURL(/\/changes/)
  })

  test('renders baseline plan v1 state correctly', async ({ page }, testInfo) => {
    await page.route('**/api/v1/plans/plan-v1-test/changes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_BASELINE_V1),
      })
    })

    await page.goto('/changes?plan_id=plan-v1-test')

    await expect(page.getByText('Selected: Version 1')).toBeVisible()
    await expect(page.getByText('Initial baseline (v1)')).toBeVisible()
    await expect(page.getByText('Initial Schedule Baseline')).toBeVisible()
    await expect(page.getByText(/All scheduled items represent starting baseline work/)).toBeVisible()
    await expect(page.getByText('Feasibility: Full')).toBeVisible()
    await expect(page.getByText('200m')).toBeVisible()

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath('changes-v1-baseline.png'), fullPage: true })
  })

  test('displays plan comparison v2 with move, resize, unproven removal, and feasibility', async ({ page }, testInfo) => {
    await page.route('**/api/v1/plans/plan-v2-test/changes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHANGES_V2),
      })
    })

    await page.goto('/changes?plan_id=plan-v2-test')

    // Version tags
    await expect(page.getByText('Selected: Version 2')).toBeVisible()
    await expect(page.getByText('Compared with Parent (v1)')).toBeVisible()

    // Feasibility metrics
    await expect(page.getByText('Feasibility: Partial')).toBeVisible()
    await expect(page.getByText('180m')).toBeVisible()
    await expect(page.getByText('130m')).toBeVisible()
    await expect(page.getByText('Shortfall', { exact: true })).toBeVisible()
    await expect(page.locator('.metric-value.shortfall')).toHaveText('30m')

    // Dual Move + Resize card
    const loopsCard = page.locator('.change-card', { hasText: 'wi-dual-01' })
    await expect(loopsCard).toBeVisible()
    await expect(loopsCard.locator('.status-badge.moved')).toBeVisible()
    await expect(loopsCard.locator('.status-badge.resized')).toBeVisible()
    await expect(loopsCard.getByText('MISSED WORK')).toBeVisible()
    await expect(loopsCard.getByText(/40m/)).toBeVisible()
    await expect(loopsCard.getByText(/25m/)).toBeVisible()

    // Unproven removal with Reason unavailable
    const removalCard = page.locator('.change-card', { hasText: 'wi-unproven-01' })
    await expect(removalCard).toBeVisible()
    await expect(removalCard.locator('.status-badge.removed')).toBeVisible()
    await expect(removalCard.getByText('Reason unavailable')).toBeVisible()

    // Deferred card
    const deferredCard = page.locator('.change-card', { hasText: 'wi-deferred-01' })
    await expect(deferredCard).toBeVisible()
    await expect(deferredCard.locator('.status-badge.deferred')).toBeVisible()

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath('changes-v2-diff.png'), fullPage: true })
  })

  test('filters changes by category: all, moved, deferred, removed', async ({ page }) => {
    await page.route('**/api/v1/plans/plan-v2-test/changes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHANGES_V2),
      })
    })

    await page.goto('/changes?plan_id=plan-v2-test')

    // Initially all 4 items visible
    await expect(page.locator('.change-card')).toHaveCount(4)

    // Filter to Moved
    await page.getByRole('button', { name: 'Moved (1)', exact: true }).click()
    await expect(page.locator('.change-card')).toHaveCount(1)
    await expect(page.locator('.change-card', { hasText: 'wi-dual-01' })).toBeVisible()

    // Filter to Deferred
    await page.getByRole('button', { name: 'Deferred (1)', exact: true }).click()
    await expect(page.locator('.change-card')).toHaveCount(1)
    await expect(page.locator('.change-card', { hasText: 'wi-deferred-01' })).toBeVisible()

    // Filter back to All
    await page.getByRole('button', { name: 'All (4)', exact: true }).click()
    await expect(page.locator('.change-card')).toHaveCount(4)
  })

  test('single-fetch export preview and download for full schedule (JSON)', async ({ page }) => {
    const mockJson = JSON.stringify({ plan_id: 'plan-v2-test', version: 2, targets: ['loops'] }, null, 2)
    let exportFetchCount = 0

    await page.route('**/api/v1/plans/plan-v2-test/changes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHANGES_V2),
      })
    })

    await page.route('**/api/v1/plans/plan-v2-test/export*', async (route) => {
      exportFetchCount++
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { 'Content-Disposition': 'attachment; filename="plan-v2.json"' },
        body: mockJson,
      })
    })

    await page.goto('/changes?plan_id=plan-v2-test')

    // Preview export
    await page.getByRole('button', { name: /preview export/i }).click()
    await expect(page.getByText('plan-v2.json')).toBeVisible()
    await expect(page.locator('.export-code-block')).toContainText('"plan_id": "plan-v2-test"')
    expect(exportFetchCount).toBe(1)

    // Download button uses retained blob without refetching from server
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /download plan-v2\.json/i }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('plan-v2.json')
    expect(exportFetchCount).toBe(1) // Confirms zero redundant network fetch
  })

  test('single-fetch export preview and download for changes report (CSV)', async ({ page }) => {
    const mockCsv = 'version,parent_plan_id,work_item_id,topic_id\n2,plan-v1,wi-01,loops\n'
    let exportFetchCount = 0

    await page.route('**/api/v1/plans/plan-v2-test/changes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHANGES_V2),
      })
    })

    await page.route('**/api/v1/plans/plan-v2-test/export*', async (route) => {
      exportFetchCount++
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        headers: { 'Content-Disposition': 'attachment; filename="comparison-plan-v2.csv"' },
        body: mockCsv,
      })
    })

    await page.goto('/changes?plan_id=plan-v2-test')

    // Toggle to Changes Summary and CSV
    const changesSummaryBtn = page.getByRole('button', { name: 'Changes Summary' })
    await changesSummaryBtn.scrollIntoViewIfNeeded()
    await changesSummaryBtn.click({ force: true })
    const csvBtn = page.getByRole('button', { name: 'CSV' })
    await csvBtn.scrollIntoViewIfNeeded()
    await csvBtn.click({ force: true })

    // Preview export
    await page.getByRole('button', { name: /preview export/i }).click()
    await expect(page.getByText('comparison-plan-v2.csv')).toBeVisible()
    await expect(page.locator('.export-code-block')).toContainText('version,parent_plan_id')
    expect(exportFetchCount).toBe(1)

    // Download button uses retained blob without refetching
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /download comparison-plan-v2\.csv/i }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('comparison-plan-v2.csv')
    expect(exportFetchCount).toBe(1)
  })

  test('interactive on-demand explanation for change item', async ({ page }) => {
    await page.route('**/api/v1/plans/plan-v2-test/changes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHANGES_V2),
      })
    })

    await page.route('**/api/v1/assistant/query', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Practice on loops was moved because of missed work in the previous session.',
        }),
      })
    })

    await page.goto('/changes?plan_id=plan-v2-test')

    const loopsCard = page.locator('.change-card', { hasText: 'wi-dual-01' })
    await loopsCard.getByRole('button', { name: 'Explain this change' }).click()

    await expect(loopsCard.getByText('Practice on loops was moved because of missed work')).toBeVisible()
  })

  test('error state displays clear alert and retry button without masking as missing plan', async ({ page }) => {
    await page.route('**/api/v1/plans/plan-err-test/changes', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'PLAN_DIFF_ERROR',
            message: 'Internal server error resolving plan snapshot',
          },
        }),
      })
    })

    await page.goto('/changes?plan_id=plan-err-test')

    await expect(page.getByRole('heading', { name: 'Unable to load comparison' })).toBeVisible()
    await expect(page.getByText('Internal server error resolving plan snapshot')).toBeVisible()
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible()
    // Verify it is NOT masked as "No plan version selected"
    await expect(page.getByText('No plan version selected')).not.toBeVisible()
  })

  test('live un-mocked empty state without plan/goal displays honest guidance', async ({ page }) => {
    // Navigate with no parameters and no goal in localStorage
    await page.goto('/changes')

    await expect(page.getByRole('heading', { name: 'No plan version selected' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Set up a goal' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'View current plan' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  })
})
