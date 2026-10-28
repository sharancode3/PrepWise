import { useEffect, useState } from 'react'
import { ArrowRight, BookOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import type { Profile } from '../../lib/api'
import { ActionLink, Notice } from '../../components/ui'
import { fetchLearningState } from './progress-api'
import { QuizPlayer } from './QuizPlayer'
import { QuizResult } from './QuizResult'
import { QuizSetup } from './QuizSetup'
import type { AttemptBatchReceipt, LearningStateResponse, QuizConfig, QuizDifficulty, QuizQuestion, QuizStep } from './types'
import './progress.css'

interface ProgressQuizFlowProps {
  initialGoalId?: string
  initialSkillId?: string
  initialDifficulty?: QuizDifficulty
  onReturnToDashboard?: () => void
}

export function ProgressQuizFlow({
  initialGoalId,
  initialSkillId,
  initialDifficulty,
  onReturnToDashboard,
}: ProgressQuizFlowProps) {
  const [goalId, setGoalId] = useState<string>(() => initialGoalId || localStorage.getItem('learnnova.goal-id') || '')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [learningState, setLearningState] = useState<LearningStateResponse | null>(null)

  const [step, setStep] = useState<QuizStep>('setup')
  const [activeConfig, setActiveConfig] = useState<QuizConfig | null>(null)
  const [activeQuestions, setActiveQuestions] = useState<QuizQuestion[]>([])
  const [lastReceipt, setLastReceipt] = useState<AttemptBatchReceipt | null>(null)

  // Load profile & goal ID
  useEffect(() => {
    let active = true

    // Check localStorage if not passed directly
    const storedGoalId = initialGoalId || localStorage.getItem('learnnova.goal-id')
    if (storedGoalId) setGoalId(storedGoalId)

    api<Profile>('/me')
      .then((p) => {
        if (active) setProfile(p)
      })
      .catch(() => {
        // Unauthenticated or not yet created
      })

    return () => {
      active = false
    }
  }, [initialGoalId])

  // Load learning state whenever goalId changes or after an attempt submission
  useEffect(() => {
    let active = true
    if (!goalId) return

    fetchLearningState(goalId)
      .then((res) => {
        if (active) setLearningState(res)
      })
      .catch(() => {
        // Ignored if goal is not yet initialized
      })

    return () => {
      active = false
    }
  }, [goalId, lastReceipt])

  if (!goalId) {
    return (
      <div className="quiz-container">
        <div className="quiz-flow-header">
          <h1 className="page-title">Evidence and assessment</h1>
          <p className="page-intro">
            A quiz requires an active goal so answers can be evaluated against your curriculum topics.
          </p>
        </div>
        <Notice>
          <strong>No active learning goal found</strong>
          <p>Create and save a goal to enable reviewed quizzes and skill evidence tracking.</p>
          <div style={{ marginTop: '12px' }}>
            <ActionLink to="/setup">
              Set up a goal <ArrowRight size={15} aria-hidden="true" />
            </ActionLink>
          </div>
        </Notice>
      </div>
    )
  }

  function handleStartQuiz(config: QuizConfig, questions: QuizQuestion[]) {
    setActiveConfig(config)
    setActiveQuestions(questions)
    setStep('playing')
  }

  function handleCompleteQuiz(receipt: AttemptBatchReceipt) {
    setLastReceipt(receipt)
    // Update local input_revision from server response receipt
    if (profile) {
      setProfile({
        ...profile,
        input_revision: receipt.new_revision,
      })
    }
    setStep('results')
  }

  function handleConfigureAnother() {
    setActiveConfig(null)
    setActiveQuestions([])
    setLastReceipt(null)
    setStep('setup')
  }

  return (
    <div className="quiz-flow-wrapper">
      {step === 'setup' && (
        <QuizSetup
          goalId={goalId}
          onStartQuiz={handleStartQuiz}
          initialSkillId={initialSkillId}
          initialDifficulty={initialDifficulty}
        />
      )}

      {step === 'playing' && activeConfig && (
        <QuizPlayer
          goalId={goalId}
          currentRevision={profile?.input_revision ?? 0}
          config={activeConfig}
          questions={activeQuestions}
          onComplete={handleCompleteQuiz}
          onCancel={() => setStep('setup')}
        />
      )}

      {step === 'results' && lastReceipt && activeConfig && (
        <QuizResult
          receipt={lastReceipt}
          questions={activeQuestions}
          config={activeConfig}
          learningState={learningState}
          onConfigureAnother={handleConfigureAnother}
        />
      )}
    </div>
  )
}
