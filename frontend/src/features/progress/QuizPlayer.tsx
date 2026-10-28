import { useState } from 'react'
import { ArrowLeft, ArrowRight, CheckCircle2, HelpCircle, RefreshCw, Send } from 'lucide-react'
import { Button, Notice, Panel } from '../../components/ui'
import { submitAttemptBatch } from './progress-api'
import type { AttemptBatchReceipt, QuizConfig, QuizQuestion } from './types'

interface QuizPlayerProps {
  goalId: string
  currentRevision: number
  config: QuizConfig
  questions: QuizQuestion[]
  onComplete: (receipt: AttemptBatchReceipt, answers: Record<string, string>, hints: Record<string, number>) => void
  onCancel: () => void
}

export function QuizPlayer({
  goalId,
  currentRevision,
  config,
  questions,
  onComplete,
  onCancel,
}: QuizPlayerProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [hintsUsed, setHintsUsed] = useState<Record<string, number>>({})
  const [showHintNotice, setShowHintNotice] = useState<boolean>(false)

  // Confirmation & submission state
  const [confirmingSubmit, setConfirmingSubmit] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submissionError, setSubmissionError] = useState<string>('')
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => crypto.randomUUID())

  const total = questions.length
  const currentQuestion = questions[currentIndex]

  const answeredCount = Object.keys(answers).filter((qid) => answers[qid]).length
  const allAnswered = questions.every((q) => Boolean(answers[q.question_id]))

  function selectOption(optionKey: string) {
    if (submitting) return
    setAnswers((prev) => ({
      ...prev,
      [currentQuestion.question_id]: optionKey,
    }))
  }

  function handleUseHint() {
    if (config.mode !== 'practice') return
    const currentHints = hintsUsed[currentQuestion.question_id] || 0
    setHintsUsed((prev) => ({
      ...prev,
      [currentQuestion.question_id]: currentHints + 1,
    }))
    setShowHintNotice(true)
  }

  async function handleSubmit() {
    if (!allAnswered) {
      setSubmissionError('Please answer all questions before submitting.')
      return
    }

    setSubmitting(true)
    setSubmissionError('')

    try {
      const items = questions.map((q) => ({
        question_id: q.question_id,
        selected_option: answers[q.question_id],
        hints_used: hintsUsed[q.question_id] || 0,
      }))

      const receipt = await submitAttemptBatch(
        goalId,
        {
          expected_revision: currentRevision,
          items,
        },
        idempotencyKey
      )

      onComplete(receipt, answers, hintsUsed)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Submission failed. Please try again.'
      setSubmissionError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  // Format code prompts if markdown-style code or python trace is detected
  function renderPrompt(prompt: string) {
    const codeMatch = prompt.match(/`([^`]+)`/)
    if (codeMatch) {
      const parts = prompt.split(/`([^`]+)`/)
      return (
        <p className="quiz-prompt">
          {parts.map((part, i) =>
            i % 2 === 1 ? (
              <code key={i} className="quiz-inline-code">
                {part}
              </code>
            ) : (
              part
            )
          )}
        </p>
      )
    }
    return <p className="quiz-prompt">{prompt}</p>
  }

  return (
    <div className="quiz-player-layout">
      {/* Top Meta Bar */}
      <div className="quiz-meta-bar">
        <div>
          <span className="quiz-badge quiz-badge--accent" style={{ textTransform: 'capitalize' }}>
            {config.mode}
          </span>{' '}
          <span className="quiz-badge" style={{ textTransform: 'capitalize', marginLeft: '6px' }}>
            {config.difficulty}
          </span>
        </div>
        <div>
          Question {currentIndex + 1} of {total} · {answeredCount} of {total} answered
        </div>
      </div>

      {/* Slim Progress Bar */}
      <div className="quiz-progress-track" role="progressbar" aria-valuenow={currentIndex + 1} aria-valuemin={1} aria-valuemax={total}>
        <div
          className="quiz-progress-fill"
          style={{ width: `${((currentIndex + 1) / total) * 100}%` }}
        />
      </div>

      {submissionError && (
        <Notice error>
          <div>
            <strong>Submission issue</strong>
            <p>{submissionError}</p>
            <Button
              variant="secondary"
              onClick={handleSubmit}
              disabled={submitting}
              style={{ marginTop: '8px' }}
            >
              <RefreshCw size={15} aria-hidden="true" /> Retry submission
            </Button>
          </div>
        </Notice>
      )}

      {/* Main Question Card */}
      <Panel className="quiz-card">
        {renderPrompt(currentQuestion.prompt)}

        {/* Practice Mode Hint Section */}
        {config.mode === 'practice' && (
          <div style={{ marginBottom: '20px' }}>
            <Button
              type="button"
              variant="secondary"
              onClick={handleUseHint}
              style={{ fontSize: '13px', padding: '6px 12px', minHeight: '34px' }}
            >
              <HelpCircle size={15} aria-hidden="true" />
              {hintsUsed[currentQuestion.question_id]
                ? `Hints used on this question: ${hintsUsed[currentQuestion.question_id]}`
                : 'Need a hint?'}
            </Button>
            {showHintNotice && (
              <p className="field-help" style={{ marginTop: '8px' }}>
                Practice hint: Consider boundary limits and zero-based indexing. Note that using hints records this question as supported practice rather than independent evidence.
              </p>
            )}
          </div>
        )}

        {/* Answer Cards */}
        <div className="quiz-options" role="radiogroup" aria-label="Answer options">
          {Object.entries(currentQuestion.options).map(([optKey, optText]) => {
            const isSelected = answers[currentQuestion.question_id] === optKey
            return (
              <label key={optKey} className="quiz-option-card">
                <input
                  type="radio"
                  name={`q-${currentQuestion.question_id}`}
                  value={optKey}
                  checked={isSelected}
                  onChange={() => selectOption(optKey)}
                  disabled={submitting}
                />
                <div className="quiz-option-label">
                  <strong>{optKey.toUpperCase()}.</strong> {optText}
                </div>
              </label>
            )
          })}
        </div>
      </Panel>

      {/* Confirmation State Before Final Submit */}
      {confirmingSubmit && (
        <Panel style={{ padding: '20px', marginBottom: '24px', background: 'var(--dp-color-ground-muted)' }}>
          <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>Ready to submit your answers?</h3>
          <p style={{ fontSize: '14px', marginBottom: '16px' }}>
            You have answered all {total} questions. The server will grade your answers, record verified evidence, and update your learning state.
          </p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? 'Submitting & scoring…' : 'Confirm and view results'}
              <Send size={16} aria-hidden="true" />
            </Button>
            <Button variant="secondary" onClick={() => setConfirmingSubmit(false)} disabled={submitting}>
              Review answers
            </Button>
          </div>
        </Panel>
      )}

      {/* Navigation Controls */}
      <div className="quiz-nav-bar">
        <div>
          <Button
            variant="secondary"
            onClick={() => setCurrentIndex((idx) => Math.max(0, idx - 1))}
            disabled={currentIndex === 0 || submitting}
          >
            <ArrowLeft size={16} aria-hidden="true" /> Previous
          </Button>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Exit quiz
          </Button>

          {currentIndex < total - 1 ? (
            <Button
              onClick={() => setCurrentIndex((idx) => Math.min(total - 1, idx + 1))}
              disabled={submitting}
            >
              Next <ArrowRight size={16} aria-hidden="true" />
            </Button>
          ) : (
            <Button
              onClick={() => setConfirmingSubmit(true)}
              disabled={!allAnswered || submitting || confirmingSubmit}
            >
              {submitting ? 'Scoring on server…' : 'Finish & submit'}
              <CheckCircle2 size={16} aria-hidden="true" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
