import { useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  FileText,
  Info,
  Layers,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { Button } from '../../components/ui'
import { ReplanModal } from './ReplanModal'
import { mockCurriculumService } from './mockService'
import type { CurriculumTopic, ReplanRequest, SimulatedPlan, SimulatedPlanEntry } from './types'

export interface StudyTimelineProps {
  plan: SimulatedPlan | null
  projectTitle: string
  topics?: CurriculumTopic[]
  availableVersions?: number[]
  activeVersion?: number
  onSelectVersion?: (version: number) => void
  onToggleSession: (entryId: string, completed: boolean) => Promise<void>
  onReplanWithRequest?: (request: ReplanRequest) => Promise<void>
  onSimulateReplan: () => Promise<void>
  onBackToScope?: () => void
}

export function StudyTimeline({
  plan,
  projectTitle,
  topics = [],
  availableVersions = [1],
  activeVersion = 1,
  onSelectVersion,
  onToggleSession,
  onReplanWithRequest,
  onSimulateReplan,
  onBackToScope,
}: StudyTimelineProps) {
  const [pendingEntryId, setPendingEntryId] = useState<string | null>(null)
  const [isReplanModalOpen, setIsReplanModalOpen] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [simulateErrorActive, setSimulateErrorActive] = useState(
    mockCurriculumService.getSimulateFailure()
  )

  function handleToggleSimulateError(checked: boolean) {
    setSimulateErrorActive(checked)
    mockCurriculumService.setSimulateFailure(checked)
  }

  async function handleCheckboxChange(entry: SimulatedPlanEntry, newCompleted: boolean) {
    setPendingEntryId(entry.entryId)
    setErrorMessage(null)
    try {
      await onToggleSession(entry.entryId, newCompleted)
    } catch (err) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : 'Could not update session completion status. Please try again.'
      )
    } finally {
      setPendingEntryId(null)
    }
  }

  // 1. Empty Plan State
  if (!plan || plan.entries.length === 0) {
    return (
      <div className="section-card timeline-empty-state">
        <Info size={32} className="timeline-empty-icon" aria-hidden="true" />
        <h3>No study sessions scheduled</h3>
        <p className="section-desc">
          There are currently no sessions in this study plan. Return to study scope selection to select topics and generate your timeline.
        </p>
        {onBackToScope && (
          <Button variant="secondary" onClick={onBackToScope}>
            <ArrowLeft size={15} aria-hidden="true" />
            Back to study selection
          </Button>
        )}
      </div>
    )
  }

  // 2. Computed Metrics (totals guaranteed to match entries)
  const completedCount = plan.entries.filter((e) => e.completed).length
  const totalCount = plan.entries.length
  const completedMinutes = plan.entries
    .filter((e) => e.completed)
    .reduce((sum, e) => sum + e.durationMinutes, 0)
  const totalMinutes = plan.entries.reduce((sum, e) => sum + e.durationMinutes, 0)
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className="study-timeline-wrapper">
      {/* Navigation Header */}
      <div className="timeline-top-nav">
        {onBackToScope && (
          <Button variant="secondary" onClick={onBackToScope}>
            <ArrowLeft size={15} aria-hidden="true" />
            Edit study selection
          </Button>
        )}
        <div className="timeline-header-meta">
          <span className="demo-badge">Planning integration preview</span>
          <span style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
            Project: <strong>{projectTitle}</strong>
          </span>
        </div>
      </div>

      {/* Main Timeline Card */}
      <div className="section-card timeline-main-card">
        {/* Timeline Header & Summary Bar */}
        <div className="timeline-summary-bar">
          <div className="timeline-summary-left">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h2 style={{ margin: 0, fontSize: 20 }}>Study timeline</h2>
              <span className="timeline-version-pill">Plan v{plan.version}</span>
              <span className={`feasibility-pill ${plan.feasibility}`}>
                {plan.feasibility === 'full' ? 'Full coverage' : 'Partial coverage'}
              </span>
            </div>

            {/* Version Switcher (Allows switching without overwriting earlier plans) */}
            {availableVersions.length > 1 && (
              <div className="version-selector-group" role="group" aria-label="Study plan versions">
                <span className="version-selector-label">
                  <Layers size={13} aria-hidden="true" /> Available versions:
                </span>
                {availableVersions.map((v) => {
                  const isActive = v === plan.version
                  return (
                    <button
                      key={v}
                      type="button"
                      className={`version-selector-btn ${isActive ? 'active' : ''}`}
                      onClick={() => onSelectVersion?.(v)}
                      aria-pressed={isActive}
                      title={`Switch to Plan v${v}`}
                    >
                      Plan v{v}
                    </button>
                  )
                })}
              </div>
            )}

            <div className="timeline-stats-row">
              <span className="timeline-stat-highlight">
                <strong>{completedCount}</strong> of <strong>{totalCount}</strong> sessions completed
              </span>
              <span className="timeline-stat-divider">·</span>
              <span>
                <strong>{completedMinutes}</strong> of <strong>{totalMinutes}</strong> min total
              </span>
              <span className="timeline-stat-divider">·</span>
              <span style={{ color: 'var(--dp-color-accent)', fontWeight: 600 }}>
                {progressPercent}% progress
              </span>
            </div>

            <div
              className="timeline-progress-track"
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Study plan progress"
            >
              <div
                className="timeline-progress-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          <div className="timeline-summary-actions">
            <Button
              onClick={() => setIsReplanModalOpen(true)}
              title="Open replan dialog to adjust schedule"
            >
              <RefreshCw size={15} aria-hidden="true" />
              Replan schedule
            </Button>
          </div>
        </div>

        {/* Change Summary Card (When viewing an updated version) */}
        {plan.changeSummary && (
          <div className="timeline-change-summary-card">
            <div className="change-summary-header">
              <Sparkles size={16} color="var(--dp-color-accent)" aria-hidden="true" />
              <strong style={{ fontSize: 14 }}>{plan.changeSummary.headline}</strong>
              <span className="change-delta-badge">
                +{plan.changeSummary.durationDeltaMinutes} min total
              </span>
            </div>

            <div className="change-summary-grid">
              <div>
                <span className="change-subheading">Schedule adjustments:</span>
                <ul className="change-bullet-list">
                  {plan.changeSummary.changes.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="change-subheading">Preserved elements:</span>
                <ul className="change-bullet-list preserved">
                  {plan.changeSummary.preservedItems.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="change-handover-notice">
              Person 5 will supply live multi-plan comparison and export diffs in the final integrated platform.
            </div>
          </div>
        )}

        {/* Deterministic Error Test Control */}
        <div className="timeline-test-bar">
          <label className="test-control-label" htmlFor="simulate-network-error-toggle">
            <input
              id="simulate-network-error-toggle"
              type="checkbox"
              checked={simulateErrorActive}
              onChange={(e) => handleToggleSimulateError(e.target.checked)}
              className="test-control-checkbox"
            />
            <span style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
              Deterministic test control: <strong>Simulate network failure on session toggle</strong>
            </span>
          </label>
          <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
            (Exercises recoverable error state)
          </span>
        </div>

        {/* Recoverable Error Banner */}
        {errorMessage && (
          <div className="timeline-error-banner" role="alert">
            <AlertTriangle size={18} className="error-banner-icon" aria-hidden="true" />
            <div style={{ flex: 1 }}>
              <strong>Action could not be synced:</strong> {errorMessage}
            </div>
            <button
              type="button"
              className="close-btn"
              onClick={() => setErrorMessage(null)}
              aria-label="Dismiss error notice"
            >
              ✕
            </button>
          </div>
        )}

        <div className="timeline-honest-disclaimer">
          <Info size={14} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
          <span>
            This timeline previews how Person 3's planner orchestrates study sessions. Durations reflect topic estimates ({totalMinutes} minutes total). Checkbox toggles simulate local session progress without claiming formal mastery or test scores.
          </span>
        </div>

        {/* Vertical Timeline Structure */}
        <div className="vertical-timeline" role="list" aria-label="Scheduled study sessions list">
          {plan.entries.map((entry, index) => {
            const isPending = pendingEntryId === entry.entryId
            const isLast = index === plan.entries.length - 1

            return (
              <div
                key={entry.entryId}
                className={`timeline-item ${entry.completed ? 'is-completed' : ''} ${isPending ? 'is-pending' : ''}`}
                role="listitem"
              >
                {/* Continuous Vertical Guide Line */}
                {!isLast && <div className="timeline-line" aria-hidden="true" />}

                {/* Left: Node & Accessible Checkbox */}
                <div className="timeline-left-col">
                  <div className={`timeline-node ${entry.completed ? 'node-completed' : ''}`} aria-hidden="true">
                    {isPending ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : entry.completed ? (
                      <Check size={14} strokeWidth={3} />
                    ) : (
                      <span className="node-num">{index + 1}</span>
                    )}
                  </div>

                  <label className="timeline-checkbox-label">
                    <input
                      type="checkbox"
                      className="timeline-checkbox"
                      checked={entry.completed}
                      disabled={isPending}
                      aria-label={`Mark session ${index + 1}: ${entry.activityTitle ?? entry.summary} on ${entry.topicTitle} as ${entry.completed ? 'incomplete' : 'completed'}`}
                      onChange={(e) => handleCheckboxChange(entry, e.target.checked)}
                    />
                    <span className="timeline-checkbox-custom" aria-hidden="true">
                      {entry.completed && <CheckCircle2 size={16} color="#1a7f37" />}
                    </span>
                  </label>
                </div>

                {/* Right: Session Details Card */}
                <div className="timeline-card">
                  <div className="timeline-card-header">
                    <div className="timeline-card-meta">
                      <span className="timeline-day-pill">{entry.scheduledDay}</span>
                      <span className={`timeline-kind-badge ${entry.activityKind}`}>
                        {entry.activityKind}
                      </span>
                      <span className="timeline-duration-badge">
                        <Clock size={12} aria-hidden="true" />
                        {entry.durationMinutes} min
                      </span>
                      {entry.resourceName && (
                        <span className="timeline-resource-pill">
                          <FileText size={12} aria-hidden="true" />
                          {entry.resourceName}
                        </span>
                      )}
                    </div>

                    <span className="timeline-version-tag">Plan v{plan.version}</span>
                  </div>

                  <div className="timeline-card-body">
                    <h4 className="timeline-activity-title">
                      {entry.activityTitle ?? entry.summary}
                    </h4>
                    <div className="timeline-topic-ref">
                      Topic: <strong>{entry.topicTitle}</strong>
                    </div>
                    <p className="timeline-summary-text">{entry.summary}</p>
                  </div>

                  {/* Expandable Activity Details (Fixture-grounded) */}
                  {(entry.steps || entry.expectedOutcome) && (
                    <details className="timeline-details-disclosure">
                      <summary className="timeline-details-summary">
                        View session steps & expected outcome
                      </summary>
                      <div className="timeline-disclosure-content">
                        {entry.steps && entry.steps.length > 0 && (
                          <div style={{ marginBottom: 10 }}>
                            <strong style={{ fontSize: 13, color: 'var(--dp-color-ink)' }}>
                              Actionable session steps:
                            </strong>
                            <ol className="timeline-steps-list">
                              {entry.steps.map((step, sIdx) => (
                                <li key={sIdx}>{step}</li>
                              ))}
                            </ol>
                          </div>
                        )}

                        {entry.expectedOutcome && (
                          <div className="timeline-outcome-box">
                            <strong style={{ fontSize: 12, color: 'var(--dp-color-accent)' }}>
                              Expected session outcome:
                            </strong>
                            <p style={{ margin: '4px 0 0 0', fontSize: 13 }}>
                              {entry.expectedOutcome}
                            </p>
                          </div>
                        )}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Replan Modal Dialog */}
      <ReplanModal
        isOpen={isReplanModalOpen}
        topics={topics}
        currentPlanVersion={plan.version}
        onClose={() => setIsReplanModalOpen(false)}
        onSubmitReplan={async (req) => {
          if (onReplanWithRequest) {
            await onReplanWithRequest(req)
          } else {
            await onSimulateReplan()
          }
        }}
      />
    </div>
  )
}
