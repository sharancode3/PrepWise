import { useEffect, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Award,
  BookOpen,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Compass,
  HelpCircle,
  History,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  TrendingUp,
  X,
  XCircle,
} from 'lucide-react'
import { ActionLink, Button, Eyebrow, Notice, Panel } from '../../components/ui'
import { api } from '../../lib/api'
import type { Profile } from '../../lib/api'
import {
  fetchDashboard,
  fetchQuizHistory,
  recordProgressEvent,
} from './progress-api'
import { ProgressQuizFlow } from './ProgressQuizFlow'
import type {
  DashboardOverviewResponse,
  QuizDifficulty,
  QuizHistoryItem,
  QuizHistoryResponse,
  SkillEvidence,
  WorkItemSummary,
} from './types'
import './progress.css'

type ProgressTab = 'overview' | 'quiz' | 'history'

export function ProgressPage() {
  const [goalId, setGoalId] = useState<string>(
    () => localStorage.getItem('learnnova.goal-id') || ''
  )
  const [profile, setProfile] = useState<Profile | null>(null)
  const [activeTab, setActiveTab] = useState<ProgressTab>('overview')

  // Dashboard Data State
  const [dashboard, setDashboard] = useState<DashboardOverviewResponse | null>(null)
  const [history, setHistory] = useState<QuizHistoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')

  // Pre-configured quiz params when starting from recommendation or skill card
  const [targetSkillId, setTargetSkillId] = useState<string | undefined>(undefined)
  const [targetDifficulty, setTargetDifficulty] = useState<QuizDifficulty | undefined>(undefined)

  // Completion Tracking State per Work Item
  const [updatingItemId, setUpdatingItemId] = useState<string | null>(null)
  const [actualMinutesInput, setActualMinutesInput] = useState<Record<string, number>>({})
  const [actionError, setActionError] = useState<{ itemId: string; message: string; payload: any; idemKey: string } | null>(null)

  // Expandable Quiz History Items
  const [expandedBatchId, setExpandedBatchId] = useState<string | null>(null)

  // Load profile
  useEffect(() => {
    let active = true
    api<Profile>('/me')
      .then((p) => {
        if (active) setProfile(p)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  // Check goal ID from storage if needed
  useEffect(() => {
    if (!goalId) {
      const stored = localStorage.getItem('learnnova.goal-id')
      if (stored) setGoalId(stored)
    }
  }, [goalId])

  // Load Dashboard & History
  const loadDashboardData = (currentGoalId: string) => {
    if (!currentGoalId) return
    setLoading(true)
    setError('')

    Promise.all([
      fetchDashboard(currentGoalId),
      fetchQuizHistory(currentGoalId),
    ])
      .then(([dashData, histData]) => {
        setDashboard(dashData)
        setHistory(histData)
        // Initialize actual minutes map from work items
        const minsMap: Record<string, number> = {}
        for (const item of dashData.scheduled_items) {
          minsMap[item.work_item_id] = item.actual_minutes ?? item.duration_minutes
        }
        setActualMinutesInput(minsMap)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load progress dashboard.')
      })
      .finally(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    if (goalId) {
      loadDashboardData(goalId)
    } else {
      setLoading(false)
    }
  }, [goalId])

  // Handle Mark Completed / Missed
  async function handleRecordEvent(
    item: WorkItemSummary,
    eventType: 'completed' | 'missed',
    existingIdemKey?: string
  ) {
    if (!dashboard || !goalId) return

    setUpdatingItemId(item.work_item_id)
    setActionError(null)

    const idemKey = existingIdemKey || `idem-event-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`
    const actualMinutes = actualMinutesInput[item.work_item_id] ?? item.duration_minutes

    const payload = {
      expected_revision: dashboard.current_revision,
      plan_id: item.plan_id,
      work_item_id: item.work_item_id,
      event_type: eventType,
      actual_minutes: actualMinutes,
    }

    try {
      const receipt = await recordProgressEvent(goalId, payload, idemKey)
      // Update local revision in profile if present
      if (profile) {
        setProfile({ ...profile, input_revision: receipt.new_revision })
      }
      // Reload dashboard data
      loadDashboardData(goalId)
    } catch (err: any) {
      setActionError({
        itemId: item.work_item_id,
        message: err.message || `Failed to mark work as ${eventType}.`,
        payload,
        idemKey,
      })
    } finally {
      setUpdatingItemId(null)
    }
  }

  function handleStartTargetedQuiz(skillId?: string, difficultyLevel?: number) {
    setTargetSkillId(skillId)
    if (difficultyLevel !== undefined) {
      if (difficultyLevel <= 2) setTargetDifficulty('easy')
      else if (difficultyLevel >= 4) setTargetDifficulty('hard')
      else setTargetDifficulty('medium')
    } else {
      setTargetDifficulty('adaptive')
    }
    setActiveTab('quiz')
  }

  if (!goalId) {
    return (
      <section className="container page-section">
        <div className="quiz-flow-header">
          <h1 className="page-title">Progress and Evidence</h1>
          <p className="page-intro">
            Track demonstrated skill mastery, manage study participation, and launch targeted quizzes.
          </p>
        </div>
        <Notice>
          <strong>No active learning goal found</strong>
          <p>Create and save a learning goal to track your curriculum progress and skill evidence.</p>
          <div style={{ marginTop: '12px' }}>
            <ActionLink to="/setup">
              Set up a goal <ArrowRight size={15} aria-hidden="true" />
            </ActionLink>
          </div>
        </Notice>
      </section>
    )
  }

  // Filter skills into Demonstrated vs Needs Attention / Limited
  const demonstratedSkills = dashboard?.skill_evidence.filter(
    (s) => s.evidence_status === 'strong' || (s.evidence_status === 'ordinary' && (s.performance_estimate ?? 0) >= 0.5)
  ) ?? []

  const needsCheckSkills = dashboard?.skill_evidence.filter(
    (s) => s.evidence_status === 'needs_attention' || s.evidence_status === 'limited' || s.evidence_status === 'unknown'
  ) ?? []

  return (
    <section className="container page-section">
      {/* Header and View Tabs */}
      <div className="dashboard-header-row">
        <div>
          <div className="dashboard-meta-badge">
            <Eyebrow>Progress + Evidence</Eyebrow>
            {dashboard && (
              <span className="revision-tag" title="Server State Input Revision">
                Revision: {dashboard.current_revision}
              </span>
            )}
          </div>
          <h1 className="page-title">{dashboard?.goal_title || 'Your Learning Progress'}</h1>
          <p className="page-intro">
            Evidence-based tracking distinguishing daily study participation from verified skill performance.
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="dashboard-tabs" role="tablist" aria-label="Progress views">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'overview'}
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <TrendingUp size={16} aria-hidden="true" />
            Overview
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'quiz'}
            className={`tab-btn ${activeTab === 'quiz' ? 'active' : ''}`}
            onClick={() => {
              setTargetSkillId(undefined)
              setTargetDifficulty(undefined)
              setActiveTab('quiz')
            }}
          >
            <Play size={16} aria-hidden="true" />
            Take a Quiz
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'history'}
            className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <History size={16} aria-hidden="true" />
            Quiz History ({history?.total_quizzes ?? 0})
          </button>
        </div>
      </div>

      {loading && (
        <div className="dashboard-loading-state">
          <RefreshCw className="spin-icon" size={24} aria-hidden="true" />
          <span>Loading verified learning state...</span>
        </div>
      )}

      {error && !loading && (
        <Notice error>
          <strong>Could not load progress data</strong>
          <p>{error}</p>
          <Button variant="secondary" onClick={() => loadDashboardData(goalId)} style={{ marginTop: '8px' }}>
            <RotateCcw size={14} aria-hidden="true" /> Retry
          </Button>
        </Notice>
      )}

      {/* VIEW: OVERVIEW */}
      {!loading && !error && activeTab === 'overview' && dashboard && (
        <div className="overview-content">
          {/* Metrics Bar */}
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Study items completed</span>
              <div className="metric-value">
                {dashboard.completed_work_items_count}{' '}
                <span className="metric-denom">/ {dashboard.total_work_items_count}</span>
              </div>
              <span className="metric-sub">
                {dashboard.total_work_items_count > 0
                  ? `${Math.round((dashboard.completed_work_items_count / dashboard.total_work_items_count) * 100)}% active plan`
                  : 'No active plan items'}
              </span>
            </div>

            <div className="metric-card">
              <span className="metric-label">Planned minutes done</span>
              <div className="metric-value">
                {dashboard.planned_minutes_completed}{' '}
                <span className="metric-denom">/ {dashboard.total_planned_minutes} min</span>
              </div>
              <span className="metric-sub">
                {dashboard.actual_minutes_recorded} actual minutes recorded
              </span>
            </div>

            <div className="metric-card">
              <span className="metric-label">Assessed skills</span>
              <div className="metric-value">
                {dashboard.skills_with_independent_evidence}{' '}
                <span className="metric-denom">/ {dashboard.total_skills_count}</span>
              </div>
              <span className="metric-sub">With verified independent evidence</span>
            </div>

            <div className="metric-card">
              <span className="metric-label">Latest quiz score</span>
              <div className="metric-value">
                {dashboard.latest_quiz_score ? (
                  `${dashboard.latest_quiz_score.score_percent}%`
                ) : (
                  <span className="metric-none">None yet</span>
                )}
              </div>
              <span className="metric-sub">
                {dashboard.latest_quiz_score
                  ? `${dashboard.latest_quiz_score.correct_count}/${dashboard.latest_quiz_score.question_count} correct answers`
                  : 'Take a quiz to start assessment'}
              </span>
            </div>
          </div>

          {/* Mandatory Participation vs Demonstrated Performance Disclaimer */}
          <div className="disclaimer-banner" role="note">
            <Compass size={18} className="disclaimer-icon" aria-hidden="true" />
            <p className="disclaimer-text">{dashboard.disclaimer}</p>
          </div>

          {/* Two-Column Layout */}
          <div className="dashboard-grid">
            {/* LEFT COLUMN: SKILL EVIDENCE */}
            <div className="dashboard-column">
              {/* What you demonstrated */}
              <div className="section-block">
                <div className="section-header-row">
                  <h2 className="section-heading">
                    <Award size={18} className="icon-success" aria-hidden="true" />
                    What you demonstrated
                  </h2>
                  <span className="section-count">{demonstratedSkills.length} skills</span>
                </div>

                {demonstratedSkills.length === 0 ? (
                  <div className="empty-panel">
                    <p className="empty-title">No demonstrated mastery recorded yet</p>
                    <p className="empty-desc">
                      Independent answers without hints demonstrate mastery. Complete quizzes to populate verified evidence.
                    </p>
                  </div>
                ) : (
                  <div className="skill-cards-stack">
                    {demonstratedSkills.map((s) => (
                      <div key={s.skill_id} className="skill-evidence-card strong">
                        <div className="skill-card-top">
                          <div>
                            <span className="skill-name">{s.skill_id}</span>
                            <span className="skill-status-tag success">
                              {s.evidence_status === 'strong' ? 'Strong Evidence' : 'Assessed'}
                            </span>
                          </div>
                          {s.performance_estimate !== null && (
                            <span className="estimate-score">
                              {Math.round(s.performance_estimate * 100)}% estimate
                            </span>
                          )}
                        </div>
                        <div className="skill-card-metrics">
                          <span>{s.independent_count} independent answers</span>
                          <span>•</span>
                          <span>{s.supported_count} supported practice</span>
                        </div>
                        <div className="skill-card-action">
                          <button
                            type="button"
                            className="btn-text-action"
                            onClick={() => handleStartTargetedQuiz(s.skill_id, 3)}
                          >
                            Reinforce skill <ArrowRight size={13} aria-hidden="true" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* What needs another check */}
              <div className="section-block">
                <div className="section-header-row">
                  <h2 className="section-heading">
                    <AlertCircle size={18} className="icon-alert" aria-hidden="true" />
                    What needs another check
                  </h2>
                  <span className="section-count">{needsCheckSkills.length} skills</span>
                </div>

                {needsCheckSkills.length === 0 ? (
                  <div className="empty-panel">
                    <p className="empty-title">All assessed skills in good standing</p>
                    <p className="empty-desc">No active skill flags requiring immediate diagnostic checks.</p>
                  </div>
                ) : (
                  <div className="skill-cards-stack">
                    {needsCheckSkills.map((s) => {
                      const isNeedsAttn = s.evidence_status === 'needs_attention'
                      const isLimited = s.evidence_status === 'limited'
                      return (
                        <div
                          key={s.skill_id}
                          className={`skill-evidence-card ${isNeedsAttn ? 'needs-attention' : 'neutral'}`}
                        >
                          <div className="skill-card-top">
                            <div>
                              <span className="skill-name">{s.skill_id}</span>
                              <span
                                className={`skill-status-tag ${
                                  isNeedsAttn ? 'alert' : isLimited ? 'subtle' : 'unknown'
                                }`}
                              >
                                {isNeedsAttn
                                  ? 'Needs Attention'
                                  : isLimited
                                  ? 'Limited Evidence'
                                  : 'No Evidence Yet'}
                              </span>
                            </div>
                            {s.performance_estimate !== null && (
                              <span className="estimate-score warning">
                                {Math.round(s.performance_estimate * 100)}%
                              </span>
                            )}
                          </div>

                          <p className="skill-reason-note">
                            {isNeedsAttn &&
                              `Recent performance (${Math.round(
                                (s.performance_estimate ?? 0) * 100
                              )}%) is below standard across ${s.independent_count} independent checks.`}
                            {isLimited &&
                              `Only ${s.independent_count} independent answer recorded. More fresh questions are needed before diagnosing performance.`}
                            {s.evidence_status === 'unknown' &&
                              'No questions attempted for this skill yet. Fresh baseline check needed.'}
                          </p>

                          <div className="skill-card-action">
                            <button
                              type="button"
                              className="btn-text-action alert"
                              onClick={() => handleStartTargetedQuiz(s.skill_id, isNeedsAttn ? 2 : 3)}
                            >
                              {isNeedsAttn ? 'Take Targeted Quiz' : 'Check Skill'} <ArrowRight size={13} aria-hidden="true" />
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT COLUMN: RECOMMENDATIONS & SCHEDULED WORK */}
            <div className="dashboard-column">
              {/* STAGE 6: ADAPTIVE RECOMMENDATION CARD */}
              {dashboard.recommendation && (
                <div className="recommendation-card">
                  <div className="rec-header">
                    <span className="rec-badge">
                      <Sparkles size={14} aria-hidden="true" />
                      Recommended Next Step
                    </span>
                    <span className="rec-diff-tag">
                      {dashboard.recommendation.difficulty_label}
                    </span>
                  </div>

                  <h3 className="rec-title">
                    {dashboard.recommendation.priority_skill_title ||
                      dashboard.recommendation.priority_skill_id ||
                      'Comprehensive Practice'}
                  </h3>

                  <p className="rec-explanation">
                    {dashboard.recommendation.factual_explanation}
                  </p>

                  <div className="rec-footer">
                    <span className="rec-count-note">
                      {dashboard.recommendation.available_count} questions ready
                      {dashboard.recommendation.is_supported_practice_only &&
                        ' (supported practice)'}
                    </span>
                    <Button
                      variant="primary"
                      onClick={() =>
                        handleStartTargetedQuiz(
                          dashboard.recommendation?.priority_skill_id ?? undefined,
                          dashboard.recommendation?.effective_difficulty ?? 3
                        )
                      }
                    >
                      <Play size={14} aria-hidden="true" /> Start targeted quiz
                    </Button>
                  </div>
                </div>
              )}

              {/* STAGE 7: SCHEDULED WORK & COMPLETION CONTROLS */}
              <div className="scheduled-work-panel">
                <div className="section-header-row">
                  <h2 className="section-heading">
                    <Calendar size={18} aria-hidden="true" />
                    Scheduled Study Work
                  </h2>
                  <span className="section-count">
                    {dashboard.scheduled_items.length} items
                  </span>
                </div>

                {!dashboard.has_active_plan ? (
                  <div className="empty-panel">
                    <p className="empty-title">No active study plan</p>
                    <p className="empty-desc">
                      Create and generate an active plan in the Planner to track daily study tasks.
                    </p>
                    <div style={{ marginTop: '12px' }}>
                      <ActionLink to="/planner">
                        Open Planner <ArrowRight size={14} aria-hidden="true" />
                      </ActionLink>
                    </div>
                  </div>
                ) : dashboard.scheduled_items.length === 0 ? (
                  <div className="empty-panel">
                    <p className="empty-title">No items scheduled</p>
                    <p className="empty-desc">All scheduled items for this version have been reviewed.</p>
                  </div>
                ) : (
                  <div className="work-items-list">
                    {dashboard.scheduled_items.map((item) => {
                      const isPending = item.state === 'pending'
                      const isCompleted = item.state === 'completed'
                      const isMissed = item.state === 'missed'
                      const isUpdating = updatingItemId === item.work_item_id

                      return (
                        <div key={item.work_item_id} className={`work-item-row ${item.state}`}>
                          <div className="item-main-details">
                            <div className="item-title-row">
                              <span className="item-title">{item.title}</span>
                              <span className={`item-kind-tag ${item.kind}`}>{item.kind}</span>
                              <span className={`item-state-badge ${item.state}`}>
                                {isCompleted && <Check size={12} aria-hidden="true" />}
                                {isMissed && <X size={12} aria-hidden="true" />}
                                {item.state}
                              </span>
                            </div>

                            <div className="item-meta-info">
                              <span>
                                <Clock size={12} aria-hidden="true" /> {item.duration_minutes} min planned
                              </span>
                              {item.actual_minutes !== null && item.actual_minutes !== undefined && (
                                <span>• {item.actual_minutes} min recorded</span>
                              )}
                              <span>• Date: {item.study_date}</span>
                            </div>
                          </div>

                          {/* Completion / Missed Controls */}
                          {isPending && (
                            <div className="item-action-controls">
                              <div className="actual-minutes-wrapper">
                                <label
                                  htmlFor={`mins-${item.work_item_id}`}
                                  className="actual-minutes-label"
                                >
                                  Mins:
                                </label>
                                <input
                                  id={`mins-${item.work_item_id}`}
                                  type="number"
                                  min="1"
                                  max="480"
                                  value={actualMinutesInput[item.work_item_id] ?? item.duration_minutes}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10) || 0
                                    setActualMinutesInput({
                                      ...actualMinutesInput,
                                      [item.work_item_id]: val,
                                    })
                                  }}
                                  className="actual-minutes-input"
                                  disabled={isUpdating}
                                />
                              </div>

                              <div className="action-buttons-group">
                                <button
                                  type="button"
                                  className="btn-mark-completed"
                                  disabled={isUpdating}
                                  onClick={() => handleRecordEvent(item, 'completed')}
                                >
                                  {isUpdating ? 'Saving...' : 'Mark Done'}
                                </button>
                                <button
                                  type="button"
                                  className="btn-mark-missed"
                                  disabled={isUpdating}
                                  onClick={() => handleRecordEvent(item, 'missed')}
                                >
                                  Missed
                                </button>
                              </div>
                            </div>
                          )}

                          {actionError && actionError.itemId === item.work_item_id && (
                            <div className="work-item-error-box">
                              <span>{actionError.message}</span>
                              <button
                                type="button"
                                className="btn-retry-action"
                                onClick={() =>
                                  handleRecordEvent(item, actionError.payload.event_type, actionError.idemKey)
                                }
                              >
                                Retry
                              </button>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW: TAKE A QUIZ */}
      {activeTab === 'quiz' && (
        <div className="quiz-tab-content">
          <div className="quiz-subnav-bar">
            <button
              type="button"
              className="btn-back-dashboard"
              onClick={() => {
                setActiveTab('overview')
                loadDashboardData(goalId)
              }}
            >
              ← Back to Progress Overview
            </button>
          </div>
          <ProgressQuizFlow
            initialGoalId={goalId}
            initialSkillId={targetSkillId}
            initialDifficulty={targetDifficulty}
            onReturnToDashboard={() => {
              setActiveTab('overview')
              loadDashboardData(goalId)
            }}
          />
        </div>
      )}

      {/* VIEW: QUIZ HISTORY */}
      {activeTab === 'history' && (
        <div className="history-tab-content">
          <div className="history-header-summary">
            <div>
              <h2 className="history-title">Persisted Quiz Sessions</h2>
              <p className="history-subtitle">
                Server-scored quiz attempts persisted in durable storage.
              </p>
            </div>
            {history && (
              <div className="history-stats-pill">
                <span>Total Quizzes: <strong>{history.total_quizzes}</strong></span>
                <span>•</span>
                <span>Questions Answered: <strong>{history.total_questions_attempted}</strong></span>
                {history.average_accuracy !== null && (
                  <>
                    <span>•</span>
                    <span>Average Accuracy: <strong>{Math.round(history.average_accuracy * 100)}%</strong></span>
                  </>
                )}
              </div>
            )}
          </div>

          {!history || history.batches.length === 0 ? (
            <div className="empty-panel">
              <p className="empty-title">No completed quizzes yet</p>
              <p className="empty-desc">
                Your past assessment and practice quizzes will appear here with detailed question breakdowns.
              </p>
              <Button
                variant="primary"
                onClick={() => setActiveTab('quiz')}
                style={{ marginTop: '14px' }}
              >
                <Play size={14} aria-hidden="true" /> Take your first quiz
              </Button>
            </div>
          ) : (
            <div className="history-batches-list">
              {history.batches.map((batch: QuizHistoryItem) => {
                const isExpanded = expandedBatchId === batch.batch_id
                const submittedDate = new Date(batch.submitted_at).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })

                return (
                  <div key={batch.batch_id} className="history-batch-card">
                    <div
                      className="history-batch-summary"
                      onClick={() => setExpandedBatchId(isExpanded ? null : batch.batch_id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          setExpandedBatchId(isExpanded ? null : batch.batch_id)
                        }
                      }}
                    >
                      <div className="batch-info-col">
                        <span className="batch-date">{submittedDate}</span>
                        <div className="batch-skills-tags">
                          {batch.skill_titles.map((title) => (
                            <span key={title} className="batch-skill-tag">{title}</span>
                          ))}
                        </div>
                      </div>

                      <div className="batch-score-col">
                        <span className={`batch-pct ${batch.score_percent >= 70 ? 'pass' : 'sub'}`}>
                          {batch.score_percent}%
                        </span>
                        <span className="batch-raw-score">
                          {batch.correct_count} / {batch.question_count} correct
                        </span>
                        <span className="batch-evidence-pill">{batch.evidence_type_summary}</span>
                      </div>

                      <div className="batch-disclosure-arrow">
                        {isExpanded ? '▲ Hide' : '▼ Details'}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="history-items-drawer">
                        <h4 className="drawer-heading">Question Review</h4>
                        <div className="drawer-items-stack">
                          {batch.items.map((item, idx) => (
                            <div key={item.attempt_id} className={`drawer-item-box ${item.correct ? 'correct' : 'incorrect'}`}>
                              <div className="drawer-item-header">
                                <span className="drawer-q-num">Question #{idx + 1} ({item.skill_id})</span>
                                <span className={`drawer-q-result ${item.correct ? 'pass' : 'fail'}`}>
                                  {item.correct ? 'Correct' : 'Incorrect'} ({item.evidence_type})
                                </span>
                              </div>
                              <div className="drawer-item-body">
                                <div>
                                  Selected: <code>{item.selected_option}</code> | Correct: <code>{item.correct_option}</code>
                                </div>
                                <p className="drawer-explanation">
                                  <strong>Explanation:</strong> {item.explanation}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
