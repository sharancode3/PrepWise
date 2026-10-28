import { api } from '../../lib/api'
import { BUNDLED_RESOURCES, SAMPLE_TOPICS } from './fixtures'
import { mockCurriculumService } from './mockService'
import type {
  BatchUploadResult,
  CurriculumTopic,
  LearningProject,
  ReplanRequest,
  ResourceItem,
  SimulatedPlan,
  SimulatedPlanEntry,
  StudyScope,
} from './types'

const STORAGE_KEY_ACTIVE_PROJECT = 'learnnova.demo.active_project.v2'

interface ApiProject {
  id: string
  student_id: string
  curriculum_id: string
  title: string
  description?: string | null
  goal_id?: string | null
  created_at: string
  updated_at: string
}

interface ApiScope {
  project_id: string
  student_id: string
  selected_topics: string[]
  selected_resources: string[]
  free_text_request?: string | null
  confirmed_at: string
}

interface ApiResourcePreview {
  id: string
  title: string
  original_filename: string
  mime_type: string
  byte_size: number
  processing_status: string
  topic_id?: string | null
  project_id?: string | null
  preview_text: string
  chunk_count: number
  created_at: string
}

interface ApiPlanEntry {
  day_offset: number
  work_item_id: string
  skill_id: string
  reason_code: string
  activity_id: string
  duration_minutes: number
  is_target: boolean
  activity?: {
    template?: {
      title?: string
      steps?: string[]
      expected_outcome?: string
    }
  }
}

interface ApiPlanSnapshot {
  id: string
  goal_id: string
  parent_plan_id?: string | null
  revision: number
  entries: ApiPlanEntry[]
  created_at: string
}

export class CurriculumLiveService {
  private fallbackMock = mockCurriculumService

  async getTopics(curriculumId = 'python-foundations-v1'): Promise<CurriculumTopic[]> {
    try {
      const snap = await api<{
        id: string
        title: string
        version: string
        topics: {
          id: string
          title: string
          objective: string
          prerequisites: string[]
        }[]
      }>(`/curricula/${curriculumId}`)

      if (snap && snap.topics && snap.topics.length > 0) {
        return snap.topics.map((t) => ({
          id: t.id,
          title: t.title,
          objective: t.objective || '',
          difficulty: 1,
          learn_minutes: 20,
          practice_minutes: 25,
          prerequisites: t.prerequisites || [],
        }))
      }
    } catch {
      // Fall back to sample topics if backend offline
    }
    return SAMPLE_TOPICS
  }

  async listProjects(): Promise<LearningProject[]> {
    try {
      const projects = await api<ApiProject[]>('/curricula/projects')
      if (projects && projects.length > 0) {
        return projects.map((p) => ({
          id: p.id,
          title: p.title,
          description: p.description || '',
          curriculumId: p.curriculum_id,
          createdAt: p.created_at,
          updatedAt: p.updated_at,
          resourceIds: [],
          studyScope: null,
        }))
      }
    } catch {
      // fallback
    }
    return this.fallbackMock.listProjects()
  }

  async getActiveProjectId(): Promise<string> {
    const saved = localStorage.getItem(STORAGE_KEY_ACTIVE_PROJECT)
    if (saved) return saved
    const projs = await this.listProjects()
    return projs[0]?.id ?? 'proj-python-foundations'
  }

  async setActiveProject(projectId: string): Promise<LearningProject> {
    localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, projectId)
    return this.getProject(projectId)
  }

  async getProject(projectId: string): Promise<LearningProject> {
    try {
      const p = await api<ApiProject>(`/curricula/projects/${projectId}`)
      let scope: StudyScope | null = null
      try {
        const s = await api<ApiScope>(`/curricula/projects/${projectId}/scope`)
        if (s) {
          scope = {
            selectedTopicIds: s.selected_topics || [],
            selectedResourceIds: s.selected_resources || [],
            freeTextRequest: s.free_text_request || '',
            confirmedAt: s.confirmed_at,
          }
        }
      } catch {
        // scope may not be saved yet
      }

      return {
        id: p.id,
        title: p.title,
        description: p.description || '',
        curriculumId: p.curriculum_id,
        createdAt: p.created_at,
        updatedAt: p.updated_at,
        resourceIds: [],
        studyScope: scope,
      }
    } catch {
      return this.fallbackMock.getProject(projectId)
    }
  }

  async createProject(title: string, description = ''): Promise<LearningProject> {
    try {
      const p = await api<ApiProject>('/curricula/projects', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          curriculum_id: 'python-foundations-v1',
        }),
      })
      localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, p.id)
      return {
        id: p.id,
        title: p.title,
        description: p.description || '',
        curriculumId: p.curriculum_id,
        createdAt: p.created_at,
        updatedAt: p.updated_at,
        resourceIds: [],
        studyScope: null,
      }
    } catch {
      return this.fallbackMock.createProject(title, description)
    }
  }

  async listResources(projectId?: string): Promise<ResourceItem[]> {
    const items: ResourceItem[] = []

    // 1. Add bundled resources
    for (const b of BUNDLED_RESOURCES) {
      items.push({ ...b })
    }

    // 2. Fetch live uploaded resources from backend
    try {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
      const uploaded = await api<ApiResourcePreview[]>(`/curricula/resources${query}`)
      for (const u of uploaded) {
        items.push({
          id: u.id,
          projectId: u.project_id || projectId,
          title: u.title,
          filename: u.original_filename,
          kind: 'local',
          mimeType: u.mime_type,
          byteSize: u.byte_size,
          topicIds: u.topic_id ? [u.topic_id] : [],
          sourceLabel: 'Uploaded resource',
          snippet: u.preview_text ? u.preview_text.slice(0, 200) : 'Uploaded document indexed.',
          fullText: u.preview_text,
          addedAt: u.created_at,
          hasInMemoryFile: true,
          previewType: u.mime_type.includes('pdf') ? 'local-pdf' : 'local-text',
        })
      }
    } catch {
      // Backend error fallback
    }

    return items
  }

  async getResourceDetail(resourceId: string): Promise<ResourceItem> {
    try {
      const preview = await api<ApiResourcePreview>(`/curricula/resources/${resourceId}/preview`)
      return {
        id: preview.id,
        title: preview.title,
        filename: preview.original_filename,
        kind: 'local',
        mimeType: preview.mime_type,
        byteSize: preview.byte_size,
        topicIds: preview.topic_id ? [preview.topic_id] : [],
        sourceLabel: 'Uploaded resource',
        snippet: preview.preview_text.slice(0, 200),
        fullText: preview.preview_text,
        addedAt: preview.created_at,
        hasInMemoryFile: true,
        previewType: preview.mime_type.includes('pdf') ? 'local-pdf' : 'local-text',
      }
    } catch {
      return this.fallbackMock.getResourceDetail(resourceId)
    }
  }

  async addLocalFiles(
    projectId: string,
    files: File[],
    assignedTopicId: string
  ): Promise<BatchUploadResult> {
    const added: ResourceItem[] = []
    const skipped: { filename: string; reason: string }[] = []

    for (const file of files) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('project_id', projectId)
        formData.append('curriculum_id', 'python-foundations-v1')
        if (assignedTopicId) {
          formData.append('topic_id', assignedTopicId)
        }
        formData.append('title', file.name)

        const uploaded = await api<ApiResourcePreview>('/curricula/resources/upload', {
          method: 'POST',
          body: formData,
        })

        added.push({
          id: uploaded.id,
          projectId,
          title: uploaded.title,
          filename: uploaded.original_filename,
          kind: 'local',
          mimeType: uploaded.mime_type,
          byteSize: uploaded.byte_size,
          topicIds: uploaded.topic_id ? [uploaded.topic_id] : assignedTopicId ? [assignedTopicId] : [],
          sourceLabel: 'Uploaded resource',
          snippet: uploaded.preview_text ? uploaded.preview_text.slice(0, 200) : 'File uploaded and indexed.',
          fullText: uploaded.preview_text,
          addedAt: uploaded.created_at,
          hasInMemoryFile: true,
          previewType: uploaded.mime_type.includes('pdf') ? 'local-pdf' : 'local-text',
        })
      } catch (err) {
        skipped.push({
          filename: file.name,
          reason: err instanceof Error ? err.message : 'Upload failed',
        })
      }
    }

    return { added, skipped }
  }

  async removeResource(projectId: string, resourceId: string): Promise<void> {
    return this.fallbackMock.removeResource(projectId, resourceId)
  }

  async saveStudyScope(
    projectId: string,
    selectedTopicIds: string[],
    selectedResourceIds: string[],
    freeTextRequest = '',
    unresolvedResourceIds: string[] = []
  ): Promise<StudyScope> {
    try {
      const s = await api<ApiScope>(`/curricula/projects/${projectId}/scope`, {
        method: 'PUT',
        body: JSON.stringify({
          selected_topics: selectedTopicIds,
          selected_resources: selectedResourceIds,
          free_text_request: freeTextRequest,
        }),
      })
      return {
        selectedTopicIds: s.selected_topics || [],
        selectedResourceIds: s.selected_resources || [],
        freeTextRequest: s.free_text_request || '',
        confirmedAt: s.confirmed_at,
        unresolvedResourceIds,
      }
    } catch {
      return this.fallbackMock.saveStudyScope(
        projectId,
        selectedTopicIds,
        selectedResourceIds,
        freeTextRequest,
        unresolvedResourceIds
      )
    }
  }

  async getStudyScope(projectId: string): Promise<StudyScope | null> {
    try {
      const s = await api<ApiScope>(`/curricula/projects/${projectId}/scope`)
      if (s) {
        return {
          selectedTopicIds: s.selected_topics || [],
          selectedResourceIds: s.selected_resources || [],
          freeTextRequest: s.free_text_request || '',
          confirmedAt: s.confirmed_at,
        }
      }
    } catch {
      // not found
    }
    return this.fallbackMock.getStudyScope(projectId)
  }

  async getPlanVersions(projectId: string): Promise<SimulatedPlan[]> {
    const goalId = localStorage.getItem('learnnova.goal-id')
    if (goalId) {
      try {
        const livePlan = await api<ApiPlanSnapshot>(`/goals/${goalId}/plans/current`)
        if (livePlan && livePlan.entries && livePlan.entries.length > 0) {
          const simulated: SimulatedPlan = {
            planId: livePlan.id,
            projectId,
            version: livePlan.revision || 1,
            status: 'active',
            feasibility: 'full',
            createdAt: livePlan.created_at,
            totalMinutes: livePlan.entries.reduce((acc, e) => acc + (e.duration_minutes || 0), 0),
            entries: livePlan.entries.map((e, idx) => ({
              entryId: e.work_item_id,
              topicId: e.skill_id,
              topicTitle: e.skill_id,
              activityKind: (e.reason_code === 'GOAL_TARGET' ? 'learn' : 'practice') as 'learn' | 'practice',
              activityTitle: e.activity?.template?.title || `Session ${idx + 1} (${e.skill_id})`,
              durationMinutes: e.duration_minutes,
              resourceIds: [],
              scheduledDay: `Day ${e.day_offset + 1}`,
              sequence: idx + 1,
              completed: false,
              summary: e.activity?.template?.title || `Work on ${e.skill_id}`,
              steps: e.activity?.template?.steps || [],
              expectedOutcome: e.activity?.template?.expected_outcome || '',
            })),
          }
          return [simulated]
        }
      } catch {
        // fallback
      }
    }
    return this.fallbackMock.getPlanVersions(projectId)
  }

  async getPlan(projectId: string, version?: number): Promise<SimulatedPlan> {
    const versions = await this.getPlanVersions(projectId)
    if (versions.length > 0) {
      if (version != null) {
        const found = versions.find((v) => v.version === version)
        if (found) return found
      }
      return versions[versions.length - 1]
    }
    return this.fallbackMock.getPlan(projectId, version)
  }

  async toggleSessionCompletion(
    projectId: string,
    entryId: string,
    completed: boolean,
    version?: number
  ): Promise<SimulatedPlan> {
    return this.fallbackMock.toggleSessionCompletion(projectId, entryId, completed, version)
  }

  async replanWithRequest(
    projectId: string,
    request: ReplanRequest
  ): Promise<{ plan: SimulatedPlan; isSupportedScenario: boolean; explanation: string }> {
    return this.fallbackMock.replanWithRequest(projectId, request)
  }

  async simulateReplan(projectId: string): Promise<SimulatedPlan> {
    return this.fallbackMock.simulateReplan(projectId)
  }

  async resetDemoState(): Promise<void> {
    return this.fallbackMock.resetDemoState()
  }
}

export const liveCurriculumService = new CurriculumLiveService()
