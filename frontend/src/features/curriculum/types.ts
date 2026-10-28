export type ResourceKind = 'bundled' | 'local'

export type ProcessingStatus = 'ready' | 'processing' | 'extracted'

export interface CurriculumTopic {
  id: string
  title: string
  objective: string
  difficulty: number
  learn_minutes: number
  practice_minutes: number
  prerequisites: string[]
}

export interface ResourceSection {
  title: string
  pageNumber?: number
  content: string
}

export interface ResourceItem {
  id: string
  projectId?: string
  title: string
  filename: string
  kind: ResourceKind
  mimeType: string
  byteSize: number
  topicIds: string[]
  sourceLabel: string
  snippet: string
  fullText?: string
  sections?: ResourceSection[]
  addedAt: string
  hasInMemoryFile?: boolean
  previewType: 'bundled-text' | 'local-text' | 'local-pdf' | 'unavailable'
  previewNotice?: string
}

export interface StudyScope {
  selectedTopicIds: string[]
  selectedResourceIds: string[]
  freeTextRequest?: string
  confirmedAt: string
  unresolvedResourceIds?: string[]
}

export interface SimulatedPlanEntry {
  entryId: string
  topicId: string
  topicTitle: string
  activityKind: 'learn' | 'practice' | 'check'
  activityTitle: string
  durationMinutes: number
  resourceIds: string[]
  resourceName?: string
  scheduledDay: string
  sequence: number
  completed: boolean
  summary: string
  steps?: string[]
  expectedOutcome?: string
  isPending?: boolean
}

export interface ReplanChangeSummary {
  headline: string
  changes: string[]
  preservedItems: string[]
  durationDeltaMinutes: number
}

export interface ReplanRequest {
  reason: string
  focusTopicIds: string[]
  deadlineChanged: boolean
  newTargetDate?: string
  dailyStudyMinutes: number
  preservePreferences: string
}

export interface SimulatedPlan {
  planId: string
  projectId: string
  version: number
  status: 'active' | 'revising'
  entries: SimulatedPlanEntry[]
  totalMinutes: number
  feasibility: 'full' | 'partial'
  createdAt: string
  replanReason?: string
  changeSummary?: ReplanChangeSummary
}

export interface LearningProject {
  id: string
  title: string
  description: string
  curriculumId: string
  createdAt: string
  updatedAt: string
  resourceIds: string[]
  studyScope: StudyScope | null
}

export interface FileValidationResult {
  file: File
  valid: boolean
  error?: string
}

export interface BatchUploadResult {
  added: ResourceItem[]
  skipped: { filename: string; reason: string }[]
}

export interface ScopeReviewData {
  projectTitle: string
  selectedTopics: CurriculumTopic[]
  selectedResources: ResourceItem[]
  unresolvedResources: ResourceItem[]
  freeTextRequest: string
}
