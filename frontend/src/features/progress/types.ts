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
