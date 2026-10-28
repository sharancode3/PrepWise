import { api } from '../../lib/api'
import type {
  AttemptBatchReceipt,
  DashboardOverviewResponse,
  LearningStateResponse,
  QuizHistoryResponse,
  QuizQuestion,
  QuizRecommendationResponse,
} from './types'

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

export interface ProgressEventPayload {
  expected_revision: number
  plan_id: string
  work_item_id: string
  event_type: 'completed' | 'missed'
  actual_minutes?: number | null
}

export interface ProgressEventReceipt {
  event_id: string
  goal_id: string
  plan_id: string
  work_item_id: string
  event_type: 'completed' | 'missed'
  actual_minutes: number | null
  work_item_state: 'pending' | 'missed' | 'completed'
  new_revision: number
  occurred_at: string
}

export async function recordProgressEvent(
  goalId: string,
  payload: ProgressEventPayload,
  idempotencyKey: string
): Promise<ProgressEventReceipt> {
  return api<ProgressEventReceipt>(`/goals/${goalId}/progress-events`, {
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

export async function fetchRecommendation(goalId: string): Promise<QuizRecommendationResponse> {
  return api<QuizRecommendationResponse>(`/goals/${goalId}/recommendation`)
}

export async function fetchQuizHistory(goalId: string): Promise<QuizHistoryResponse> {
  return api<QuizHistoryResponse>(`/goals/${goalId}/quiz-history`)
}

export async function fetchDashboard(goalId: string): Promise<DashboardOverviewResponse> {
  return api<DashboardOverviewResponse>(`/goals/${goalId}/dashboard`)
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

