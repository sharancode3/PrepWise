import { api } from '../../lib/api'
import type { AttemptBatchReceipt, LearningStateResponse, QuizQuestion } from './types'

export interface QuestionsQueryOptions {
  skill_id?: string
  form?: 'baseline' | 'followup' | 'practice'
  difficulty?: number
  limit?: number
}

export interface QuestionsApiResponse {
  goal_id: string
  questions: QuizQuestion[]
  items?: QuizQuestion[]
  question_pool_exhausted: boolean
}

export async function fetchQuestions(
  goalId: string,
  options: QuestionsQueryOptions = {}
): Promise<QuestionsApiResponse> {
  const params = new URLSearchParams()
  if (options.skill_id) params.set('skill_id', options.skill_id)
  if (options.form) params.set('form', options.form)
  if (options.difficulty !== undefined) params.set('difficulty', String(options.difficulty))
  if (options.limit !== undefined) params.set('limit', String(options.limit))

  const qs = params.toString() ? `?${params.toString()}` : ''
  return api<QuestionsApiResponse>(`/goals/${goalId}/questions${qs}`)
}

export interface AttemptSubmissionItem {
  question_id: string
  selected_option: string
  hints_used: number
}

export interface AttemptBatchPayload {
  expected_revision: number
  items: AttemptSubmissionItem[]
}

export async function submitAttemptBatch(
  goalId: string,
  payload: AttemptBatchPayload,
  idempotencyKey: string
): Promise<AttemptBatchReceipt> {
  return api<AttemptBatchReceipt>(`/goals/${goalId}/attempt-batches`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(payload),
  })
}

export async function fetchLearningState(
  goalId: string,
  skillId?: string
): Promise<LearningStateResponse> {
  const qs = skillId ? `?skill_id=${encodeURIComponent(skillId)}` : ''
  return api<LearningStateResponse>(`/goals/${goalId}/learning-state${qs}`)
}

export interface GoalDetails {
  goal_id: string
  title: string
  goal_text?: string
  curriculum_id: string
  start_date: string
  deadline: string
  input_revision: number
  targets: { topic_id: string; self_report: string }[]
  availability: { date: string; minutes: number }[]
}

export async function fetchGoal(goalId: string): Promise<GoalDetails> {
  return api<GoalDetails>(`/goals/${goalId}`)
}
