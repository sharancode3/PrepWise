import React from 'react'
import { Lightbulb, Eye, EyeOff, CheckCircle2, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { PracticeTask, ProgressiveHint } from './types'

interface StudyPracticeProps {
  practice: PracticeTask
  hints: ProgressiveHint[]
  solution: string
  revealedHintsCount: number
  showSolution: boolean
  onRevealHint: () => void
  onToggleSolution: () => void
  durationMinutes: number
  topicId?: string
}

export const StudyPractice: React.FC<StudyPracticeProps> = ({
  practice,
  hints,
  solution,
  revealedHintsCount,
  showSolution,
  onRevealHint,
  onToggleSolution,
  durationMinutes,
  topicId,
}) => {
  const totalHints = hints.length
  const hasMoreHints = revealedHintsCount < totalHints

  return (
    <div className="study-practice">
      <div className="study-practice-prompt">{practice.prompt}</div>
      <div className="study-practice-instructions">{practice.instructions}</div>

      {practice.starter_code && (
        <pre
          style={{
            background: 'var(--dp-color-ground-muted)',
            border: '1px solid var(--dp-color-rule)',
            borderRadius: '6px',
            padding: '12px 16px',
            fontSize: '13px',
            fontFamily: 'monospace',
            overflowX: 'auto',
            marginBottom: '20px',
          }}
        >
          <code>{practice.starter_code}</code>
        </pre>
      )}

      {/* Progressive Hints Area */}
      <div className="study-hints-area">
        <div className="study-hints-controls">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lightbulb size={16} style={{ color: 'var(--dp-color-accent)' }} aria-hidden="true" />
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--dp-color-ink)' }}>
              Progressive Hints ({revealedHintsCount} of {totalHints} revealed)
            </span>
          </div>

          <button
            type="button"
            className="button button--secondary"
            style={{ minHeight: '36px', padding: '6px 14px', fontSize: '13px' }}
            onClick={onRevealHint}
            disabled={!hasMoreHints}
          >
            {hasMoreHints
              ? `Show hint (${totalHints - revealedHintsCount} left)`
              : 'All hints visible'}
          </button>
        </div>

        {revealedHintsCount > 0 && (
          <div className="study-hints-list" role="region" aria-label="Revealed hints">
            {hints.slice(0, revealedHintsCount).map((h) => {
              const tierLabel =
                h.tier === 'conceptual_cue'
                  ? 'Hint 1 · Conceptual Cue'
                  : h.tier === 'concrete_direction'
                  ? 'Hint 2 · Next Step'
                  : 'Hint 3 · Partial Step'

              return (
                <div key={`hint-${h.level}`} className="study-hint-card">
                  <span className="study-hint-badge">{tierLabel}</span>
                  <p className="study-hint-text">{h.hint_text}</p>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Suggested Solution Disclosure */}
      <div className="study-solution-disclosure">
        <button
          type="button"
          className="button button--secondary"
          style={{ minHeight: '36px', padding: '6px 14px', fontSize: '13px', width: '100%', justifyContent: 'space-between' }}
          onClick={onToggleSolution}
          aria-expanded={showSolution}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={15} style={{ color: 'var(--dp-color-accent)' }} aria-hidden="true" />
            {showSolution ? 'Hide Suggested Solution' : 'Reveal Suggested Solution'}
          </span>
          {showSolution ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
        </button>

        {showSolution && (
          <div className="study-solution-box" role="region" aria-label="Suggested Solution">
            {solution}
          </div>
        )}
      </div>

      {/* Completion Transition */}
      <div className="study-footer-actions">
        <span style={{ fontSize: '13px', color: 'var(--dp-color-ink-secondary)' }}>
          Finished this {durationMinutes}-minute study session?
        </span>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <Link
            to={topicId ? `/progress?tab=quiz&topic=${encodeURIComponent(topicId)}` : '/progress?tab=quiz'}
            className="button button--secondary"
            style={{ minHeight: '38px', fontSize: '13.5px' }}
          >
            Take Skill Quiz <ArrowRight size={15} aria-hidden="true" />
          </Link>
          <Link
            to="/progress"
            className="button button--primary"
            style={{ minHeight: '38px', fontSize: '13.5px' }}
          >
            Record Progress & Assessment <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>
      </div>
    </div>
  )
}
