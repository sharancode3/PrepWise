export interface QuizQuestion {
  question_id: string
  skill_id: string
  prompt: string
  options: Record<string, string>
  difficulty: number
  form: 'baseline' | 'followup' | 'practice'
  source_label?: string | null
}

export interface AttemptItemResult {
  question_id: string
  skill_id: string
  selected_option: string
  correct: boolean
  correct_option: string
  explanation: string
  hints_used: number
  evidence_type: 'independent' | 'supported'
  attempt_id: string
}

export interface AttemptBatchReceipt {
  batch_id: string
  goal_id: string
  accepted_revision: number
  new_revision: number
  correct_count: number
  question_count: number
  results: AttemptItemResult[]
}

export interface SkillEvidence {
  skill_id: string
  topic_id?: string
  independent_count: number
  supported_count: number
  performance_estimate: number | null
  evidence_status: 'unknown' | 'limited' | 'needs_attention' | 'ordinary' | 'strong'
  attempt_ids: string[]
}

export interface LearningStateResponse {
  goal_id: string
  skills: SkillEvidence[]
  items?: SkillEvidence[]
}

export type QuizDifficulty = 'easy' | 'medium' | 'hard' | 'adaptive'
export type QuizMode = 'practice' | 'assessment'

export interface QuizConfig {
  topicId: string
  skillId?: string
  difficulty: QuizDifficulty
  mode: QuizMode
  count: number
}

export type QuizStep = 'setup' | 'playing' | 'results'

export interface QuizRecommendationResponse {
  goal_id: string
  action: 'targeted_quiz' | 'fresh_check' | 'mixed_practice' | 'challenge_quiz'
  priority_skill_id?: string | null
  priority_skill_title?: string | null
  skill_ids: string[]
  effective_difficulty: number
  difficulty_label: string
  question_count: number
  reason_code: 'needs_attention' | 'limited_evidence' | 'no_evidence' | 'ordinary_practice' | 'strong_mastery'
  supporting_attempt_ids: string[]
  factual_explanation: string
  availability_status: 'available' | 'limited' | 'exhausted' | 'supported_only'
  available_count: number
  is_supported_practice_only: boolean
  questions: QuizQuestion[]
}

export interface QuizHistoryItem {
  batch_id: string
  submitted_at: string
  skill_ids: string[]
  skill_titles: string[]
  question_count: number
  correct_count: number
  score_percent: number
  evidence_type_summary: string
  items: AttemptItemResult[]
}

export interface QuizHistoryResponse {
  goal_id: string
  batches: QuizHistoryItem[]
  total_quizzes: number
  total_questions_attempted: number
  average_accuracy: number | null
}

export interface WorkItemSummary {
  work_item_id: string
  plan_id: string
  title: string
  kind: string
  study_date: string
  sequence: number
  duration_minutes: number
  state: 'pending' | 'completed' | 'missed'
  actual_minutes?: number | null
  skill_id?: string | null
}

export interface DashboardOverviewResponse {
  goal_id: string
  goal_title: string
  deadline: string
  has_active_plan: boolean
  active_plan_id?: string | null
  active_plan_version?: number | null
  current_revision: number
  completed_work_items_count: number
  total_work_items_count: number
  planned_minutes_completed: number
  total_planned_minutes: number
  actual_minutes_recorded: number
  skills_with_independent_evidence: number
  total_skills_count: number
  latest_quiz_score?: {
    batch_id: string
    submitted_at: string
    correct_count: number
    question_count: number
    score_percent: number
    skill_titles: string[]
  } | null
  scheduled_items: WorkItemSummary[]
  skill_evidence: SkillEvidence[]
  recommendation?: QuizRecommendationResponse | null
  disclaimer: string
}

