import React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Clock,
  Sparkles,
  BookOpen,
  Layers,
  CheckCircle2,
  FileText,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react'
import { Eyebrow, Notice, Button } from '../../components/ui'
import { useStudyPackage } from './useStudyPackage'
import { StudyOutline } from './StudyOutline'
import { StudyDiagram } from './StudyDiagram'
import { StudyPractice } from './StudyPractice'
import { StudySources } from './StudySources'
import './study.css'

export const StudyPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const topicParam = searchParams.get('topic') || searchParams.get('topic_id')

  const {
    pkg,
    loading,
    generatingMode,
    error,
    currentMode,
    revealedHintsCount,
    showSolution,
    activeSection,
    statusAnnouncement,
    fetchPackage,
    revealNextHint,
    toggleSolution,
    requestMode,
    scrollToSection,
  } = useStudyPackage('normal', topicParam)

  if (loading && !pkg) {
    return (
      <div className="container study-container">
        <Notice>Connecting to local PrepWise learning engine…</Notice>
      </div>
    )
  }

  if (error && !pkg) {
    return (
      <div className="container study-container">
        <Notice error>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <span>{error}</span>
            <Button variant="secondary" onClick={() => fetchPackage(currentMode, topicParam)}>
              <RotateCcw size={14} aria-hidden="true" /> Retry loading session
            </Button>
          </div>
        </Notice>
      </div>
    )
  }

  if (!pkg) {
    return (
      <div className="container study-container">
        <Notice>No study session selected. Open an activity from your study plan.</Notice>
        <div style={{ marginTop: '16px' }}>
          <Link to="/plan" className="button button--primary">
            Return to Plan
          </Link>
        </div>
      </div>
    )
  }

  const provenanceOrigin = pkg.provenance.origin
  const isFallback = provenanceOrigin === 'template'
  const isCached = provenanceOrigin === 'cache'

  const provenanceLabel = isFallback
    ? 'Source Fallback'
    : isCached
    ? 'Cached Session'
    : 'Locally Generated'

  const provenanceClass = isFallback
    ? 'study-pill--fallback'
    : isCached
    ? 'study-pill--cached'
    : 'study-pill--accent'

  return (
    <div className="container study-container">
      {/* Live region for non-urgent accessible status announcements */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {statusAnnouncement}
      </div>

      {/* Header */}
      <header className="study-header">
        <Link to="/plan" className="study-nav-back">
          <ArrowLeft size={15} aria-hidden="true" />
          <span>Back to My Plan</span>
        </Link>

        <div className="study-header-main">
          <div className="study-title-group">
            <Eyebrow>PrepWise Study Session · {pkg.topic_id}</Eyebrow>
            <h1>{pkg.title}</h1>
            <div className="study-meta-pills">
              <span className="study-pill">
                <Clock size={13} aria-hidden="true" />
                {pkg.duration_minutes} minutes
              </span>

              <span className="study-pill study-pill--accent">
                {pkg.support_mode === 'simpler'
                  ? 'Simpler Breakdown'
                  : pkg.support_mode === 'another_example'
                  ? 'Alternative Example'
                  : 'Standard Pacing'}
              </span>

              <span className={`study-pill ${provenanceClass}`}>
                {isFallback ? (
                  <AlertTriangle size={13} aria-hidden="true" />
                ) : (
                  <ShieldCheck size={13} aria-hidden="true" />
                )}
                {provenanceLabel}
              </span>

              {generatingMode && (
                <span className="study-pill" style={{ color: 'var(--dp-color-accent)' }}>
                  Updating explanation…
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Two-Column Learning Layout */}
      <div className="study-layout">
        {/* Left Column: Outline & Mode Controls */}
        <StudyOutline
          activeSection={activeSection}
          onSelectSection={scrollToSection}
          currentMode={currentMode}
          generatingMode={generatingMode}
          onRequestMode={requestMode}
          hasSources={pkg.sources && pkg.sources.length > 0}
        />

        {/* Right Column: Reading and Interactive Canvas */}
        <main className="study-content">
          {/* Section 1: Overview */}
          <section id="overview" className="study-card" aria-labelledby="heading-overview">
            <div className="study-section-header">
              <h2 id="heading-overview" className="study-section-title">
                <BookOpen size={20} aria-hidden="true" />
                <span>Session Overview</span>
              </h2>
            </div>

            <p style={{ fontSize: '16px', lineHeight: 1.6, color: 'var(--dp-color-ink)' }}>
              {pkg.objective}
            </p>

            <div className="study-overview-grid">
              <div className="study-overview-item">
                <span>Focus Objective</span>
                <p>{pkg.objective}</p>
              </div>

              <div className="study-overview-item">
                <span>Time Budget</span>
                <p>{pkg.duration_minutes} minutes scheduled</p>
              </div>

              <div className="study-overview-item">
                <span>Pedagogical Support</span>
                <p>
                  {pkg.evidence_status === 'unknown'
                    ? 'Foundational pacing'
                    : pkg.evidence_status === 'needs_attention'
                    ? 'Step-by-step scaffolding'
                    : pkg.evidence_status === 'strong'
                    ? 'Accelerated transfer'
                    : 'Standard guided practice'}
                </p>
              </div>
            </div>
          </section>

          {/* Section 2: Learn */}
          <section id="learn" className="study-card" aria-labelledby="heading-learn">
            <div className="study-section-header">
              <h2 id="heading-learn" className="study-section-title">
                <Sparkles size={20} aria-hidden="true" />
                <span>Grounded Concept Explanation</span>
              </h2>
              {generatingMode === 'simpler' && (
                <span style={{ fontSize: '12px', color: 'var(--dp-color-accent)' }}>Regenerating…</span>
              )}
            </div>

            <div className="study-explanation-text">
              {pkg.explanation}
            </div>
          </section>

          {/* Section 3: Worked Example */}
          <section id="worked-example" className="study-card" aria-labelledby="heading-example">
            <div className="study-section-header">
              <h2 id="heading-example" className="study-section-title">
                <Layers size={20} aria-hidden="true" />
                <span>Worked Demonstration</span>
              </h2>
            </div>

            <div className="study-example-problem">
              <strong>Problem:</strong>
              <div style={{ marginTop: '8px', whiteSpace: 'pre-line' }}>
                {pkg.worked_example.problem}
              </div>
            </div>

            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--dp-color-ink)', marginBottom: '10px' }}>
              Step-by-step Walkthrough:
            </div>

            <div className="study-steps-list">
              {pkg.worked_example.steps.map((step) => (
                <div key={step.step_number} className="study-step-card">
                  <div className="study-step-num">{step.step_number}</div>
                  <div className="study-step-body">
                    {step.description}
                    {step.code_or_detail && (
                      <pre
                        style={{
                          background: 'var(--dp-color-ground-muted)',
                          padding: '8px 12px',
                          borderRadius: '4px',
                          marginTop: '6px',
                          fontSize: '12.5px',
                          fontFamily: 'monospace',
                        }}
                      >
                        <code>{step.code_or_detail}</code>
                      </pre>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Custom SVG Visualization */}
            {pkg.diagram && <StudyDiagram diagram={pkg.diagram} />}
          </section>

          {/* Section 4: Practice */}
          <section id="practice" className="study-card" aria-labelledby="heading-practice">
            <div className="study-section-header">
              <h2 id="heading-practice" className="study-section-title">
                <CheckCircle2 size={20} aria-hidden="true" />
                <span>Guided Practice & Progressive Hints</span>
              </h2>
            </div>

            <StudyPractice
              practice={pkg.practice}
              hints={pkg.hints}
              solution={pkg.solution}
              revealedHintsCount={revealedHintsCount}
              showSolution={showSolution}
              onRevealHint={revealNextHint}
              onToggleSolution={toggleSolution}
              durationMinutes={pkg.duration_minutes}
              topicId={pkg.topic_id || topicParam || undefined}
            />
          </section>

          {/* Section 5: Sources */}
          {pkg.sources && pkg.sources.length > 0 && (
            <section id="sources" className="study-card" aria-labelledby="heading-sources">
              <div className="study-section-header">
                <h2 id="heading-sources" className="study-section-title">
                  <FileText size={20} aria-hidden="true" />
                  <span>Authorized Curriculum References</span>
                </h2>
              </div>

              <StudySources sources={pkg.sources} />
            </section>
          )}
        </main>
      </div>
    </div>
  )
}
