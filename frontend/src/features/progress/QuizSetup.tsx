import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, BookOpen, Layers, ShieldCheck, Sparkles } from 'lucide-react'
import { Button, Eyebrow, Notice, Panel } from '../../components/ui'
import { api } from '../../lib/api'
import { fetchGoal, fetchQuestions, fetchLearningState } from './progress-api'
import type { GoalDetails } from './progress-api'
import type { LearningStateResponse, QuizConfig, QuizDifficulty, QuizMode, QuizQuestion } from './types'

interface QuizSetupProps {
  goalId: string
  onStartQuiz: (config: QuizConfig, questions: QuizQuestion[]) => void
  initialSkillId?: string
  initialDifficulty?: QuizDifficulty
  initialMode?: QuizMode
}

export function QuizSetup({
  goalId,
  onStartQuiz,
  initialSkillId,
  initialDifficulty,
  initialMode,
}: QuizSetupProps) {
  const [goal, setGoal] = useState<GoalDetails | null>(null)
  const [learningState, setLearningState] = useState<LearningStateResponse | null>(null)
  const [curriculumTopics, setCurriculumTopics] = useState<Array<{ id: string; title: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')

  // Form State
  const [selectedTopic, setSelectedTopic] = useState<string>('')
  const [selectedSkill, setSelectedSkill] = useState<string>(initialSkillId || '')
  const [difficulty, setDifficulty] = useState<QuizDifficulty>(initialDifficulty || 'adaptive')
  const [mode, setMode] = useState<QuizMode>(initialMode || 'assessment')
  const [questionCount, setQuestionCount] = useState<number>(5)

  // Real question availability check
  const [checkingCount, setCheckingCount] = useState(false)
  const [availableCount, setAvailableCount] = useState<number | null>(null)
  const [exhaustedNotice, setExhaustedNotice] = useState<string>('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    Promise.all([
      fetchGoal(goalId),
      fetchLearningState(goalId),
    ])
      .then(([goalData, stateData]) => {
        if (!active) return
        setGoal(goalData)
        setLearningState(stateData)

        // Select first target topic by default if available
        if (goalData.targets && goalData.targets.length > 0) {
          setSelectedTopic(goalData.targets[0].topic_id)
        }

        if (goalData.curriculum_id) {
          api<{ topics: Array<{ id: string; title: string }> }>(`/curricula/${goalData.curriculum_id}`)
            .then((curric) => {
              if (active && curric?.topics) {
                setCurriculumTopics(curric.topics)
                if ((!goalData.targets || goalData.targets.length === 0) && curric.topics.length > 0) {
                  setSelectedTopic(curric.topics[0].id)
                }
              }
            })
            .catch(() => {})
        }
      })
      .catch((err) => {
        if (active) setError(err.message || 'Could not load goal context for quiz setup.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [goalId])

  // Helper to map UI difficulty to backend numeric difficulty query param
  function mapDifficultyParam(diff: QuizDifficulty): number | undefined {
    if (diff === 'easy') return 1
    if (diff === 'medium') return 3
    if (diff === 'hard') return 4
    if (diff === 'adaptive') {
      // Choose starting level based on existing evidence for the skill
      if (selectedSkill && learningState?.skills) {
        const skillEv = learningState.skills.find((s) => s.skill_id === selectedSkill)
        if (skillEv && skillEv.performance_estimate !== null) {
          if (skillEv.performance_estimate >= 0.8) return 4 // Start at hard if demonstrating strong evidence
          if (skillEv.performance_estimate <= 0.4) return 1 // Start at easy if needing attention
        }
      }
      return 3 // Default unknown or limited evidence starts at medium
    }
    return undefined
  }

  // Pre-fetch check for question availability
  useEffect(() => {
    let active = true
    if (!goalId) return

    setCheckingCount(true)
    setExhaustedNotice('')

    const diffParam = mapDifficultyParam(difficulty)
    const formParam = mode === 'practice' ? 'practice' : undefined

    fetchQuestions(goalId, {
      topic_id: selectedTopic || undefined,
      skill_id: selectedSkill || undefined,
      difficulty: diffParam,
      form: formParam,
      limit: 10,
    })
      .then((res) => {
        if (!active) return
        const count = res.questions.length
        setAvailableCount(count)
        if (count === 0) {
          if (res.question_pool_exhausted) {
            setExhaustedNotice('All independent reviewed items matching this filter have been completed.')
          } else {
            setExhaustedNotice('No reviewed questions currently exist for this topic/skill selection in the question bank.')
          }
        } else if (count < 5) {
          setExhaustedNotice(`Coverage note: ${count} reviewed item${count === 1 ? '' : 's'} available for this selection. We never duplicate questions.`)
        }
      })
      .catch(() => {
        if (active) setAvailableCount(null)
      })
      .finally(() => {
        if (active) setCheckingCount(false)
      })

    return () => {
      active = false
    }
  }, [goalId, selectedTopic, selectedSkill, difficulty, mode])

  async function handleStart(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const diffParam = mapDifficultyParam(difficulty)
      const formParam = mode === 'practice' ? 'practice' : undefined

      const res = await fetchQuestions(goalId, {
        topic_id: selectedTopic || undefined,
        skill_id: selectedSkill || undefined,
        difficulty: diffParam,
        form: formParam,
        limit: Math.min(questionCount, 10),
      })

      if (res.questions.length === 0) {
        throw new Error('No eligible unattempted questions found for this selection. Try adjusting the difficulty or mode.')
      }

      onStartQuiz(
        {
          topicId: selectedTopic,
          skillId: selectedSkill || undefined,
          difficulty,
          mode,
          count: res.questions.length,
        },
        res.questions
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start quiz. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (loading && !goal) {
    return <Notice>Loading quiz configuration…</Notice>
  }

  return (
    <div className="quiz-container">
      <div className="quiz-flow-header">
        <Eyebrow>Assessment & Practice / Quiz Setup</Eyebrow>
        <h1 className="page-title">Build your next quiz</h1>
        <p className="page-intro">
          Select target topics, challenge level, and mode. Questions come from the reviewed curriculum bank to verify demonstrated performance.
        </p>
      </div>

      {error && <Notice error>{error}</Notice>}

      <div className="quiz-setup-grid">
        <form onSubmit={handleStart} className="setup-form">
          <fieldset>
            <legend>
              <span>01</span> Focus area
            </legend>
            <div className="form-pair">
              <label>
                Topic
                <select
                  value={selectedTopic}
                  onChange={(e) => {
                    setSelectedTopic(e.target.value)
                    setSelectedSkill('')
                  }}
                  className="setup-select"
                >
                  <option value="">All target topics</option>
                  {goal?.targets && goal.targets.length > 0
                    ? goal.targets.map((t) => (
                        <option key={t.topic_id} value={t.topic_id}>
                          {t.topic_id.replace('-', ' ').toUpperCase()}
                        </option>
                      ))
                    : curriculumTopics.map((ct) => (
                        <option key={ct.id} value={ct.id}>
                          {ct.title || ct.id.toUpperCase()}
                        </option>
                      ))}
                </select>
              </label>

              <label>
                Specific micro-skill <span className="optional">(optional)</span>
                <select
                  value={selectedSkill}
                  onChange={(e) => setSelectedSkill(e.target.value)}
                  className="setup-select"
                >
                  <option value="">All topic skills</option>
                  {(learningState?.skills || [])
                    .filter((s) => !selectedTopic || !s.topic_id || s.topic_id === selectedTopic)
                    .map((s) => (
                      <option key={s.skill_id} value={s.skill_id}>
                        {s.skill_id.split('-').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} ({s.skill_id})
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <p className="field-help">
              Reviewed bank source: <strong>{goal?.curriculum_id || 'python-foundations-v1'}</strong>. Core questions test specific programming understanding.
            </p>
          </fieldset>

          <fieldset>
            <legend>
              <span>02</span> Challenge level
            </legend>
            <div className="quiz-radio-grid" role="radiogroup" aria-label="Difficulty selection">
              <label className="quiz-radio-card">
                <input
                  type="radio"
                  name="difficulty"
                  value="adaptive"
                  checked={difficulty === 'adaptive'}
                  onChange={() => setDifficulty('adaptive')}
                />
                <span className="quiz-radio-card-title">Adaptive</span>
                <span className="quiz-radio-card-desc">Starts using current evidence</span>
              </label>

              <label className="quiz-radio-card">
                <input
                  type="radio"
                  name="difficulty"
                  value="easy"
                  checked={difficulty === 'easy'}
                  onChange={() => setDifficulty('easy')}
                />
                <span className="quiz-radio-card-title">Easy</span>
                <span className="quiz-radio-card-desc">Difficulty 1–2</span>
              </label>

              <label className="quiz-radio-card">
                <input
                  type="radio"
                  name="difficulty"
                  value="medium"
                  checked={difficulty === 'medium'}
                  onChange={() => setDifficulty('medium')}
                />
                <span className="quiz-radio-card-title">Medium</span>
                <span className="quiz-radio-card-desc">Difficulty 3</span>
              </label>

              <label className="quiz-radio-card">
                <input
                  type="radio"
                  name="difficulty"
                  value="hard"
                  checked={difficulty === 'hard'}
                  onChange={() => setDifficulty('hard')}
                />
                <span className="quiz-radio-card-title">Hard</span>
                <span className="quiz-radio-card-desc">Difficulty 4–5</span>
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>
              <span>03</span> Mode & structure
            </legend>
            <div className="quiz-radio-grid" role="radiogroup" aria-label="Quiz mode">
              <label className="quiz-radio-card">
                <input
                  type="radio"
                  name="mode"
                  value="assessment"
                  checked={mode === 'assessment'}
                  onChange={() => setMode('assessment')}
                />
                <span className="quiz-radio-card-title">Assessment</span>
                <span className="quiz-radio-card-desc">Counts toward independent evidence</span>
              </label>

              <label className="quiz-radio-card">
                <input
                  type="radio"
                  name="mode"
                  value="practice"
                  checked={mode === 'practice'}
                  onChange={() => setMode('practice')}
                />
                <span className="quiz-radio-card-title">Practice</span>
                <span className="quiz-radio-card-desc">Explore with optional support</span>
              </label>
            </div>

            <label>
              Question count
              <input
                type="number"
                min={1}
                max={10}
                value={questionCount}
                onChange={(e) => setQuestionCount(Number(e.target.value))}
                aria-describedby="count-help"
              />
            </label>
            <p className="field-help" id="count-help">
              Default is 5 questions. Real available questions are bounded to prevent artificial repetition.
            </p>
          </fieldset>

          {exhaustedNotice && <Notice>{exhaustedNotice}</Notice>}

          <div className="form-actions">
            <Button
              type="submit"
              disabled={loading || checkingCount || (availableCount !== null && availableCount === 0)}
            >
              {loading ? 'Preparing questions…' : 'Start quiz'}
              <ArrowRight size={17} aria-hidden="true" />
            </Button>
            <span>
              {checkingCount
                ? 'Checking available questions…'
                : availableCount !== null
                ? `${availableCount} eligible item${availableCount === 1 ? '' : 's'} ready`
                : 'Server-graded assessment'}
            </span>
          </div>
        </form>

        <aside className="setup-aside">
          <Panel className="summary-panel">
            <span className="icon-tile">
              <ShieldCheck size={24} aria-hidden="true" />
            </span>
            <h2>Evidence-based checks.</h2>
            <p>
              Completing study sessions is participation. This quiz tests actual performance to adjust your plan with reliable evidence.
            </p>
            <dl>
              <div>
                <dt>Topic</dt>
                <dd>{selectedTopic || 'All targets'}</dd>
              </div>
              <div>
                <dt>Level</dt>
                <dd style={{ textTransform: 'capitalize' }}>{difficulty}</dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd style={{ textTransform: 'capitalize' }}>{mode}</dd>
              </div>
              <div>
                <dt>Question bank</dt>
                <dd>Reviewed python-foundations</dd>
              </div>
            </dl>
            <p className="summary-note">
              No answers or grading criteria are revealed before submission. Results update your learning state directly.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
