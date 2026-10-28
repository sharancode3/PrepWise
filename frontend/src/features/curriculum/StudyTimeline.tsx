import { useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  Info,
  Layers,
  Loader2,
  RefreshCw,
  Sparkles,
  X,
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
  onSimulateReplan?: () => Promise<void>
  onBackToScope?: () => void
}

// Staggered connector lengths to produce the rhythm from the layout reference
const STAGGER_CONNECTOR_HEIGHTS = [96, 44, 108, 48, 92, 44, 104, 48]

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
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null)
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
          There are currently no sessions in this study plan. Return to study scope selection to choose topics and generate your checklist.
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

  // Active inspected session
  const selectedEntry = plan.entries.find((e) => e.entryId === selectedEntryId) ?? null

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

      {/* Main Timeline / Checklist Card */}
      <div className="section-card timeline-main-card">
        {/* Timeline Header & Summary Bar */}
        <div className="timeline-summary-bar">
          <div className="timeline-summary-left">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h2 style={{ margin: 0, fontSize: 20 }}>Study checklist</h2>
              <span className="timeline-version-pill">Plan v{plan.version}</span>
              <span className={`feasibility-pill ${plan.feasibility}`}>
                {plan.feasibility === 'full' ? 'Full coverage' : 'Partial coverage'}
              </span>
            </div>

            {/* Version Switcher */}
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

            {/* Honest Metric: Sessions completed */}
            <div className="timeline-stats-row">
              <span className="timeline-stat-highlight">
                Sessions completed: <strong>{completedCount}</strong> of <strong>{totalCount}</strong> ({progressPercent}%)
              </span>
              <span className="timeline-stat-divider">·</span>
              <span>
                <strong>{completedMinutes}</strong> of <strong>{totalMinutes}</strong> min total
              </span>
              <span className="timeline-stat-divider">·</span>
              <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                (Checklist tracking only; does not claim mastery)
              </span>
            </div>

            {/* Progress Fill Indicator */}
            <div
              className="timeline-progress-track"
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Sessions completed progress"
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
            (Exercises recoverable error alert)
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
            Horizontal study checklist layout with staggered milestone connectors. Checkbox clicks record local progress across sessions ({totalMinutes} minutes total). Click any milestone card to inspect its actionable steps and related resource.
          </span>
        </div>

        {/* ============================================================ */}
        {/* HORIZONTAL STUDY CHECKLIST (Layout Reference Implementation) */}
        {/* ============================================================ */}
        <div
          className="checklist-scroll-container"
          tabIndex={0}
          role="region"
          aria-label="Horizontal study checklist timeline, scrollable with arrow keys"
        >
          <div className="checklist-diagram">
            {/* The Main Continuous Horizontal Line across all columns */}
            <div className="checklist-horizontal-rail" aria-hidden="true">
              <div
                className="checklist-rail-progress"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Columns Track */}
            <div className="checklist-columns-track" role="list" aria-label="Chronological study milestones">
              {/* Endpoint 0%: Start Connector */}
              <div className="checklist-col checklist-endpoint-col" aria-hidden="true">
                <div className="checklist-connector-vertical" style={{ height: 60 }}>
                  <div className="checklist-marker-dot endpoint-dot" />
                </div>
                <div className="checklist-endpoint-label">0%</div>
                <div className="checklist-endpoint-sub">Start</div>
              </div>

              {/* Chronological Milestones (Sessions) */}
              {plan.entries.map((entry, index) => {
                const isPending = pendingEntryId === entry.entryId
                const isSelected = selectedEntryId === entry.entryId
                const dropHeight = STAGGER_CONNECTOR_HEIGHTS[index % STAGGER_CONNECTOR_HEIGHTS.length]

                return (
                  <div
                    key={entry.entryId}
                    className={`checklist-col checklist-milestone-col ${
                      entry.completed ? 'is-completed' : ''
                    } ${isSelected ? 'is-selected' : ''}`}
                    role="listitem"
                  >
                    {/* Vertical Connector extending downward from horizontal rail */}
                    <div
                      className={`checklist-connector-vertical ${
                        entry.completed ? 'connector-completed' : ''
                      }`}
                      style={{ height: dropHeight }}
                      aria-hidden="true"
                    >
                      {/* Circular Marker at connector end */}
                      <div
                        className={`checklist-marker-dot ${
                          entry.completed ? 'marker-completed' : ''
                        }`}
                      >
                        {isPending ? (
                          <Loader2 size={10} className="animate-spin" />
                        ) : entry.completed ? (
                          <Check size={10} strokeWidth={3} />
                        ) : (
                          <span className="marker-num">{index + 1}</span>
                        )}
                      </div>
                    </div>

                    {/* Milestone Card beneath the marker */}
                    <div
                      className={`checklist-milestone-card ${
                        entry.completed ? 'card-completed' : ''
                      } ${isSelected ? 'card-selected' : ''}`}
                      onClick={() => setSelectedEntryId(entry.entryId)}
                    >
                      {/* Top Checkbox + Concise Title */}
                      <div className="milestone-card-header">
                        <label
                          className="milestone-checkbox-wrap"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            className="milestone-checkbox"
                            checked={entry.completed}
                            disabled={isPending}
                            aria-label={`Mark session ${index + 1}: ${
                              entry.activityTitle ?? entry.summary
                            } on ${entry.topicTitle} as ${
                              entry.completed ? 'incomplete' : 'completed'
                            }`}
                            onChange={(e) => handleCheckboxChange(entry, e.target.checked)}
                          />
                        </label>

                        <h4 className="milestone-card-title" title={entry.activityTitle ?? entry.summary}>
                          {entry.activityTitle ?? entry.summary}
                        </h4>
                      </div>

                      {/* Supporting Metadata: Day, Duration, Kind */}
                      <div className="milestone-card-meta">
                        <span className="milestone-day-pill">{entry.scheduledDay}</span>
                        <span className="milestone-duration-pill">
                          <Clock size={11} aria-hidden="true" />
                          {entry.durationMinutes}m
                        </span>
                        <span className={`milestone-kind-pill ${entry.activityKind}`}>
                          {entry.activityKind}
                        </span>
                      </div>

                      {/* Topic Name */}
                      <div className="milestone-topic-name" title={`Topic: ${entry.topicTitle}`}>
                        {entry.topicTitle}
                      </div>

                      {/* Resource Tag if present */}
                      {entry.resourceName && (
                        <div className="milestone-resource-tag" title={entry.resourceName}>
                          <FileText size={11} aria-hidden="true" />
                          <span className="milestone-resource-text">{entry.resourceName}</span>
                        </div>
                      )}

                      {/* Inspect Action */}
                      <button
                        type="button"
                        className="milestone-inspect-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedEntryId(entry.entryId)
                        }}
                        aria-expanded={isSelected}
                        aria-label={`Inspect activity details for session ${index + 1}`}
                      >
                        Inspect details
                        <ChevronRight size={13} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                )
              })}

              {/* Endpoint 100%: End Connector */}
              <div className="checklist-col checklist-endpoint-col" aria-hidden="true">
                <div className="checklist-connector-vertical" style={{ height: 60 }}>
                  <div
                    className={`checklist-marker-dot endpoint-dot ${
                      progressPercent === 100 ? 'marker-completed' : ''
                    }`}
                  >
                    {progressPercent === 100 && <Check size={10} strokeWidth={3} />}
                  </div>
                </div>
                <div className="checklist-endpoint-label">100%</div>
                <div className="checklist-endpoint-sub">Complete</div>
              </div>
            </div>
          </div>
        </div>

        {/* Mobile Horizontal Scroll Indicator Notice */}
        <div className="checklist-scroll-notice">
          <span>← Scroll horizontally to browse all milestones →</span>
        </div>

        {/* ============================================================ */}
        {/* SESSION ACTIVITY INSPECTION PANEL (When a Milestone is clicked) */}
        {/* ============================================================ */}
        {selectedEntry && (
          <div className="session-inspect-panel" role="region" aria-label="Session details inspection">
            <div className="session-inspect-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span className="milestone-day-pill">{selectedEntry.scheduledDay}</span>
                <span className={`timeline-kind-badge ${selectedEntry.activityKind}`}>
                  {selectedEntry.activityKind}
                </span>
                <span className="timeline-duration-badge">
                  <Clock size={12} aria-hidden="true" />
                  {selectedEntry.durationMinutes} min
                </span>
                <h3 className="session-inspect-title" style={{ margin: 0 }}>
                  {selectedEntry.activityTitle ?? selectedEntry.summary}
                </h3>
              </div>

              <button
                type="button"
                className="close-btn"
                onClick={() => setSelectedEntryId(null)}
                aria-label="Close session details"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="session-inspect-grid">
              <div className="session-inspect-left">
                <div className="session-inspect-topic">
                  Curriculum Topic: <strong>{selectedEntry.topicTitle}</strong>
                </div>
                <p className="session-inspect-summary">{selectedEntry.summary}</p>

                {selectedEntry.steps && selectedEntry.steps.length > 0 && (
                  <div className="session-steps-box">
                    <strong style={{ fontSize: 13, color: 'var(--dp-color-ink)' }}>
                      Actionable session steps:
                    </strong>
                    <ol className="timeline-steps-list">
                      {selectedEntry.steps.map((step, sIdx) => (
                        <li key={sIdx}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>

              <div className="session-inspect-right">
                {selectedEntry.expectedOutcome && (
                  <div className="timeline-outcome-box" style={{ marginTop: 0, marginBottom: 12 }}>
                    <strong style={{ fontSize: 12, color: 'var(--dp-color-accent)' }}>
                      Expected learning outcome:
                    </strong>
                    <p style={{ margin: '4px 0 0 0', fontSize: 13, color: 'var(--dp-color-ink)' }}>
                      {selectedEntry.expectedOutcome}
                    </p>
                  </div>
                )}

                {selectedEntry.resourceName && (
                  <div className="session-resource-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                      <FileText size={14} color="var(--dp-color-accent)" aria-hidden="true" />
                      <strong style={{ fontSize: 12, color: 'var(--dp-color-ink)' }}>
                        Linked study resource:
                      </strong>
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--dp-color-ink)' }}>
                      {selectedEntry.resourceName}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--dp-color-ink-secondary)', marginTop: 2 }}>
                      Grounded citation from project study materials
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 16 }}>
                  <Button
                    variant={selectedEntry.completed ? 'secondary' : 'primary'}
                    onClick={() => handleCheckboxChange(selectedEntry, !selectedEntry.completed)}
                    disabled={pendingEntryId === selectedEntry.entryId}
                  >
                    {selectedEntry.completed ? (
                      <>
                        <Check size={15} aria-hidden="true" />
                        Completed (Click to uncheck)
                      </>
                    ) : (
                      <>
                        <CheckCircle2 size={15} aria-hidden="true" />
                        Mark session completed
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
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
          } else if (onSimulateReplan) {
            await onSimulateReplan()
          }
        }}
      />
    </div>
  )
}
