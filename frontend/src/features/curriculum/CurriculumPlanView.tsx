import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  FileText,
  HelpCircle,
  Info,
  ListOrdered,
} from 'lucide-react'
import { Button } from '../../components/ui'
import { StudyTimeline } from './StudyTimeline'
import type {
  CurriculumTopic,
  LearningProject,
  ReplanRequest,
  ResourceItem,
  SimulatedPlan,
} from './types'

type PlanSubView = 'configure' | 'review' | 'timeline'

interface PlanViewProps {
  project: LearningProject
  topics: CurriculumTopic[]
  resources: ResourceItem[]
  plan: SimulatedPlan | null
  availableVersions?: number[]
  activeVersion?: number
  onSelectVersion?: (version: number) => void
  onSaveScope: (
    selectedTopics: string[],
    selectedResources: string[],
    freeText: string,
    unresolvedResources: string[]
  ) => Promise<void>
  onToggleSession: (entryId: string, completed: boolean) => Promise<void>
  onReplanWithRequest?: (request: ReplanRequest) => Promise<void>
  onSimulateReplan: () => Promise<void>
}

export function CurriculumPlanView({
  project,
  topics,
  resources,
  plan,
  availableVersions = [1],
  activeVersion = 1,
  onSelectVersion,
  onSaveScope,
  onToggleSession,
  onReplanWithRequest,
  onSimulateReplan,
}: PlanViewProps) {
  const initialScope = project.studyScope

  // Input states preserved across step navigation
  const [selectedTopics, setSelectedTopics] = useState<string[]>(
    initialScope?.selectedTopicIds ?? ['variables', 'conditions', 'loops']
  )
  const [selectedResources, setSelectedResources] = useState<string[]>(
    initialScope?.selectedResourceIds ?? resources.map((r) => r.id)
  )
  const [freeText, setFreeText] = useState<string>(
    initialScope?.freeTextRequest ?? ''
  )
  const [viewMode, setViewMode] = useState<PlanSubView>(
    plan && plan.entries.length > 0 ? 'timeline' : 'configure'
  )
  const [validationError, setValidationError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // Identify unmapped local resources selected by the user
  const unresolvedResourceIds = selectedResources.filter((resId) => {
    const res = resources.find((r) => r.id === resId)
    return res && res.kind === 'local' && (!res.topicIds || res.topicIds.length === 0)
  })

  function toggleTopic(id: string) {
    setValidationError(null)
    if (selectedTopics.includes(id)) {
      setSelectedTopics(selectedTopics.filter((t) => t !== id))
    } else {
      setSelectedTopics([...selectedTopics, id])
    }
  }

  function toggleResource(id: string) {
    setValidationError(null)
    if (selectedResources.includes(id)) {
      setSelectedResources(selectedResources.filter((r) => r !== id))
    } else {
      setSelectedResources([...selectedResources, id])
    }
  }

  function selectAllTopics() {
    setSelectedTopics(topics.map((t) => t.id))
    setValidationError(null)
  }

  function clearAllTopics() {
    setSelectedTopics([])
  }

  function selectAllResources() {
    setSelectedResources(resources.map((r) => r.id))
    setValidationError(null)
  }

  function clearAllResources() {
    setSelectedResources([])
  }

  async function handleProceedToReview(e?: FormEvent) {
    if (e) e.preventDefault()
    setValidationError(null)

    // Validation: Require at least some study scope
    if (selectedTopics.length === 0 && selectedResources.length === 0) {
      setValidationError(
        'Please select at least one curriculum topic or study resource to define your study scope.'
      )
      return
    }

    setIsSaving(true)
    try {
      await onSaveScope(selectedTopics, selectedResources, freeText, unresolvedResourceIds)
      setViewMode('review')
    } catch (err) {
      setValidationError(
        err instanceof Error ? err.message : 'Could not persist study scope selection.'
      )
    } finally {
      setIsSaving(false)
    }
  }

  // --- Sub-View 3: Vertical Study Timeline Preview ---
  if (viewMode === 'timeline') {
    return (
      <StudyTimeline
        plan={plan}
        projectTitle={project.title}
        topics={topics}
        availableVersions={availableVersions}
        activeVersion={activeVersion}
        onSelectVersion={onSelectVersion}
        onToggleSession={onToggleSession}
        onReplanWithRequest={onReplanWithRequest}
        onSimulateReplan={onSimulateReplan}
        onBackToScope={() => setViewMode('configure')}
      />
    )
  }

  // Calculated totals for summary
  const selectedTopicsList = topics.filter((t) => selectedTopics.includes(t.id))
  const selectedResourcesList = resources.filter((r) => selectedResources.includes(r.id))
  const totalTopicMinutes = selectedTopicsList.reduce(
    (acc, t) => acc + t.learn_minutes + t.practice_minutes,
    0
  )

  // --- Sub-View 2: Review Screen ---
  if (viewMode === 'review') {
    const unmappedList = resources.filter(
      (r) => unresolvedResourceIds.includes(r.id) || (selectedResources.includes(r.id) && r.kind === 'local')
    )

    return (
      <div className="curriculum-review-view">
        <div className="section-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <div>
              <span className="demo-badge">Step 2 of 2: Review study selection</span>
              <h2 style={{ margin: '8px 0 4px 0' }}>Confirm study scope</h2>
            </div>
            <Button variant="secondary" onClick={() => setViewMode('configure')}>
              <ArrowLeft size={15} aria-hidden="true" />
              Back to selection
            </Button>
          </div>

          <p className="section-desc">
            Verify your selected topics, resources, and study request for <strong>{project.title}</strong> before viewing the planned timeline.
          </p>

          {/* Project Details */}
          <div className="review-section">
            <h3 className="review-heading">Learning project</h3>
            <div className="review-project-box">
              <strong style={{ fontSize: 16, color: 'var(--dp-color-ink)' }}>{project.title}</strong>
              <div style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)', marginTop: 4 }}>
                Curriculum ID: <code>{project.curriculumId}</code>
              </div>
            </div>
          </div>

          {/* Selected Topics List */}
          <div className="review-section">
            <h3 className="review-heading">
              Selected curriculum topics ({selectedTopicsList.length}) · {totalTopicMinutes} estimated min
            </h3>
            {selectedTopicsList.length === 0 ? (
              <div className="review-empty-text">No curriculum topics selected.</div>
            ) : (
              <div className="review-grid">
                {selectedTopicsList.map((topic) => (
                  <div key={topic.id} className="review-item-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: 14 }}>{topic.title}</strong>
                      <span className="review-duration-tag">
                        {topic.learn_minutes + topic.practice_minutes} min
                      </span>
                    </div>
                    <p style={{ margin: '6px 0 0 0', fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                      {topic.objective}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Selected Resources List */}
          <div className="review-section">
            <h3 className="review-heading">
              Selected resources ({selectedResourcesList.length})
            </h3>
            {selectedResourcesList.length === 0 ? (
              <div className="review-empty-text">No study resources selected.</div>
            ) : (
              <div className="review-list">
                {selectedResourcesList.map((res) => (
                  <div key={res.id} className="review-resource-card">
                    <FileText size={18} color="var(--dp-color-accent)" aria-hidden="true" />
                    <span style={{ fontWeight: 500, fontSize: 14 }}>{res.title}</span>
                    <span className={`source-badge ${res.kind === 'bundled' ? 'badge-sample' : 'badge-local'}`}>
                      {res.kind === 'bundled' ? 'Sample resource' : 'Local file'}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)', marginLeft: 'auto' }}>
                      {(res.byteSize / 1024).toFixed(1)} KB
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Original Free-text Request */}
          <div className="review-section">
            <h3 className="review-heading">Original study inquiry</h3>
            <div className="review-request-box">
              {freeText.trim() ? (
                <>
                  <div style={{ fontStyle: 'italic', fontSize: 14, color: 'var(--dp-color-ink)', marginBottom: 6 }}>
                    “{freeText.trim()}”
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                    Original free-text inquiry preserved verbatim. Not artificially altered or parsed by mock AI.
                  </div>
                </>
              ) : (
                <span style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
                  None entered (standard curriculum progression requested).
                </span>
              )}
            </div>
          </div>

          {/* Unresolved Resource Mappings Notice */}
          {unmappedList.length > 0 && (
            <div className="review-unresolved-box" role="status">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <HelpCircle size={16} color="#9a5b00" aria-hidden="true" />
                <strong style={{ fontSize: 14, color: '#7a3e00' }}>
                  Unresolved resource-level selection ({unmappedList.length})
                </strong>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#7a3e00', lineHeight: 1.5 }}>
                The following local files are selected at the resource level: {unmappedList.map((u) => u.title).join(', ')}.
                Topic mappings remain unresolved for these files and are preserved in the payload for Person 3's planning service to index during full backend integration.
              </p>
            </div>
          )}

          {/* Sample Plan Integration Preview Banner */}
          <div className="review-preview-notice">
            <Info size={18} className="review-info-icon" aria-hidden="true" />
            <div>
              <strong style={{ display: 'block', fontSize: 14, color: 'var(--dp-color-ink)' }}>
                Planning integration preview notice
              </strong>
              <p style={{ margin: '4px 0 0 0', fontSize: 13, color: 'var(--dp-color-ink-secondary)', lineHeight: 1.5 }}>
                The next screen previews how Person 3 will render the scheduled study timeline. Sample plan content reflects the supported Python Fundamentals curriculum topics. We do not claim an arbitrary custom plan was generated from local PDF uploads.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 24, flexWrap: 'wrap', gap: 12 }}>
            <Button variant="secondary" onClick={() => setViewMode('configure')}>
              <ArrowLeft size={15} aria-hidden="true" />
              Back to selection
            </Button>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Link
                to={`/setup?topics=${encodeURIComponent(selectedTopics.join(','))}`}
                className="btn btn-secondary"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                Configure study goal in Setup →
              </Link>
              <Button onClick={() => setViewMode('timeline')}>
                View study checklist
                <ArrowRight size={15} aria-hidden="true" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // --- Sub-View 1: Configure Study Scope Screen ---
  return (
    <div className="curriculum-plan-view">
      <div className="section-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
          <div>
            <span className="demo-badge">Step 1 of 2: Define scope</span>
            <h2 style={{ margin: '6px 0 0 0' }}>Choose what to study</h2>
          </div>
          <Button variant="secondary" onClick={() => setViewMode('timeline')}>
            <Calendar size={15} aria-hidden="true" />
            View study checklist
          </Button>
        </div>

        <p className="section-desc">
          Select the curriculum topics and source resources you want to master in <strong>{project.title}</strong>. You may also include an optional focus inquiry.
        </p>

        {validationError && (
          <div className="scope-validation-alert" role="alert">
            <AlertCircle size={16} aria-hidden="true" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleProceedToReview}>
          {/* 1. Topics Selection */}
          <div className="scope-group">
            <div className="scope-group-header">
              <div>
                <span className="scope-group-title">
                  <BookOpen size={16} aria-hidden="true" />
                  Curriculum topics
                </span>
                <span className="scope-group-subtitle">
                  Select key topics to include in your scheduled sessions.
                </span>
              </div>
              <div className="scope-quick-links">
                <button type="button" className="text-action-link" onClick={selectAllTopics}>
                  Select all
                </button>
                <span>·</span>
                <button type="button" className="text-action-link" onClick={clearAllTopics}>
                  Clear
                </button>
              </div>
            </div>

            <div className="scope-topics-grid">
              {topics.map((topic) => {
                const isChecked = selectedTopics.includes(topic.id)
                return (
                  <label
                    key={topic.id}
                    className={`scope-topic-card ${isChecked ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleTopic(topic.id)}
                      className="scope-checkbox"
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                        <span className="scope-item-title">{topic.title}</span>
                        <span className="scope-item-duration">
                          {topic.learn_minutes + topic.practice_minutes} min
                        </span>
                      </div>
                      <div className="scope-item-objective">{topic.objective}</div>
                      {topic.prerequisites.length > 0 && (
                        <div className="scope-item-prereq">
                          Prereq: {topic.prerequisites.join(', ')}
                        </div>
                      )}
                    </div>
                  </label>
                )
              })}
            </div>
          </div>

          {/* 2. Whole Resources Selection */}
          <div className="scope-group" style={{ marginTop: 24 }}>
            <div className="scope-group-header">
              <div>
                <span className="scope-group-title">
                  <FileText size={16} aria-hidden="true" />
                  Source resources
                </span>
                <span className="scope-group-subtitle">
                  Select whole reference documents or local notes for grounding.
                </span>
              </div>
              <div className="scope-quick-links">
                <button type="button" className="text-action-link" onClick={selectAllResources}>
                  Select all
                </button>
                <span>·</span>
                <button type="button" className="text-action-link" onClick={clearAllResources}>
                  Clear
                </button>
              </div>
            </div>

            {resources.length === 0 ? (
              <div className="scope-empty-notice">
                No resources available. Add notes or course texts in the <strong>Resources</strong> tab.
              </div>
            ) : (
              <div className="scope-resources-list">
                {resources.map((res) => {
                  const isChecked = selectedResources.includes(res.id)
                  const isLocal = res.kind === 'local'

                  return (
                    <label
                      key={res.id}
                      className={`scope-resource-card ${isChecked ? 'selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleResource(res.id)}
                        className="scope-checkbox"
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span className="scope-item-title">{res.title}</span>
                          <span className={`source-badge ${res.kind === 'bundled' ? 'badge-sample' : 'badge-local'}`}>
                            {res.kind === 'bundled' ? 'Sample resource' : 'Local file'}
                          </span>
                          <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                            {(res.byteSize / 1024).toFixed(1)} KB
                          </span>
                        </div>
                        {isLocal && (
                          <div style={{ fontSize: 12, color: '#9a5b00', marginTop: 3 }}>
                            Resource-level selection. Topic mapping remains unresolved until full planner integration.
                          </div>
                        )}
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {/* 3. Optional Free-Text Inquiry */}
          <div className="scope-group" style={{ marginTop: 24 }}>
            <label htmlFor="scope-free-text" className="scope-group-title" style={{ display: 'block', marginBottom: 4 }}>
              Optional study inquiry
            </label>
            <p className="scope-group-subtitle" style={{ marginBottom: 8 }}>
              Enter any focus instructions. (e.g. “Complete Control Flow Notes and focus on loops.”)
            </p>
            <input
              id="scope-free-text"
              type="text"
              maxLength={250}
              placeholder="e.g. Complete Control Flow Notes and focus on loops."
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              className="scope-text-input"
            />
            <div style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)', marginTop: 4 }}>
              Free text is captured verbatim for Person 3's planner. It does not artificially alter selected topics.
            </div>
          </div>

          {/* 4. Selection Summary Bar */}
          <div className="scope-summary-card">
            <div className="scope-summary-left">
              <div className="scope-summary-metrics">
                <span>
                  <strong>{selectedTopics.length}</strong> topic{selectedTopics.length === 1 ? '' : 's'} ({totalTopicMinutes} min)
                </span>
                <span className="timeline-stat-divider">·</span>
                <span>
                  <strong>{selectedResources.length}</strong> resource{selectedResources.length === 1 ? '' : 's'}
                </span>
                {unresolvedResourceIds.length > 0 && (
                  <>
                    <span className="timeline-stat-divider">·</span>
                    <span style={{ color: '#9a5b00' }}>
                      {unresolvedResourceIds.length} unresolved mapping{unresolvedResourceIds.length === 1 ? '' : 's'}
                    </span>
                  </>
                )}
              </div>
            </div>

            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Saving selection…' : 'Review selection'}
              <ArrowRight size={15} aria-hidden="true" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
