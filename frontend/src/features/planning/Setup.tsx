import { useEffect, useState, useMemo } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, Check, CalendarDays, Clock, SlidersHorizontal, RefreshCw } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ensureProfile, saveGoal } from '../../lib/api'
import type { Curriculum, SavedGoal } from '../../lib/api'
import { Button, Eyebrow, Notice, Panel } from '../../components/ui'

type Familiarity = 'unknown' | 'low' | 'medium' | 'high'

function localDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}

function formatDateLabel(dateStr: string) {
  const d = new Date(`${dateStr}T12:00:00`)
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

function isWeekend(dateStr: string) {
  const day = new Date(`${dateStr}T12:00:00`).getDay()
  return day === 0 || day === 6
}

function generateDateList(start: string, end: string) {
  const dates: string[] = []
  const cursor = new Date(`${start}T12:00:00`)
  const last = new Date(`${end}T12:00:00`)
  while (cursor <= last && dates.length < 31) {
    dates.push(localDate(cursor))
    cursor.setDate(cursor.getDate() + 1)
  }
  return dates
}

export function Setup() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const today = localDate(new Date())
  const later = new Date()
  later.setDate(later.getDate() + 6)

  const [name, setName] = useState('')
  const [title, setTitle] = useState('My next learning goal')
  const [goalText, setGoalText] = useState('')
  const [start, setStart] = useState(today)
  const [end, setEnd] = useState(localDate(later))
  const [defaultMinutes, setDefaultMinutes] = useState(60)

  // Curriculum & topic selections
  const [curriculum, setCurriculum] = useState<Curriculum | null>(null)
  const [availableCurricula, setAvailableCurricula] = useState<{ id: string; title?: string }[]>([])
  const [targets, setTargets] = useState<string[]>([])
  const [familiarity, setFamiliarity] = useState<Record<string, Familiarity>>({})

  // Per-date availability overrides (date -> minutes)
  const [customAvailability, setCustomAvailability] = useState<Record<string, number>>({})
  const [showDateCustomizer, setShowDateCustomizer] = useState(false)

  // Study Preferences
  const [maxSessionMinutes, setMaxSessionMinutes] = useState<number>(25)
  const [preferredPace, setPreferredPace] = useState<'balanced' | 'intensive' | 'relaxed'>('balanced')

  const [error, setError] = useState('')
  const [generationError, setGenerationError] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<SavedGoal | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setGenerationError('')

    api<{ id: string; title?: string }[]>('/curricula')
      .then(async (rows) => {
        if (!rows.length) throw new Error('No curriculum is available yet. Seed the curriculum and try again.')
        if (active) setAvailableCurricula(rows)

        const existingGoalId = localStorage.getItem('learnnova.goal-id')
        let targetCurriculumId = rows[0].id

        if (existingGoalId) {
          try {
            const goal = await api<{
              curriculum_id: string
              title: string
              goal_text: string
              start_date: string
              deadline: string
              targets: { topic_id: string; self_report: Familiarity }[]
              availability: { date: string; minutes: number }[]
            }>(`/goals/${existingGoalId}`)
            if (!active) return

            targetCurriculumId = goal.curriculum_id || rows[0].id
            setTitle(goal.title)
            setGoalText(goal.goal_text)
            setStart(goal.start_date)
            setEnd(goal.deadline)
            setTargets(goal.targets.map((t) => t.topic_id))
            setFamiliarity(Object.fromEntries(goal.targets.map((t) => [t.topic_id, t.self_report])))
            setCustomAvailability(Object.fromEntries(goal.availability.map((row) => [row.date, row.minutes])))
          } catch {
            // Unavailable or deleted local goal; clear stale reference
            localStorage.removeItem('learnnova.goal-id')
            window.dispatchEvent(new Event('storage'))
          }
        }

        const curricData = await api<Curriculum>(`/curricula/${targetCurriculumId}`)
        if (active) {
          setCurriculum(curricData)

          // If topics query param passed from curriculum page, apply them
          const paramTopics = searchParams.get('topics')
          if (paramTopics) {
            const topicList = paramTopics.split(',').filter(Boolean)
            if (topicList.length > 0) {
              setTargets(topicList)
            }
          }
        }
      })
      .catch((e) => {
        if (active) setError(e.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [reload, searchParams])

  const dateList = generateDateList(start, end)

  // Compute final availability array
  const rows = useMemo(() => {
    return dateList.map((d) => ({
      date: d,
      minutes: customAvailability[d] !== undefined ? customAvailability[d] : defaultMinutes,
    }))
  }, [dateList, customAvailability, defaultMinutes])

  const totalAvailableMinutes = rows.reduce((acc, r) => acc + r.minutes, 0)
  const activeDaysCount = rows.filter((r) => r.minutes > 0).length

  // Approximate required minutes for selected topics
  const estimatedRequiredMinutes = useMemo(() => {
    return targets.reduce((sum, tid) => {
      const top = curriculum?.topics.find((t) => String(t.id) === tid)
      if (!top) return sum
      const learn = Number(top.learn_minutes) || 15
      const practice = Number(top.practice_minutes) || 15
      const check = Number(top.check_minutes) || 0
      const fam = familiarity[tid] || 'unknown'
      const adjPractice = fam === 'high' ? Math.ceil(practice * 0.75) : fam === 'medium' ? Math.ceil(practice * 0.85) : practice
      return sum + learn + Math.max(5, adjPractice) + check
    }, 0)
  }, [targets, curriculum, familiarity])

  function applyPreset(type: 'equal' | 'weekdays_more' | 'weekdays_only') {
    const updated: Record<string, number> = {}
    dateList.forEach((d) => {
      if (type === 'equal') {
        updated[d] = defaultMinutes
      } else if (type === 'weekdays_more') {
        updated[d] = isWeekend(d) ? Math.min(480, defaultMinutes * 2) : defaultMinutes
      } else if (type === 'weekdays_only') {
        updated[d] = isWeekend(d) ? 0 : defaultMinutes
      }
    })
    setCustomAvailability(updated)
  }

  function handleDateMinuteChange(d: string, mins: number) {
    setCustomAvailability((prev) => ({
      ...prev,
      [d]: Math.min(480, Math.max(0, mins)),
    }))
  }

  function toggleDateAvailability(d: string) {
    const current = customAvailability[d] !== undefined ? customAvailability[d] : defaultMinutes
    setCustomAvailability((prev) => ({
      ...prev,
      [d]: current === 0 ? defaultMinutes : 0,
    }))
  }

  async function generatePlanForGoal(goalId: string, inputRevision: number) {
    let activePlanId: string | undefined = undefined
    try {
      const curr = await api<{ plan_id: string }>(`/goals/${goalId}/plans/current`)
      activePlanId = curr?.plan_id
    } catch {
      // No active plan yet
    }

    const mode = activePlanId ? 'replan' : 'generate'
    await api(`/goals/${goalId}/plan-jobs`, {
      method: 'POST',
      body: JSON.stringify({
        expected_revision: inputRevision,
        mode,
        base_plan_id: activePlanId,
        max_session_minutes: maxSessionMinutes,
        preferred_pace: preferredPace,
      }),
    })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setGenerationError('')
    setSaved(null)

    if (!curriculum || !targets.length) {
      setError('Choose at least one target topic.')
      return
    }
    if (rows.length < 1 || rows.length > 30) {
      setError('Choose a study period between 1 and 30 days.')
      return
    }

    setSaving(true)
    let savedGoalResult: SavedGoal | null = null

    try {
      const profile = await ensureProfile(name)
      const payloadTargets = targets.map((topic_id) => ({
        topic_id,
        self_report: familiarity[topic_id] || 'unknown',
      }))

      const existingGoalId = localStorage.getItem('learnnova.goal-id')
      const payload = {
        expected_revision: profile.input_revision,
        curriculum_id: curriculum.curriculum_id,
        title,
        goal_text: goalText,
        start_date: start,
        deadline: end,
        targets: payloadTargets,
        availability: rows,
        max_session_minutes: maxSessionMinutes,
        preferred_pace: preferredPace,
      }

      if (existingGoalId) {
        // Send required Idempotency-Key
        const idemKey = crypto.randomUUID()
        savedGoalResult = await api<SavedGoal>(`/goals/${existingGoalId}`, {
          method: 'PATCH',
          headers: { 'Idempotency-Key': idemKey },
          body: JSON.stringify({
            expected_revision: payload.expected_revision,
            title: payload.title,
            goal_text: payload.goal_text,
            start_date: payload.start_date,
            deadline: payload.deadline,
            targets: payloadTargets,
            availability: payload.availability,
            max_session_minutes: maxSessionMinutes,
            preferred_pace: preferredPace,
          }),
        })
      } else {
        savedGoalResult = await saveGoal(payload)
      }

      localStorage.setItem('learnnova.goal-id', savedGoalResult.goal_id)
      window.dispatchEvent(new Event('storage'))

      // Step 2: Generate plan
      try {
        await generatePlanForGoal(savedGoalResult.goal_id, savedGoalResult.input_revision)
        setSaved(savedGoalResult)
      } catch (planErr) {
        setSaved(savedGoalResult)
        setGenerationError('Your details are saved; your plan could not be generated.')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function retryGeneration() {
    if (!saved) return
    setSaving(true)
    setGenerationError('')
    try {
      const g = await api<{ input_revision: number }>(`/goals/${saved.goal_id}`)
      await generatePlanForGoal(saved.goal_id, g.input_revision)
      setGenerationError('')
    } catch (e) {
      setGenerationError('Your details are saved; your plan could not be generated.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="container page-section">
      <Eyebrow>Your workspace / Getting started</Eyebrow>
      <h1 className="page-title">
        Let’s make space<br />for your learning.
      </h1>
      <p className="page-intro">
        A few essentials to give your next step a clear direction. Set your target topics, dates, and realistic availability.
      </p>

      <div className="setup-grid">
        <form onSubmit={submit} className="setup-form" aria-busy={saving}>
          {error && <Notice error>{error}</Notice>}

          {loading ? (
            <Notice>Loading available study options…</Notice>
          ) : (
            <>
              {/* 01: Goal Information */}
              <fieldset>
                <legend>
                  <span>01</span> Who and what
                </legend>
                <label>
                  Your name or nickname
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="E.g. Maria or Alex"
                    maxLength={80}
                  />
                  <span className="field-hint">Used for your local browser profile.</span>
                </label>

                <label>
                  Goal title
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="E.g. Master loops and conditionals"
                    maxLength={120}
                    required
                  />
                </label>

                <label>
                  Goal details (optional)
                  <textarea
                    value={goalText}
                    onChange={(e) => setGoalText(e.target.value)}
                    placeholder="Briefly state what you want to achieve or any specific focus area."
                    rows={2}
                    maxLength={1000}
                  />
                </label>

                {availableCurricula.length > 1 && (
                  <label>
                    Curriculum subject
                    <select
                      value={curriculum?.curriculum_id || ''}
                      onChange={async (e) => {
                        const newId = e.target.value
                        const c = await api<Curriculum>(`/curricula/${newId}`)
                        setCurriculum(c)
                        setTargets([])
                      }}
                    >
                      {availableCurricula.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.title || c.id}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </fieldset>

              {/* 02: Target Topics & Familiarity */}
              <fieldset>
                <legend>
                  <span>02</span> Target topics &amp; familiarity
                </legend>
                <p className="fieldset-desc">
                  Select the concepts you want to learn. State your current familiarity to help tailor practice intensity.
                </p>

                <div className="topic-selection-list">
                  {curriculum?.topics.map((t) => {
                    const tid = String(t.id)
                    const isChecked = targets.includes(tid)
                    return (
                      <div key={tid} className={`topic-row ${isChecked ? 'selected' : ''}`}>
                        <label className="topic-checkbox-label">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setTargets((prev) => [...prev, tid])
                              } else {
                                setTargets((prev) => prev.filter((id) => id !== tid))
                              }
                            }}
                          />
                          <span className="topic-title">{String(t.title)}</span>
                        </label>

                        {isChecked && (
                          <div className="familiarity-picker">
                            <span className="picker-label">Familiarity:</span>
                            <select
                              className="familiarity-select"
                              value={familiarity[tid] || 'unknown'}
                              onChange={(e) => {
                                const val = e.target.value as Familiarity
                                setFamiliarity((prev) => ({ ...prev, [tid]: val }))
                              }}
                            >
                              <option value="unknown">Unknown (Full coverage)</option>
                              <option value="low">Slightly known (Solid practice)</option>
                              <option value="medium">Kind of known (Refresher)</option>
                              <option value="high">Mostly known (Fast-track)</option>
                            </select>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </fieldset>

              {/* 03: Dates & Availability */}
              <fieldset>
                <legend>
                  <span>03</span> Dates &amp; availability
                </legend>
                <div className="date-row">
                  <label>
                    Start date
                    <input type="date" value={start} onChange={(e) => setStart(e.target.value)} required />
                  </label>
                  <label>
                    Deadline
                    <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} required />
                  </label>
                </div>

                <label>
                  Default daily study time (minutes)
                  <input
                    type="number"
                    min={0}
                    max={480}
                    step={15}
                    value={defaultMinutes}
                    onChange={(e) => setDefaultMinutes(Number(e.target.value))}
                  />
                  <span className="field-hint">Applied to all dates unless customized below.</span>
                </label>

                <div className="presets-bar">
                  <span className="presets-label">Quick presets:</span>
                  <button type="button" className="preset-btn" onClick={() => applyPreset('equal')}>
                    Uniform ({defaultMinutes}m/day)
                  </button>
                  <button type="button" className="preset-btn" onClick={() => applyPreset('weekdays_more')}>
                    Weekend intensive (2x)
                  </button>
                  <button type="button" className="preset-btn" onClick={() => applyPreset('weekdays_only')}>
                    Weekdays only
                  </button>
                </div>

                <div className="customizer-toggle-wrapper">
                  <button
                    type="button"
                    className="toggle-customizer-btn"
                    onClick={() => setShowDateCustomizer(!showDateCustomizer)}
                  >
                    <SlidersHorizontal size={14} aria-hidden="true" />
                    {showDateCustomizer ? 'Hide date-by-date customizer' : 'Customize specific dates'}
                  </button>
                </div>

                {showDateCustomizer && (
                  <div className="date-customizer-grid">
                    {rows.map((row) => (
                      <div key={row.date} className={`date-custom-card ${row.minutes === 0 ? 'zero-day' : ''}`}>
                        <div className="date-card-header">
                          <strong>{formatDateLabel(row.date)}</strong>
                          {isWeekend(row.date) && <span className="weekend-badge">Weekend</span>}
                        </div>
                        <div className="date-card-input">
                          <input
                            type="number"
                            min={0}
                            max={480}
                            step={15}
                            value={row.minutes}
                            onChange={(e) => handleDateMinuteChange(row.date, Number(e.target.value))}
                          />
                          <span>min</span>
                          <button
                            type="button"
                            className="toggle-btn"
                            onClick={() => toggleDateAvailability(row.date)}
                          >
                            {row.minutes === 0 ? 'Make available' : 'Mark unavailable'}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </fieldset>

              {/* 04: Study Preferences */}
              <fieldset>
                <legend>
                  <span>04</span> Study preferences
                </legend>
                <div className="preference-grid">
                  <label>
                    Max session unit duration
                    <select
                      className="familiarity-select"
                      value={maxSessionMinutes}
                      onChange={(e) => setMaxSessionMinutes(Number(e.target.value))}
                    >
                      <option value={15}>15 minutes (Bite-sized units)</option>
                      <option value={25}>25 minutes (Standard / Pomodoro)</option>
                      <option value={45}>45 minutes (Deep concentration)</option>
                    </select>
                  </label>
                  <label>
                    Preferred pacing
                    <select
                      className="familiarity-select"
                      value={preferredPace}
                      onChange={(e) => setPreferredPace(e.target.value as 'balanced' | 'intensive' | 'relaxed')}
                    >
                      <option value="balanced">Balanced (Steady daily effort)</option>
                      <option value="intensive">Intensive (Front-load foundations)</option>
                      <option value="relaxed">Relaxed (Gentle progression)</option>
                    </select>
                  </label>
                </div>
              </fieldset>

              <div className="form-actions">
                <Button type="submit" disabled={saving}>
                  {saving ? 'Creating your plan…' : 'Create my learning plan'}
                  <ArrowRight size={17} aria-hidden="true" />
                </Button>
                <span>No file upload needed</span>
              </div>
            </>
          )}

          {generationError && (
            <Notice error>
              <strong>Your details are saved; your plan could not be generated.</strong>
              <p style={{ marginTop: '0.5rem' }}>
                You can retry generating your study timetable with the saved parameters.
              </p>
              <div style={{ marginTop: '0.75rem' }}>
                <Button type="button" onClick={retryGeneration} disabled={saving}>
                  <RefreshCw size={15} aria-hidden="true" />
                  Retry plan generation
                </Button>
              </div>
            </Notice>
          )}

          {saved && !generationError && (
            <Notice>
              <strong>
                <Check size={16} aria-hidden="true" /> Your goal is saved.
              </strong>
              <p>{saved.title} is stored locally and your first schedule is ready.</p>
              <Link className="text-link" to="/plan">
                Open my plan <ArrowRight size={15} aria-hidden="true" />
              </Link>
            </Notice>
          )}
        </form>

        {/* Aside Summary */}
        <aside className="setup-aside">
          <Panel className="summary-panel">
            <span className="icon-tile">
              <CalendarDays size={24} aria-hidden="true" />
            </span>
            <h2>A realistic starting point.</h2>
            <p>Your available time is a planning constraint, not a promise of learning speed.</p>
            <dl>
              <div>
                <dt>Study window</dt>
                <dd>{rows.length > 30 ? 'Choose up to 30' : rows.length} days</dd>
              </div>
              <div>
                <dt>Active study days</dt>
                <dd>{activeDaysCount} of {rows.length} days</dd>
              </div>
              <div>
                <dt>Total allocated time</dt>
                <dd>
                  {rows.length > 30 ? '—' : `${totalAvailableMinutes} min (${(totalAvailableMinutes / 60).toFixed(1)}h)`}
                </dd>
              </div>
              <div>
                <dt>Target topics</dt>
                <dd>{targets.length || 'Not selected'}</dd>
              </div>
              <div>
                <dt>Est. required effort</dt>
                <dd>~{estimatedRequiredMinutes} min</dd>
              </div>
            </dl>
            {totalAvailableMinutes > 0 && estimatedRequiredMinutes > totalAvailableMinutes && (
              <p className="summary-note" style={{ color: 'var(--dp-color-accent)', fontWeight: 600 }}>
                Note: Total capacity ({totalAvailableMinutes}m) is less than estimated required effort ({estimatedRequiredMinutes}m). The planner will schedule priority work and identify deferred items.
              </p>
            )}
            <p className="summary-note">Start with honest inputs. Build a useful plan from there.</p>
          </Panel>
          <p className="aside-note">Already have a local profile? Your saved identity is reused on this browser.</p>
        </aside>
      </div>
    </section>
  )
}
