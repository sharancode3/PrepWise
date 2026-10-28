import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { AlertCircle, Calendar, Clock, RefreshCw, Sparkles, X } from 'lucide-react'
import { Button } from '../../components/ui'
import { SAMPLE_REPLAN_REQUEST_LOOPS } from './fixtures'
import type { CurriculumTopic, ReplanRequest } from './types'

interface ReplanModalProps {
  isOpen: boolean
  topics: CurriculumTopic[]
  currentPlanVersion: number
  onClose: () => void
  onSubmitReplan: (request: ReplanRequest) => Promise<void>
}

export function ReplanModal({
  isOpen,
  topics,
  currentPlanVersion,
  onClose,
  onSubmitReplan,
}: ReplanModalProps) {
  const [reason, setReason] = useState(SAMPLE_REPLAN_REQUEST_LOOPS.reason)
  const [focusTopicIds, setFocusTopicIds] = useState<string[]>(
    SAMPLE_REPLAN_REQUEST_LOOPS.focusTopicIds
  )
  const [deadlineChanged, setDeadlineChanged] = useState(
    SAMPLE_REPLAN_REQUEST_LOOPS.deadlineChanged
  )
  const [newTargetDate, setNewTargetDate] = useState(
    SAMPLE_REPLAN_REQUEST_LOOPS.newTargetDate ?? '2026-11-04'
  )
  const [dailyStudyMinutes, setDailyStudyMinutes] = useState<number>(
    SAMPLE_REPLAN_REQUEST_LOOPS.dailyStudyMinutes
  )
  const [preservePreferences, setPreservePreferences] = useState(
    SAMPLE_REPLAN_REQUEST_LOOPS.preservePreferences
  )
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const firstInputRef = useRef<HTMLTextAreaElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)

  // Focus management & Escape key handling
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    const timer = setTimeout(() => {
      firstInputRef.current?.focus()
    }, 50)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      clearTimeout(timer)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  function toggleFocusTopic(topicId: string) {
    setValidationError(null)
    if (focusTopicIds.includes(topicId)) {
      setFocusTopicIds(focusTopicIds.filter((id) => id !== topicId))
    } else {
      setFocusTopicIds([...focusTopicIds, topicId])
    }
  }

  function applyPreset() {
    setReason(SAMPLE_REPLAN_REQUEST_LOOPS.reason)
    setFocusTopicIds([...SAMPLE_REPLAN_REQUEST_LOOPS.focusTopicIds])
    setDeadlineChanged(true)
    setNewTargetDate('2026-11-04')
    setDailyStudyMinutes(35)
    setPreservePreferences(SAMPLE_REPLAN_REQUEST_LOOPS.preservePreferences)
    setValidationError(null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setValidationError(null)

    // Validation requiring change justification
    if (!reason.trim()) {
      setValidationError('Please explain what you would like to change in your schedule.')
      return
    }

    if (focusTopicIds.length === 0) {
      setValidationError('Please select at least one topic needing more attention.')
      return
    }

    if (dailyStudyMinutes < 15 || dailyStudyMinutes > 180) {
      setValidationError('Daily study minutes must be between 15 and 180 minutes.')
      return
    }

    setSubmitting(true)
    try {
      await onSubmitReplan({
        reason: reason.trim(),
        focusTopicIds,
        deadlineChanged,
        newTargetDate: deadlineChanged ? newTargetDate : undefined,
        dailyStudyMinutes,
        preservePreferences: preservePreferences.trim(),
      })
      onClose()
    } catch (err) {
      setValidationError(
        err instanceof Error ? err.message : 'Could not generate replan preview.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="replan-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-content" ref={modalRef} style={{ maxWidth: 640 }}>
        <div className="modal-header">
          <div>
            <div className="workspace-meta" style={{ marginBottom: 4 }}>
              <span className="demo-badge">Schedule adjustment</span>
              <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                Current: Plan v{currentPlanVersion}
              </span>
            </div>
            <h3 id="replan-modal-title" style={{ margin: 0 }}>
              Replan your study schedule
            </h3>
          </div>
          <button
            type="button"
            className="close-btn"
            onClick={onClose}
            aria-label="Close replan dialog without changes"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <p className="section-desc" style={{ marginBottom: 16 }}>
          Adjust your study pace, target daily minutes, or focus topics. A new plan version will be generated while preserving your completed work.
        </p>

        {/* Quick Sample Preset */}
        <div className="replan-preset-box">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Sparkles size={15} color="var(--dp-color-accent)" aria-hidden="true" />
            <strong style={{ fontSize: 13, color: 'var(--dp-color-ink)' }}>
              Sample supported scenario:
            </strong>
          </div>
          <p style={{ margin: '0 0 8px 0', fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
            “Spend more time on loops and spread the remaining work over more days (capped under 35 min/day).”
          </p>
          <button
            type="button"
            className="text-action-link"
            onClick={applyPreset}
            style={{ fontWeight: 600 }}
          >
            Load sample replan request
          </button>
        </div>

        {validationError && (
          <div className="scope-validation-alert" role="alert" style={{ marginTop: 14 }}>
            <AlertCircle size={16} aria-hidden="true" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ marginTop: 16 }}>
          {/* Question 1: What would you like to change? */}
          <div className="replan-field-group">
            <label htmlFor="replan-reason-input" className="replan-field-label">
              1. What would you like to change?
            </label>
            <textarea
              id="replan-reason-input"
              ref={firstInputRef}
              rows={2}
              className="scope-text-input"
              placeholder="e.g. Spend more time on loops and spread the remaining work over more days."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={250}
            />
          </div>

          {/* Question 2: Which topics need more attention? */}
          <div className="replan-field-group">
            <span className="replan-field-label">
              2. Which topics need more attention?
            </span>
            <div className="replan-topics-chips">
              {topics.map((t) => {
                const isSelected = focusTopicIds.includes(t.id)
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => toggleFocusTopic(t.id)}
                    className={`replan-chip ${isSelected ? 'selected' : ''}`}
                    aria-pressed={isSelected}
                  >
                    {t.title}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Question 3: Has your deadline changed? */}
          <div className="replan-field-group">
            <label className="replan-checkbox-row" htmlFor="deadline-toggle">
              <input
                id="deadline-toggle"
                type="checkbox"
                checked={deadlineChanged}
                onChange={(e) => setDeadlineChanged(e.target.checked)}
                className="scope-checkbox"
              />
              <span className="replan-field-label" style={{ margin: 0 }}>
                3. Has your target deadline changed?
              </span>
            </label>

            {deadlineChanged && (
              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
                <Calendar size={16} color="var(--dp-color-ink-secondary)" aria-hidden="true" />
                <label htmlFor="new-deadline-input" style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
                  New target deadline:
                </label>
                <input
                  id="new-deadline-input"
                  type="date"
                  value={newTargetDate}
                  onChange={(e) => setNewTargetDate(e.target.value)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 6,
                    border: '1px solid var(--dp-color-rule)',
                    fontSize: 13,
                    fontFamily: 'inherit',
                  }}
                />
              </div>
            )}
          </div>

          {/* Question 4: Daily study minutes */}
          <div className="replan-field-group">
            <label htmlFor="daily-minutes-select" className="replan-field-label">
              4. Target daily study minutes
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <Clock size={16} color="var(--dp-color-ink-secondary)" aria-hidden="true" />
              <select
                id="daily-minutes-select"
                value={dailyStudyMinutes}
                onChange={(e) => setDailyStudyMinutes(Number(e.target.value))}
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--dp-color-rule)',
                  fontSize: 14,
                  minWidth: 180,
                }}
              >
                <option value={20}>20 minutes / day (Light)</option>
                <option value={30}>30 minutes / day (Balanced)</option>
                <option value={35}>35 minutes / day (Recommended)</option>
                <option value={45}>45 minutes / day (Focused)</option>
                <option value={60}>60 minutes / day (Intensive)</option>
              </select>
              <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                Avoids schedule overload
              </span>
            </div>
          </div>

          {/* Question 5: What should stay the same? */}
          <div className="replan-field-group">
            <label htmlFor="preserve-prefs-input" className="replan-field-label">
              5. What should stay the same?
            </label>
            <input
              id="preserve-prefs-input"
              type="text"
              className="scope-text-input"
              value={preservePreferences}
              onChange={(e) => setPreservePreferences(e.target.value)}
              placeholder="e.g. Keep completed Day 1 sessions and preserve original resource selections."
            />
          </div>

          {/* Dialog Action Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--dp-color-rule)' }}>
            <Button type="button" variant="secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? (
                <>
                  <RefreshCw size={15} className="animate-spin" aria-hidden="true" />
                  Generating replan…
                </>
              ) : (
                'Preview updated plan'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
