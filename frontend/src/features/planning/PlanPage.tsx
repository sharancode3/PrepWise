import { useEffect, useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  CalendarDays,
  Clock,
  Sparkles,
  ArrowRight,
  BookOpen,
  AlertTriangle,
  CheckCircle2,
  GitCompare,
  FileDown,
  Layers,
  RefreshCw,
  Sliders,
} from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { Button, Eyebrow, Notice, Panel } from '../../components/ui'

export type PlanEntry = {
  entry_id: string
  work_item_id: string
  topic_id: string
  topic_title?: string
  activity_kind: 'learn' | 'practice' | 'assess' | 'review'
  date: string
  sequence: number
  duration_minutes: number
  title?: string
  reason_code?: string
}

export type PlanDeferred = {
  work_item_id: string
  topic_id: string
  remaining_minutes: number
  reason_code: string
}

export type Plan = {
  plan_id: string
  goal_id: string
  version: number
  parent_plan_id: string | null
  created_at: string
  reason: string
  is_active: boolean
  feasibility: 'full' | 'partial' | 'no_capacity' | 'FULL' | 'PARTIAL' | 'NO_CAPACITY'
  generation_status?: string
  metrics: {
    capacity_minutes?: number
    available_minutes?: number
    scheduled_minutes: number
    remaining_work_minutes?: number
    deferred_minutes?: number
    unscheduled_minutes?: number
    minute_shortfall?: number
    time_deficit?: number
    placement_conflict_count?: number
  }
  entries: PlanEntry[]
  deferred: PlanDeferred[]
  completed_history?: { work_item_id: string; event_type: string; occurred_at: string }[]
  assumptions?: string[]
}

export function PlanPage() {
  const navigate = useNavigate()
  const [goalId, setGoalId] = useState<string | null>(() => localStorage.getItem('learnnova.goal-id'))
  const [plans, setPlans] = useState<Plan[]>([])
  const [selected, setSelected] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(Boolean(goalId))
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [completedWorkItemIds, setCompletedWorkItemIds] = useState<Set<string>>(new Set())

  // Synchronize goal ID from storage events
  useEffect(() => {
    function handleStorage() {
      const gid = localStorage.getItem('learnnova.goal-id')
      setGoalId(gid)
    }
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [])

  async function load() {
    if (!goalId) return
    setLoading(true)
    setError('')
    try {
      const data = await api<Plan[]>(`/goals/${goalId}/plans`)
      setPlans(data)
      const active = data.find((p) => p.is_active) ?? data[0] ?? null
      setSelected(active)

      // Fetch learning state / completed items if available
      try {
        const state = await api<{ completed_work_items?: string[] }>(`/goals/${goalId}/learning-state`)
        if (state.completed_work_items) {
          setCompletedWorkItemIds(new Set(state.completed_work_items))
        }
      } catch {
        // Fallback to completed_history from plan
        if (active?.completed_history) {
          setCompletedWorkItemIds(new Set(active.completed_history.map((c) => c.work_item_id)))
        }
      }
    } catch (e) {
      if (!(e instanceof ApiError && e.code === 'PLAN_NOT_FOUND')) {
        setError(e instanceof Error ? e.message : 'Unable to load your plans.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [goalId])

  async function generate(mode: 'generate' | 'replan') {
    if (!goalId) return
    setGenerating(true)
    setError('')
    try {
      const goal = await api<{ input_revision: number }>(`/goals/${goalId}`)
      const activePlan = plans.find((plan) => plan.is_active)
      await api(`/goals/${goalId}/plan-jobs`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: goal.input_revision,
          mode,
          base_plan_id: mode === 'replan' ? activePlan?.plan_id : undefined,
        }),
      })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'We couldn’t generate that plan.')
    } finally {
      setGenerating(false)
    }
  }

  // Next unfinished session calculation
  const nextSession = useMemo(() => {
    if (!selected) return null
    return selected.entries.find((entry) => !completedWorkItemIds.has(entry.work_item_id)) ?? null
  }, [selected, completedWorkItemIds])

  if (!goalId) {
    return (
      <section className="container page-section">
        <Eyebrow>My plan</Eyebrow>
        <h1 className="page-title">Start with your study details.</h1>
        <Notice>
          Create a goal and choose availability before generating a schedule.{' '}
          <Link className="text-link" to="/setup">
            Open setup <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </Notice>
      </section>
    )
  }

  const grouped =
    selected?.entries.reduce<Record<string, PlanEntry[]>>((all, entry) => {
      return { ...all, [entry.date]: [...(all[entry.date] ?? []), entry] }
    }, {}) ?? {}

  const activePlan = plans.find((p) => p.is_active)
  const isSelectedActive = selected?.is_active ?? false
  const normFeasibility = selected?.feasibility?.toLowerCase() ?? 'full'

  const availableMins = selected?.metrics.capacity_minutes ?? selected?.metrics.available_minutes ?? 0
  const scheduledMins = selected?.metrics.scheduled_minutes ?? 0
  const deferredMins = selected?.metrics.deferred_minutes ?? selected?.metrics.unscheduled_minutes ?? 0
  const shortfallMins = selected?.metrics.minute_shortfall ?? selected?.metrics.time_deficit ?? 0

  return (
    <section className="container page-section">
      <Eyebrow>My plan / schedule</Eyebrow>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title">A plan for the time you have.</h1>
          <p className="page-intro">
            Deterministic timetable balanced around your availability, prerequisite dependencies, and learning pace.
          </p>
        </div>
        {selected && (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.5rem' }}>
            <Link to="/setup" className="toggle-btn" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              <Sliders size={14} aria-hidden="true" /> Edit availability
            </Link>
            <Link
              to={selected.parent_plan_id ? `/changes?from=${selected.parent_plan_id}&to=${selected.plan_id}` : `/changes`}
              className="toggle-btn"
              style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <GitCompare size={14} aria-hidden="true" /> Compare &amp; export
            </Link>
          </div>
        )}
      </div>

      {error && <Notice error>{error}</Notice>}

      {loading ? (
        <Notice>Loading your saved plans…</Notice>
      ) : !selected ? (
        <Panel>
          <h2>No plan yet</h2>
          <p>Generate your first schedule from the study details you saved in setup.</p>
          <div style={{ marginTop: '1rem' }}>
            <Button onClick={() => generate('generate')} disabled={generating}>
              {generating ? 'Generating…' : 'Generate plan'}
              <Sparkles size={16} aria-hidden="true" />
            </Button>
          </div>
        </Panel>
      ) : (
        <div className="plan-grid">
          <div>
            {/* Toolbar */}
            <div className="plan-toolbar" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className={`plan-status ${normFeasibility}`}>
                  {normFeasibility === 'full' ? 'Feasible (Full Capacity)' : normFeasibility === 'partial' ? 'Partial Capacity' : 'No Capacity'}
                </span>
                {!isSelectedActive && (
                  <span style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', background: 'var(--dp-color-muted)', borderRadius: '4px', color: 'var(--dp-color-ink-muted)' }}>
                    Viewing historical version (Read-only)
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Button onClick={() => generate('replan')} disabled={generating}>
                  {generating ? 'Replanning…' : 'Replan with current details'}
                  <RefreshCw size={15} aria-hidden="true" />
                </Button>
              </div>
            </div>

            {/* Next session recommendation banner */}
            {nextSession && isSelectedActive && (
              <div
                style={{
                  background: 'rgba(7, 76, 224, 0.05)',
                  border: '1px solid rgba(7, 76, 224, 0.2)',
                  borderRadius: '10px',
                  padding: '1rem 1.25rem',
                  marginBottom: '1.5rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                }}
              >
                <div>
                  <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--dp-color-accent)', fontWeight: 600 }}>
                    Next study session
                  </span>
                  <h3 style={{ margin: '0.25rem 0 0 0', fontSize: '1.05rem', color: 'var(--dp-color-ink)' }}>
                    {nextSession.topic_title || nextSession.title || nextSession.topic_id}
                  </h3>
                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.35rem', fontSize: '0.85rem', color: 'var(--dp-color-ink-muted)' }}>
                    <span>Date: {nextSession.date}</span>
                    <span>Duration: {nextSession.duration_minutes} min</span>
                    <span style={{ textTransform: 'capitalize' }}>Activity: {nextSession.activity_kind}</span>
                  </div>
                </div>
                <Link
                  to={`/study?topic=${nextSession.topic_id}&work_item_id=${nextSession.work_item_id}&plan_id=${selected.plan_id}`}
                  className="button"
                  style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  Continue studying <ArrowRight size={15} aria-hidden="true" />
                </Link>
              </div>
            )}

            {/* Metrics Bar */}
            <Panel className="plan-metrics">
              <div>
                <span>Available time</span>
                <strong>{availableMins} min</strong>
              </div>
              <div>
                <span>Scheduled</span>
                <strong>{scheduledMins} min</strong>
              </div>
              <div>
                <span>Deferred / unscheduled</span>
                <strong>{deferredMins} min</strong>
              </div>
              {shortfallMins > 0 && (
                <div>
                  <span>Time deficit</span>
                  <strong style={{ color: 'var(--dp-color-accent)' }}>{shortfallMins} min</strong>
                </div>
              )}
            </Panel>

            {normFeasibility !== 'full' && (
              <Notice>
                <strong>Schedule constrained:</strong> Some topics could not fit before your target deadline due to daily availability bounds.
                Adjust your daily minutes or extend your deadline in Setup, then replan.
              </Notice>
            )}

            {/* Grouped Day-by-Day Schedule */}
            <div className="schedule-list" style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {Object.keys(grouped).length === 0 ? (
                <Panel>
                  <p>No study sessions scheduled for this period.</p>
                </Panel>
              ) : (
                Object.entries(grouped).map(([dateStr, entries]) => {
                  const dayTotalMins = entries.reduce((sum, e) => sum + e.duration_minutes, 0)
                  return (
                    <Panel key={dateStr} className="day-card" style={{ padding: '1.25rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem', borderBottom: '1px solid var(--dp-color-border)', paddingBottom: '0.5rem' }}>
                        <h2 style={{ fontSize: '1.1rem', margin: 0 }}>
                          {new Date(`${dateStr}T12:00:00`).toLocaleDateString(undefined, {
                            weekday: 'long',
                            month: 'short',
                            day: 'numeric',
                          })}
                        </h2>
                        <span style={{ fontSize: '0.85rem', color: 'var(--dp-color-ink-muted)' }}>
                          {dayTotalMins} min scheduled ({entries.length} {entries.length === 1 ? 'session' : 'sessions'})
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                        {entries.map((entry) => {
                          const isDone = completedWorkItemIds.has(entry.work_item_id)
                          return (
                            <div
                              key={entry.entry_id || entry.work_item_id}
                              className="session-row"
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: '0.75rem 1rem',
                                background: isDone ? 'rgba(34, 197, 94, 0.05)' : 'var(--dp-color-ground)',
                                border: isDone ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid var(--dp-color-border)',
                                borderRadius: '8px',
                                gap: '1rem',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                {isDone ? (
                                  <CheckCircle2 size={18} color="#16a34a" aria-label="Completed" />
                                ) : (
                                  <Clock size={18} color="var(--dp-color-ink-muted)" aria-hidden="true" />
                                )}
                                <div>
                                  <div style={{ fontWeight: 600, color: 'var(--dp-color-ink)', fontSize: '0.95rem' }}>
                                    {entry.topic_title || entry.title || entry.topic_id}
                                  </div>
                                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.2rem' }}>
                                    <span
                                      style={{
                                        fontSize: '0.75rem',
                                        textTransform: 'uppercase',
                                        padding: '0.1rem 0.4rem',
                                        borderRadius: '3px',
                                        background: 'var(--dp-color-muted)',
                                        color: 'var(--dp-color-ink-muted)',
                                        fontWeight: 500,
                                      }}
                                    >
                                      {entry.activity_kind}
                                    </span>
                                    {entry.reason_code && (
                                      <span style={{ fontSize: '0.75rem', color: 'var(--dp-color-ink-muted)' }}>
                                        {entry.reason_code === 'GOAL_TARGET' ? 'Target topic' : 'Prerequisite'}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <strong style={{ fontSize: '0.9rem', whiteSpace: 'nowrap' }}>
                                  {entry.duration_minutes} min
                                </strong>
                                <Link
                                  to={`/study?topic=${entry.topic_id}&work_item_id=${entry.work_item_id}&plan_id=${selected.plan_id}`}
                                  className="toggle-btn"
                                  style={{
                                    textDecoration: 'none',
                                    fontSize: '0.8rem',
                                    padding: '0.35rem 0.75rem',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.3rem',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {isDone ? 'Review' : 'Start'}
                                  <ArrowRight size={13} aria-hidden="true" />
                                </Link>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </Panel>
                  )
                })
              )}
            </div>

            {/* Unscheduled / Deferred Work Panel */}
            {selected.deferred.length > 0 && (
              <Panel style={{ marginTop: '1.5rem' }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
                  <AlertTriangle size={18} color="var(--dp-color-accent)" aria-hidden="true" />
                  Deferred work ({selected.deferred.length} {selected.deferred.length === 1 ? 'item' : 'items'})
                </h2>
                <p style={{ fontSize: '0.85rem', color: 'var(--dp-color-ink-muted)', margin: '0.25rem 0 1rem 0' }}>
                  These work units require more capacity than what was available within the specified horizon.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {selected.deferred.map((item, idx) => (
                    <div
                      key={item.work_item_id || idx}
                      style={{
                        padding: '0.65rem 0.85rem',
                        background: 'var(--dp-color-muted)',
                        borderRadius: '6px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.85rem',
                      }}
                    >
                      <span>
                        <strong>{item.topic_id}</strong> — {item.reason_code.replaceAll('_', ' ').toLowerCase()}
                      </span>
                      <strong>{item.remaining_minutes} min</strong>
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </div>

          {/* Aside: Plan Version History */}
          <aside>
            <Panel>
              <h2 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Plan history</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {plans.map((plan) => {
                  const isSelected = plan.plan_id === selected.plan_id
                  return (
                    <button
                      className={`history-item ${isSelected ? 'selected' : ''}`}
                      key={plan.plan_id}
                      onClick={() => setSelected(plan)}
                      style={{
                        textAlign: 'left',
                        padding: '0.75rem',
                        border: isSelected ? '1px solid var(--dp-color-accent)' : '1px solid var(--dp-color-border)',
                        background: isSelected ? 'rgba(7, 76, 224, 0.05)' : 'var(--dp-color-ground)',
                        borderRadius: '8px',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong style={{ fontSize: '0.95rem' }}>Version {plan.version}</strong>
                        {plan.is_active && (
                          <span
                            style={{
                              fontSize: '0.7rem',
                              background: '#16a34a',
                              color: '#fff',
                              padding: '0.15rem 0.4rem',
                              borderRadius: '4px',
                              fontWeight: 600,
                            }}
                          >
                            Active
                          </span>
                        )}
                      </div>
                      <small style={{ display: 'block', color: 'var(--dp-color-ink-muted)', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                        {new Date(plan.created_at).toLocaleString()}
                        <br />
                        {plan.reason}
                      </small>
                    </button>
                  )
                })}
              </div>
            </Panel>
          </aside>
        </div>
      )}
    </section>
  )
}
