import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, Check, CalendarDays, Clock, SlidersHorizontal } from 'lucide-react'
import { Link } from 'react-router-dom'
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
  const [targets, setTargets] = useState<string[]>([])
  const [familiarity, setFamiliarity] = useState<Record<string, Familiarity>>({})

  // Per-date availability overrides (date -> minutes)
  const [customAvailability, setCustomAvailability] = useState<Record<string, number>>({})
  const [showDateCustomizer, setShowDateCustomizer] = useState(false)

  // Study Preferences
  const [maxSessionMinutes, setMaxSessionMinutes] = useState<number>(25)
  const [preferredPace, setPreferredPace] = useState<'balanced' | 'intensive' | 'relaxed'>('balanced')

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<SavedGoal | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api<{ id: string }[]>('/curricula')
      .then(async (rows) => {
        if (!rows.length) throw new Error('No curriculum is available yet. Run the curriculum seed command.')
        const data = await api<Curriculum>(`/curricula/${rows[0].id}`)
        if (active) setCurriculum(data)
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
  }, [reload])

  const dateList = generateDateList(start, end)

  // Compute final availability array
  const rows = dateList.map((d) => ({
    date: d,
    minutes: customAvailability[d] !== undefined ? customAvailability[d] : defaultMinutes,
  }))

  const totalAvailableMinutes = rows.reduce((acc, r) => acc + r.minutes, 0)
  const activeDaysCount = rows.filter((r) => r.minutes > 0).length

  // Approximate required minutes for selected topics
  const estimatedRequiredMinutes = targets.reduce((sum, tid) => {
    const top = curriculum?.topics.find((t) => String(t.id) === tid)
    if (!top) return sum
    const learn = Number(top.learn_minutes) || 15
    const practice = Number(top.practice_minutes) || 15
    const check = Number(top.check_minutes) || 0
    const fam = familiarity[tid] || 'unknown'
    const adjPractice = fam === 'high' ? Math.ceil(practice * 0.75) : fam === 'medium' ? Math.ceil(practice * 0.85) : practice
    return sum + learn + Math.max(5, adjPractice) + check
  }, 0)

  // Presets
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

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
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
    try {
      const profile = await ensureProfile(name)
      const payloadTargets = targets.map((topic_id) => ({
        topic_id,
        self_report: familiarity[topic_id] || 'unknown',
      }))
      const result = await saveGoal({
        expected_revision: profile.input_revision,
        curriculum_id: curriculum.curriculum_id,
        title,
        goal_text: goalText,
        start_date: start,
        deadline: end,
        targets: payloadTargets,
        availability: rows,
      })
      setSaved(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Please try again.')
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
        A few essentials to give your next step a clear direction. You can start without uploading a file.
      </p>

      <div className="setup-grid">
        <form onSubmit={submit} className="setup-form" aria-busy={saving}>
          {error && <Notice error>{error}</Notice>}
          {loading ? (
            <Notice>Loading your curriculum…</Notice>
          ) : !curriculum ? (
            <Button type="button" variant="secondary" onClick={() => setReload(reload + 1)}>
              Retry curriculum connection
            </Button>
          ) : (
            <>
              {/* 01: About You */}
              <fieldset>
                <legend>
                  <span>01</span> A little about you
                </legend>
                <div className="form-pair">
                  <label>
                    Your name <span className="optional">(optional)</span>
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={80}
                      placeholder="What should we call you?"
                      autoComplete="given-name"
                    />
                  </label>
                  <label>
                    Goal title
                    <input
                      required
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      maxLength={120}
                    />
                  </label>
                </div>
                <label>
                  What would you like to work toward? <span className="optional">(optional)</span>
                  <textarea
                    value={goalText}
                    onChange={(e) => setGoalText(e.target.value)}
                    maxLength={1000}
                    placeholder="For example, feel confident tracing Python loops."
                    rows={3}
                  />
                </label>
                <p className="field-help">This profile stays in your local workspace. Timezone: Asia/Kolkata.</p>
              </fieldset>

              {/* 02: Target Topics & Familiarity */}
              <fieldset>
                <legend>
                  <span>02</span> Choose your direction & familiarity
                </legend>
                <p className="field-help" id="target-help">
                  {curriculum.title} · Choose your target topics. The planner automatically includes their prerequisites.
                </p>
                <div className="topic-options" aria-describedby="target-help">
                  {curriculum.topics.map((topic) => {
                    const tid = String(topic.id)
                    const isChecked = targets.includes(tid)
                    return (
                      <div className={`topic-select-card ${isChecked ? 'selected' : ''}`} key={tid}>
                        <div className="topic-header">
                          <label className="check-option" style={{ border: 0, padding: 0, minHeight: 'auto', background: 'transparent' }}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) =>
                                setTargets(
                                  e.target.checked
                                    ? [...targets, tid]
                                    : targets.filter((t) => t !== tid)
                                )
                              }
                            />
                            <span>{String(topic.title)}</span>
                          </label>
                          <span className="topic-badge">
                            Lv {Number(topic.difficulty) || 1}
                          </span>
                        </div>

                        {isChecked && (
                          <div>
                            <label style={{ fontSize: '12px', margin: '4px 0 2px' }}>
                              Familiarity:
                              <select
                                className="familiarity-select"
                                value={familiarity[tid] || 'unknown'}
                                onChange={(e) =>
                                  setFamiliarity({
                                    ...familiarity,
                                    [tid]: e.target.value as Familiarity,
                                  })
                                }
                              >
                                <option value="unknown">Unknown / Not yet studied</option>
                                <option value="low">Slightly known (Full practice)</option>
                                <option value="medium">Kind of known (Some practice)</option>
                                <option value="high">Mostly known (Review & verify)</option>
                              </select>
                            </label>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </fieldset>

              {/* 03: Study Window & Daily Availability */}
              <fieldset>
                <legend>
                  <span>03</span> Find your study window & availability
                </legend>
                <div className="form-pair">
                  <label>
                    Start date
                    <input
                      required
                      type="date"
                      value={start}
                      min={today}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <label>
                    Study deadline
                    <input
                      required
                      type="date"
                      value={end}
                      min={start}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </label>
                </div>

                <label>
                  Baseline daily minutes
                  <input
                    required
                    type="number"
                    min={0}
                    max={480}
                    step={5}
                    value={defaultMinutes}
                    onChange={(e) => {
                      const m = Number(e.target.value)
                      setDefaultMinutes(m)
                    }}
                    aria-describedby="minutes-help"
                  />
                </label>
                <p className="field-help" id="minutes-help">
                  Apply a starting capacity, then adjust individual dates or weekday/weekend schedules below.
                </p>

                {/* Preset shortcuts */}
                <div className="preset-btn-group">
                  <button type="button" className="preset-btn" onClick={() => applyPreset('equal')}>
                    Apply equal to all days
                  </button>
                  <button type="button" className="preset-btn" onClick={() => applyPreset('weekdays_more')}>
                    Weekdays {defaultMinutes}m / Weekends {Math.min(480, defaultMinutes * 2)}m
                  </button>
                  <button type="button" className="preset-btn" onClick={() => applyPreset('weekdays_only')}>
                    Weekdays only (Weekends off)
                  </button>
                  <button
                    type="button"
                    className="preset-btn"
                    onClick={() => setShowDateCustomizer(!showDateCustomizer)}
                  >
                    {showDateCustomizer ? 'Hide date overrides' : 'Customize specific dates'}
                  </button>
                </div>

                {/* Specific date overrides */}
                {showDateCustomizer && (
                  <div className="date-override-list">
                    {rows.map((row) => (
                      <div
                        key={row.date}
                        className={`date-row ${row.minutes === 0 ? 'unavailable' : ''}`}
                      >
                        <div>
                          <strong>{formatDateLabel(row.date)}</strong>
                          {isWeekend(row.date) && <span style={{ fontSize: '11px', color: 'var(--dp-color-ink-secondary)', marginLeft: '6px' }}>(Weekend)</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <input
                            type="number"
                            min={0}
                            max={480}
                            step={5}
                            className="date-row-input"
                            value={row.minutes}
                            onChange={(e) => handleDateMinuteChange(row.date, Number(e.target.value))}
                          />
                          <span style={{ fontSize: '12px' }}>min</span>
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
                  {saving ? 'Saving your workspace…' : 'Save my learning goal'}
                  <ArrowRight size={17} aria-hidden="true" />
                </Button>
                <span>No file upload needed</span>
              </div>
            </>
          )}

          {saved && (
            <Notice>
              <strong>
                <Check size={16} aria-hidden="true" /> Your goal is saved.
              </strong>
              <p>{saved.title} is stored locally. Your planning feature can now use these inputs.</p>
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
