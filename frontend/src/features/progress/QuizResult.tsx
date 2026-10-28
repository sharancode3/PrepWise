import { useState } from 'react'
import { Check, CheckCircle2, ChevronDown, ChevronRight, HelpCircle, RefreshCw, XCircle } from 'lucide-react'
import { Button, Eyebrow, Panel } from '../../components/ui'
import type { AttemptBatchReceipt, LearningStateResponse, QuizConfig, QuizQuestion } from './types'

interface QuizResultProps {
  receipt: AttemptBatchReceipt
  questions: QuizQuestion[]
  config: QuizConfig
  learningState?: LearningStateResponse | null
  onConfigureAnother: () => void
}

export function QuizResult({
  receipt,
  questions,
  config,
  learningState,
  onConfigureAnother,
}: QuizResultProps) {
  const [openDisclosures, setOpenDisclosures] = useState<Record<string, boolean>>({})

  const total = receipt.question_count
  const correct = receipt.correct_count
  const percent = Math.round((correct / total) * 100)

  // Map questions by id for joining
  const questionMap = new Map<string, QuizQuestion>()
  for (const q of questions) {
    questionMap.set(q.question_id, q)
  }

  // Count independent vs supported in this batch
  const independentAnswers = receipt.results.filter((r) => r.evidence_type === 'independent').length
  const supportedAnswers = receipt.results.filter((r) => r.evidence_type === 'supported').length

  // Build per-skill breakdown from learning state or batch results
  const skillBreakdown = new Map<string, { correct: number; total: number; independent: number }>()
  for (const r of receipt.results) {
    const existing = skillBreakdown.get(r.skill_id) || { correct: 0, total: 0, independent: 0 }
    skillBreakdown.set(r.skill_id, {
      correct: existing.correct + (r.correct ? 1 : 0),
      total: existing.total + 1,
      independent: existing.independent + (r.evidence_type === 'independent' ? 1 : 0),
    })
  }

  // Group skills into "Demonstrated" vs "Needs another check"
  const demonstratedSkills: { skillId: string; status: string; estimate: number | null }[] = []
  const needsCheckSkills: { skillId: string; status: string; estimate: number | null; reason: string }[] = []

  if (learningState?.skills) {
    for (const [skid] of skillBreakdown.entries()) {
      const stateEv = learningState.skills.find((s) => s.skill_id === skid)
      const status = stateEv ? stateEv.evidence_status : 'limited'
      const estimate = stateEv ? stateEv.performance_estimate : null

      if (status === 'strong' || status === 'ordinary') {
        demonstratedSkills.push({ skillId: skid, status, estimate })
      } else if (status === 'needs_attention') {
        needsCheckSkills.push({
          skillId: skid,
          status,
          estimate,
          reason: 'Rolling performance estimate is below 40% threshold.',
        })
      } else {
        // limited or unknown
        needsCheckSkills.push({
          skillId: skid,
          status,
          estimate,
          reason: 'More evidence needed to calibrate performance reliably.',
        })
      }
    }
  }

  function toggleDisclosure(qid: string) {
    setOpenDisclosures((prev) => ({
      ...prev,
      [qid]: !prev[qid],
    }))
  }

  return (
    <div className="quiz-results-layout">
      <Eyebrow>Assessment & Practice / Quiz Results</Eyebrow>

      {/* Main Score Banner */}
      <Panel className="quiz-score-banner">
        <h1 className="page-title" style={{ fontSize: '32px' }}>
          Quiz complete
        </h1>
        <div className="quiz-score-number">
          {correct} of {total} correct · {percent}%
        </div>

        <div className="quiz-score-meta">
          <span className="quiz-badge" style={{ textTransform: 'capitalize' }}>
            Level: {config.difficulty}
          </span>
          <span className="quiz-badge" style={{ textTransform: 'capitalize' }}>
            Mode: {config.mode}
          </span>
          <span className="quiz-badge quiz-badge--accent">
            {independentAnswers} independent · {supportedAnswers} supported
          </span>
        </div>
      </Panel>

      {/* Evidence Panels: What you demonstrated vs What needs another check */}
      <div className="quiz-evidence-grid">
        <Panel className="quiz-evidence-card">
          <h2>
            <CheckCircle2 size={20} color="#107c41" style={{ display: 'inline', marginRight: '8px' }} />
            What you demonstrated
          </h2>
          {demonstratedSkills.length > 0 ? (
            <div className="quiz-skill-list">
              {demonstratedSkills.map((s) => (
                <div key={s.skillId} className="quiz-skill-row">
                  <div>
                    <strong>{s.skillId}</strong>
                    <div style={{ fontSize: '12px', color: 'var(--dp-color-ink-secondary)' }}>
                      Recent estimate: {s.estimate !== null ? `${Math.round(s.estimate * 100)}%` : 'Calibrating'}
                    </div>
                  </div>
                  <span className={`quiz-badge ${s.status === 'strong' ? 'quiz-badge--success' : ''}`}>
                    {s.status.replace('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: '14px' }}>
              No established strong performance logged yet. Continue practicing with independent checks.
            </p>
          )}
        </Panel>

        <Panel className="quiz-evidence-card">
          <h2>
            <HelpCircle size={20} color="#b25900" style={{ display: 'inline', marginRight: '8px' }} />
            What needs another check
          </h2>
          {needsCheckSkills.length > 0 ? (
            <div className="quiz-skill-list">
              {needsCheckSkills.map((s) => (
                <div key={s.skillId} className="quiz-skill-row">
                  <div>
                    <strong>{s.skillId}</strong>
                    <div style={{ fontSize: '12px', color: 'var(--dp-color-ink-secondary)' }}>
                      {s.reason}
                    </div>
                  </div>
                  <span
                    className={`quiz-badge ${
                      s.status === 'needs_attention' ? 'quiz-badge--warning' : ''
                    }`}
                  >
                    {s.status === 'limited' ? 'More evidence needed' : s.status.replace('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: '14px' }}>
              No critical gaps detected on assessed skills. All checks met current policy thresholds.
            </p>
          )}
        </Panel>
      </div>

      {/* Expandable Question Review Section */}
      <div className="quiz-review-section">
        <h2>Review your answers</h2>
        <p style={{ fontSize: '14px', marginBottom: '20px' }}>
          Inspect server explanations and verified keys for every question in this quiz session.
        </p>

        {receipt.results.map((resItem, index) => {
          const publicQ = questionMap.get(resItem.question_id)
          const isOpen = Boolean(openDisclosures[resItem.question_id])

          const studentOptionText =
            publicQ?.options[resItem.selected_option] ?? resItem.selected_option
          const correctOptionText =
            publicQ?.options[resItem.correct_option] ?? resItem.correct_option

          return (
            <div key={resItem.question_id} className="question-disclosure">
              <summary
                onClick={() => toggleDisclosure(resItem.question_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    toggleDisclosure(resItem.question_id)
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {resItem.correct ? (
                    <Check size={18} color="#107c41" aria-hidden="true" />
                  ) : (
                    <XCircle size={18} color="#d9383a" aria-hidden="true" />
                  )}
                  <span>
                    Question {index + 1}: {publicQ?.prompt || resItem.question_id}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span
                    className={`quiz-badge ${
                      resItem.correct ? 'quiz-badge--success' : 'quiz-badge--warning'
                    }`}
                  >
                    {resItem.correct ? 'Correct' : 'Incorrect'}
                  </span>
                  {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                </div>
              </summary>

              {isOpen && (
                <div className="question-disclosure-body">
                  <dl>
                    <dt>Your answer</dt>
                    <dd>
                      {resItem.selected_option.toUpperCase()}: {studentOptionText}
                    </dd>

                    <dt>Correct answer</dt>
                    <dd>
                      {resItem.correct_option.toUpperCase()}: {correctOptionText}
                    </dd>

                    <dt>Explanation</dt>
                    <dd>{resItem.explanation}</dd>

                    <dt>Evidence type</dt>
                    <dd style={{ textTransform: 'capitalize' }}>
                      {resItem.evidence_type} (Hints: {resItem.hints_used})
                    </dd>

                    <dt>Resource source</dt>
                    <dd>Reviewed bank · Curriculum: python-foundations-v1</dd>
                  </dl>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Bottom Actions */}
      <div className="quiz-results-actions">
        <Button onClick={onConfigureAnother}>
          <RefreshCw size={16} aria-hidden="true" /> Configure another quiz
        </Button>
      </div>
    </div>
  )
}
