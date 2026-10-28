/**
 * Feature E: Plan comparison and export screen (ChangesPage).
 *
 * Implements:
 * 1. "What changed": Factual before/after differences vs parent plan (or baseline v1),
 *    change counts (added, moved, resized, deferred, removed, unchanged),
 *    dual move+resize support, and "Reason unavailable" for unverified removals.
 * 2. "Why": Saved reason codes and verified supporting references without causal speculation.
 * 3. "What to do next": Practical navigation actions grounded in the returned factual state.
 * 4. Factual feasibility words + numbers (full/partial/no_capacity, minutes, shortfall, conflicts).
 * 5. Plan export & exact in-app preview: single-fetch of CSV/JSON, Blob retention,
 *    live text preview, and download from the exact same Blob with race prevention and cancellation.
 * 6. Scoped styling adhering to docs/12-ui-ux-design-system.md.
 */

import { useEffect, useRef, useState, useTransition } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileCode,
  FileSpreadsheet,
  Info,
  RefreshCw,
  Sliders,
  Sparkles,
  AlertCircle,
  Filter,
} from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { ActionLink, Button, Eyebrow, Notice, Panel } from '../../components/ui'
import './changes.css'

export interface PlacementInfo {
  date: string
  sequence: number
  duration_minutes: number
}

export interface ChangeItem {
  work_item_id: string
  topic_id: string
  activity_kind: string
  is_added: boolean
  is_moved: boolean
  is_resized: boolean
  is_deferred: boolean
  is_removed: boolean
  previous_placement: PlacementInfo | null
  new_placement: PlacementInfo | null
  previous_duration_minutes: number | null
  new_duration_minutes: number | null
  reason_code: string | null
  evidence: Record<string, unknown>
}

export interface PlanMetrics {
  capacity_minutes: number
  remaining_work_minutes: number
  scheduled_minutes: number
  deferred_minutes: number
  minute_shortfall: number
  placement_conflict_count: number
}

export interface PlanChangesResponse {
  plan_id: string
  goal_id: string
  version: number
  parent_plan_id: string | null
  is_baseline: boolean
  feasibility: 'full' | 'partial' | 'no_capacity'
  counts: {
    added: number
    moved: number
    resized: number
    deferred: number
    removed: number
    unchanged: number
  }
  unchanged_count: number
  metrics: PlanMetrics
  changes: ChangeItem[]
}

type FilterCategory = 'all' | 'moved' | 'added' | 'resized' | 'deferred' | 'removed'

export function ChangesPage() {
  const [searchParams] = useSearchParams()
  const paramPlanId = searchParams.get('plan_id')?.trim() || null

  const [resolvedPlanId, setResolvedPlanId] = useState<string | null>(paramPlanId)
  const [data, setData] = useState<PlanChangesResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<{ message: string; code?: string } | null>(null)
  const [reloadKey, setReloadKey] = useState<number>(0)
  const [activeFilter, setActiveFilter] = useState<FilterCategory>('all')

  // Export & Preview state
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('json')
  const [exportType, setExportType] = useState<'plan' | 'changes'>('plan')
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null)
  const [previewText, setPreviewText] = useState<string | null>(null)
  const [previewFilename, setPreviewFilename] = useState<string>('')
  const [previewLoading, setPreviewLoading] = useState<boolean>(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

  // Token ref to eliminate async race conditions on export preview
  const previewRequestIdRef = useRef<number>(0)
  const previewAbortControllerRef = useRef<AbortController | null>(null)

  // On-demand AI explanation state per card
  const [explanations, setExplanations] = useState<
    Record<string, { loading: boolean; text?: string; error?: string }>
  >({})

  const [, startTransition] = useTransition()

  // 1. Resolve Plan ID if not in query param
  useEffect(() => {
    setError(null)

    if (paramPlanId) {
      setResolvedPlanId(paramPlanId)
      return
    }

    const savedGoalId = localStorage.getItem('learnnova.goal-id')
    if (!savedGoalId) {
      setLoading(false)
      setResolvedPlanId(null)
      return
    }

    let active = true
    setLoading(true)

    api<{ plan_id: string }>(`/goals/${savedGoalId}/plans/current`)
      .then((res) => {
        if (active && res.plan_id) {
          setResolvedPlanId(res.plan_id)
        } else if (active) {
          setResolvedPlanId(null)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (active) {
          setResolvedPlanId(null)
          setLoading(false)
          // Distinguish actual 404 (no plan generated yet) from real network/auth errors
          if (err instanceof ApiError) {
            if (err.code !== 'PLAN_NOT_FOUND') {
              setError({ message: err.message, code: err.code })
            }
          } else {
            setError({ message: 'Unable to reach the server to determine the current plan.' })
          }
        }
      })

    return () => {
      active = false
    }
  }, [paramPlanId, reloadKey])

  // 2. Fetch Comparison Data
  useEffect(() => {
    // Invalidate any in-flight export preview whenever plan changes
    previewRequestIdRef.current++
    if (previewAbortControllerRef.current) {
      previewAbortControllerRef.current.abort()
      previewAbortControllerRef.current = null
    }

    setData(null)
    setPreviewText(null)
    setPreviewBlob(null)
    setPreviewFilename('')
    setPreviewError(null)
    setPreviewLoading(false)
    setExplanations({})

    if (!resolvedPlanId) {
      setLoading(false)
      return
    }

    let active = true
    setLoading(true)
    setError(null)

    api<PlanChangesResponse>(`/plans/${resolvedPlanId}/changes`)
      .then((res) => {
        if (active) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (active) {
          setData(null)
          setLoading(false)
          if (err instanceof ApiError) {
            setError({ message: err.message, code: err.code })
          } else {
            setError({ message: 'Unable to reach the server to load plan comparison.' })
          }
        }
      })

    return () => {
      active = false
    }
  }, [resolvedPlanId, reloadKey])

  // 3. Clear preview when format changes and invalidate active generation token
  useEffect(() => {
    previewRequestIdRef.current++
    if (previewAbortControllerRef.current) {
      previewAbortControllerRef.current.abort()
      previewAbortControllerRef.current = null
    }
    setPreviewText(null)
    setPreviewBlob(null)
    setPreviewFilename('')
    setPreviewError(null)
    setPreviewLoading(false)
  }, [exportFormat, exportType])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      previewRequestIdRef.current++
      previewAbortControllerRef.current?.abort()
    }
  }, [])

  // 4. Feature-local single-fetch for plan export & exact preview with AbortController and generation token
  const handleFetchPreview = async () => {
    if (!resolvedPlanId) return

    if (previewAbortControllerRef.current) {
      previewAbortControllerRef.current.abort()
    }
    const abortController = new AbortController()
    previewAbortControllerRef.current = abortController

    const currentToken = ++previewRequestIdRef.current
    const currentRequestedPlan = resolvedPlanId
    const currentRequestedFormat = exportFormat
    const currentRequestedType = exportType

    setPreviewBlob(null)
    setPreviewText(null)
    setPreviewFilename('')
    setPreviewError(null)
    setPreviewLoading(true)

    try {
      const headers = new Headers()
      const token = localStorage.getItem('learnnova.token')
      if (token) headers.set('X-Local-Token', token)

      const res = await fetch(
        `/api/v1/plans/${resolvedPlanId}/export?format=${exportFormat}&type=${exportType}`,
        {
          headers,
          signal: abortController.signal,
        }
      )

      if (!res.ok) {
        let errMessage = 'Failed to fetch export.'
        try {
          const jsonErr = await res.json()
          if (jsonErr.error?.message) errMessage = jsonErr.error.message
        } catch {
          // ignore
        }
        throw new Error(errMessage)
      }

      if (
        currentToken !== previewRequestIdRef.current ||
        resolvedPlanId !== currentRequestedPlan ||
        exportFormat !== currentRequestedFormat ||
        exportType !== currentRequestedType
      ) {
        return
      }

      let filename = `plan-${resolvedPlanId}-v${data?.version || 1}.${exportFormat}`
      const disposition = res.headers.get('Content-Disposition')
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename="?([^"]+)"?/)
        if (match && match[1]) {
          filename = match[1]
        }
      }

      const blob = await res.blob()
      const text = await blob.text()

      if (currentToken !== previewRequestIdRef.current) {
        return
      }

      startTransition(() => {
        setPreviewBlob(blob)
        setPreviewText(text)
        setPreviewFilename(filename)
        setPreviewLoading(false)
      })
    } catch (err: unknown) {
      if (abortController.signal.aborted) {
        return
      }
      if (currentToken === previewRequestIdRef.current) {
        const msg = err instanceof Error ? err.message : 'Error retrieving export.'
        setPreviewError(msg)
        setPreviewLoading(false)
      }
    }
  }

  // 5. Download the exact same blob as previewed
  const handleDownloadBlob = () => {
    if (!previewBlob) return
    const url = URL.createObjectURL(previewBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = previewFilename || `plan-export.${exportFormat}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => {
      URL.revokeObjectURL(url)
    }, 100)
  }

  // 6. On-demand AI explanation for a specific change using Assistant service
  const handleExplainChange = async (item: ChangeItem) => {
    const wid = item.work_item_id
    if (explanations[wid]?.loading) return

    setExplanations((prev) => ({
      ...prev,
      [wid]: { loading: true },
    }))

    const changeKind = item.is_moved && item.is_resized
      ? 'moved and resized'
      : item.is_moved
      ? 'moved'
      : item.is_resized
      ? 'resized'
      : item.is_deferred
      ? 'deferred'
      : item.is_removed
      ? 'removed'
      : 'added'

    const question = `Explain why work item ${item.work_item_id} (${item.topic_id}) was ${changeKind} with reason '${item.reason_code || 'UNSPECIFIED'}'. What does this mean for my study plan?`

    try {
      const res = await api<{ answer: string }>('/assistant/query', {
        method: 'POST',
        body: JSON.stringify({
          question,
          section: 'changes',
          plan_id: resolvedPlanId,
        }),
      })

      setExplanations((prev) => ({
        ...prev,
        [wid]: { loading: false, text: res.answer },
      }))
    } catch {
      // Deterministic explanation fallback
      const fallback = `This ${item.activity_kind} activity on ${item.topic_id} was ${changeKind} due to ${item.reason_code || 'recorded scheduling adjustment'}. Total duration is now ${item.new_duration_minutes ?? item.previous_duration_minutes ?? 0} minutes.`
      setExplanations((prev) => ({
        ...prev,
        [wid]: { loading: false, text: fallback },
      }))
    }
  }

  // Filtered change items
  const filteredChanges = (data?.changes || []).filter((item) => {
    if (activeFilter === 'all') return true
    if (activeFilter === 'moved') return item.is_moved
    if (activeFilter === 'added') return item.is_added
    if (activeFilter === 'resized') return item.is_resized
    if (activeFilter === 'deferred') return item.is_deferred
    if (activeFilter === 'removed') return item.is_removed
    return true
  })

  // Format readable topic title
  const formatTopicTitle = (topicId: string) => {
    if (!topicId) return 'Topic'
    return topicId
      .split('-')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ')
  }

  // ============================================================================
  // RENDER: Error state takes priority over missing plan check
  // ============================================================================
  if (error) {
    return (
      <section className="container page-section changes-page" aria-labelledby="changes-title">
        <Eyebrow>Plan comparison & export</Eyebrow>
        <h1 id="changes-title" className="changes-title">
          Schedule changes.
        </h1>
        <div className="changes-empty-panel">
          <AlertCircle size={40} color="#dc2626" aria-hidden="true" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>Unable to load comparison</h2>
          <p style={{ color: '#64748b', maxWidth: '520px', margin: '0 auto 24px' }}>
            {error.message}
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              onClick={() => {
                setError(null)
                setReloadKey((k) => k + 1)
              }}
            >
              <RefreshCw size={14} style={{ marginRight: '6px' }} /> Retry
            </Button>
            <ActionLink to="/plan" secondary>
              Return to plan
            </ActionLink>
          </div>
        </div>
      </section>
    )
  }

  // Genuine empty state: no plan ID available and not currently loading
  if (!resolvedPlanId && !loading) {
    return (
      <section className="container page-section changes-page" aria-labelledby="changes-title">
        <Eyebrow>Plan comparison & export</Eyebrow>
        <h1 id="changes-title" className="changes-title">
          Compare plan versions.
          <br />
          See every factual reason.
        </h1>
        <p className="changes-intro">
          Review what changed between your schedules and export your exact plan.
        </p>
        <div className="changes-empty-panel" style={{ marginTop: '2rem' }}>
          <Info size={36} color="var(--color-primary, #074ce0)" aria-hidden="true" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>No plan version selected</h2>
          <p style={{ color: '#64748b', maxWidth: '520px', margin: '0 auto 24px', lineHeight: 1.5 }}>
            To view comparisons, generate a study plan from Setup or select an existing plan version.
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <ActionLink to="/setup">Set up a goal</ActionLink>
            <ActionLink to="/plan" secondary>
              View current plan
            </ActionLink>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="container page-section changes-page" aria-labelledby="changes-title">
      {/* Header */}
      <header className="changes-header">
        <div>
          <Eyebrow>Plan comparison & export</Eyebrow>
          <h1 id="changes-title" className="changes-title">
            Schedule changes.
            <br />
            Before, after, and why.
          </h1>
          <p className="changes-intro">
            Every change reflects genuine schedule placement, duration adjustments, and verified evidence.
          </p>
        </div>

        {data && (
          <div className="version-badges" aria-label="Version comparison status">
            <span className="version-tag active">Selected: Version {data.version}</span>
            {data.parent_plan_id ? (
              <span className="version-tag">Compared with Parent (v{data.version - 1})</span>
            ) : (
              <span className="version-tag">Initial baseline (v1)</span>
            )}
          </div>
        )}
      </header>

      {/* Loading state */}
      {loading && <Notice>Loading plan comparison…</Notice>}

      {data && !loading && (
        <>
          {/* Feasibility Overview Banner */}
          <div className="feasibility-panel">
            <div className="feasibility-title-row">
              <h2 className="feasibility-heading">
                <Sliders size={20} color="var(--color-primary, #074ce0)" aria-hidden="true" />
                <span>
                  Feasibility: <strong style={{ textTransform: 'capitalize' }}>{data.feasibility.replace('_', ' ')}</strong>
                </span>
              </h2>
              <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Plan ID: <code>{data.plan_id}</code>
              </span>
            </div>

            <div className="feasibility-metrics-grid">
              <div className="metric-item">
                <span className="metric-label">Capacity</span>
                <span className="metric-value">{data.metrics.capacity_minutes}m</span>
              </div>
              <div className="metric-item">
                <span className="metric-label">Scheduled</span>
                <span className="metric-value">{data.metrics.scheduled_minutes}m</span>
              </div>
              <div className="metric-item">
                <span className="metric-label">Deferred</span>
                <span className="metric-value">{data.metrics.deferred_minutes}m</span>
              </div>
              <div className="metric-item">
                <span className="metric-label">Shortfall</span>
                <span className={`metric-value ${data.metrics.minute_shortfall > 0 ? 'shortfall' : ''}`}>
                  {data.metrics.minute_shortfall}m
                </span>
              </div>
              <div className="metric-item">
                <span className="metric-label">Placement Conflicts</span>
                <span className="metric-value">{data.metrics.placement_conflict_count}</span>
              </div>
            </div>
          </div>

          {/* SECTION 1: What Changed */}
          <section aria-labelledby="section-what-changed">
            <div className="section-header-row">
              <div>
                <h2 id="section-what-changed" className="section-title">
                  1. What changed
                </h2>
                <p className="section-subtitle">
                  {data.is_baseline
                    ? 'Initial version (v1): Baseline schedule with no parent plan differences.'
                    : `Comparing version ${data.version} against its parent schedule.`}
                </p>
              </div>

              {/* Filters */}
              {!data.is_baseline && (
                <div className="change-filter-pills" role="toolbar" aria-label="Filter changes by category">
                  <button
                    type="button"
                    className={`filter-pill ${activeFilter === 'all' ? 'active' : ''}`}
                    onClick={() => setActiveFilter('all')}
                  >
                    All ({data.changes.length})
                  </button>
                  {data.counts.moved > 0 && (
                    <button
                      type="button"
                      className={`filter-pill ${activeFilter === 'moved' ? 'active' : ''}`}
                      onClick={() => setActiveFilter('moved')}
                    >
                      Moved ({data.counts.moved})
                    </button>
                  )}
                  {data.counts.added > 0 && (
                    <button
                      type="button"
                      className={`filter-pill ${activeFilter === 'added' ? 'active' : ''}`}
                      onClick={() => setActiveFilter('added')}
                    >
                      Added ({data.counts.added})
                    </button>
                  )}
                  {data.counts.resized > 0 && (
                    <button
                      type="button"
                      className={`filter-pill ${activeFilter === 'resized' ? 'active' : ''}`}
                      onClick={() => setActiveFilter('resized')}
                    >
                      Resized ({data.counts.resized})
                    </button>
                  )}
                  {data.counts.deferred > 0 && (
                    <button
                      type="button"
                      className={`filter-pill ${activeFilter === 'deferred' ? 'active' : ''}`}
                      onClick={() => setActiveFilter('deferred')}
                    >
                      Deferred ({data.counts.deferred})
                    </button>
                  )}
                  {data.counts.removed > 0 && (
                    <button
                      type="button"
                      className={`filter-pill ${activeFilter === 'removed' ? 'active' : ''}`}
                      onClick={() => setActiveFilter('removed')}
                    >
                      Removed ({data.counts.removed})
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Changes List */}
            {data.is_baseline ? (
              <div className="changes-empty-panel">
                <CheckCircle2 size={36} color="var(--color-primary, #074ce0)" aria-hidden="true" style={{ margin: '0 auto 12px' }} />
                <h3 style={{ fontSize: '1.15rem', marginBottom: '8px' }}>Initial Schedule Baseline</h3>
                <p style={{ color: '#64748b', maxWidth: '520px', margin: '0 auto 16px' }}>
                  This is the first generated version of your plan. All scheduled items represent starting baseline work. Future replans will compare against this version.
                </p>
                <ActionLink to="/study">Start studying today’s topics</ActionLink>
              </div>
            ) : filteredChanges.length === 0 ? (
              <div className="changes-empty-panel">
                <p style={{ color: '#64748b', margin: 0 }}>
                  {data.changes.length === 0
                    ? `No changes recorded. All ${data.unchanged_count} work items remain in identical placement and duration between versions.`
                    : 'No changes match the selected filter category.'}
                </p>
                {activeFilter !== 'all' && (
                  <button
                    type="button"
                    className="filter-pill"
                    style={{ marginTop: '12px' }}
                    onClick={() => setActiveFilter('all')}
                  >
                    Reset filter
                  </button>
                )}
              </div>
            ) : (
              <div className="changes-list">
                {filteredChanges.map((item) => (
                  <div key={item.work_item_id} className="change-card">
                    <div className="change-card-main">
                      {/* Topic & Activity identity */}
                      <div>
                        <h3 className="change-topic-title">
                          <span>{formatTopicTitle(item.topic_id)}</span>
                          <span className="activity-kind-badge">({item.activity_kind})</span>
                          <div className="status-tags-group">
                            {item.is_added && <span className="status-badge added">Added</span>}
                            {item.is_moved && <span className="status-badge moved">Moved</span>}
                            {item.is_resized && <span className="status-badge resized">Resized</span>}
                            {item.is_deferred && <span className="status-badge deferred">Deferred</span>}
                            {item.is_removed && <span className="status-badge removed">Removed</span>}
                          </div>
                        </h3>
                        <p className="change-id-sub">Work Item: {item.work_item_id}</p>
                      </div>

                      {/* Before / After Placement Comparison */}
                      <div className="placement-comparison-col">
                        <div className="placement-node before">
                          <span className="placement-label">Before</span>
                          {item.previous_placement ? (
                            <span className="placement-val">
                              <Calendar size={13} aria-hidden="true" />
                              {item.previous_placement.date} (#{item.previous_placement.sequence}) · {item.previous_duration_minutes}m
                            </span>
                          ) : (
                            <span style={{ color: '#94a3b8' }}>None</span>
                          )}
                        </div>

                        {/* Semantic Custom Placement Connector */}
                        <svg
                          className="placement-connector-svg"
                          width="28"
                          height="16"
                          viewBox="0 0 28 16"
                          fill="none"
                          aria-hidden="true"
                        >
                          <path
                            d="M2 8H24M24 8L18 3M24 8L18 13"
                            stroke="#074ce0"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>

                        <div className="placement-node after">
                          <span className="placement-label">After</span>
                          {item.new_placement ? (
                            <span className="placement-val">
                              <Calendar size={13} aria-hidden="true" />
                              {item.new_placement.date} (#{item.new_placement.sequence}) · {item.new_duration_minutes}m
                            </span>
                          ) : item.is_deferred ? (
                            <span style={{ color: '#c2410c', fontWeight: 600 }}>
                              Deferred ({item.new_duration_minutes || item.previous_duration_minutes}m)
                            </span>
                          ) : item.is_removed ? (
                            <span style={{ color: '#b91c1c', fontWeight: 600 }}>Removed from schedule</span>
                          ) : (
                            <span style={{ color: '#94a3b8' }}>None</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* SECTION 2: Why */}
                    <div className="change-why-box">
                      <div className="why-reason-text">
                        <span>Reason:</span>
                        <strong>{item.reason_code ? item.reason_code.replace(/_/g, ' ') : 'Reason unavailable'}</strong>
                        {item.evidence && Object.keys(item.evidence).length > 0 && (
                          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                            ({Object.entries(item.evidence).map(([k, v]) => `${k}: ${v}`).join(', ')})
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <button
                          type="button"
                          className="explain-change-btn"
                          onClick={() => handleExplainChange(item)}
                          disabled={explanations[item.work_item_id]?.loading}
                        >
                          <Sparkles size={13} aria-hidden="true" />
                          <span>
                            {explanations[item.work_item_id]?.loading
                              ? 'Explaining...'
                              : 'Explain this change'}
                          </span>
                        </button>
                        {item.topic_id && (
                          <Link
                            to={`/study?topic=${item.topic_id}`}
                            className="explain-change-btn"
                            style={{ color: '#334155' }}
                          >
                            <span>Study topic</span>
                            <ArrowRight size={12} aria-hidden="true" />
                          </Link>
                        )}
                      </div>
                    </div>

                    {/* On-demand explanation bubble */}
                    {explanations[item.work_item_id]?.text && (
                      <div className="ai-change-explanation">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, marginBottom: '4px' }}>
                          <Sparkles size={14} color="#1d4ed8" aria-hidden="true" />
                          <span>Assistant Explanation</span>
                        </div>
                        <div>{explanations[item.work_item_id]!.text}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* SECTION 3: Plan Export & Exact Preview */}
          <section className="export-panel" aria-labelledby="section-export-plan">
            <div className="export-controls-bar">
              <div>
                <h2 id="section-export-plan" className="section-title">
                  3. Export your plan
                </h2>
                <p className="section-subtitle">
                  Preview in-app and download the exact schedule file (version {data.version}).
                </p>
              </div>

              {/* Export scope & format toggles */}
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                {!data.is_baseline && (
                  <div className="format-toggle-group" role="group" aria-label="Export content type">
                    <button
                      type="button"
                      className={`format-btn ${exportType === 'plan' ? 'active' : ''}`}
                      onClick={() => setExportType('plan')}
                    >
                      <span>Full Schedule</span>
                    </button>
                    <button
                      type="button"
                      className={`format-btn ${exportType === 'changes' ? 'active' : ''}`}
                      onClick={() => setExportType('changes')}
                    >
                      <span>Changes Summary</span>
                    </button>
                  </div>
                )}

                <div className="format-toggle-group" role="group" aria-label="Export format">
                  <button
                    type="button"
                    className={`format-btn ${exportFormat === 'json' ? 'active' : ''}`}
                    onClick={() => setExportFormat('json')}
                  >
                    <FileCode size={15} aria-hidden="true" />
                    <span>JSON</span>
                  </button>
                  <button
                    type="button"
                    className={`format-btn ${exportFormat === 'csv' ? 'active' : ''}`}
                    onClick={() => setExportFormat('csv')}
                  >
                    <FileSpreadsheet size={15} aria-hidden="true" />
                    <span>CSV</span>
                  </button>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
              <Button
                variant="secondary"
                onClick={handleFetchPreview}
                disabled={previewLoading}
                aria-label={`Preview export as ${exportFormat.toUpperCase()}`}
              >
                <Eye size={15} style={{ marginRight: '6px' }} />
                <span>{previewLoading ? 'Loading preview…' : 'Preview export'}</span>
              </Button>

              {previewBlob && (
                <Button
                  onClick={handleDownloadBlob}
                  aria-label={`Download ${previewFilename}`}
                >
                  <Download size={15} style={{ marginRight: '6px' }} />
                  <span>Download {exportFormat.toUpperCase()}</span>
                </Button>
              )}
            </div>

            {/* Error in Preview */}
            {previewError && (
              <div style={{ marginTop: '12px' }}>
                <Notice error>{previewError}</Notice>
              </div>
            )}

            {/* Live Text Preview Box */}
            {previewText && (
              <div className="export-preview-container" aria-label="Export file preview">
                <div className="export-preview-header">
                  <span>{previewFilename}</span>
                  <span>{exportFormat.toUpperCase()} Preview</span>
                </div>
                <pre className="export-code-block">{previewText}</pre>
              </div>
            )}
          </section>
        </>
      )}
    </section>
  )
}
