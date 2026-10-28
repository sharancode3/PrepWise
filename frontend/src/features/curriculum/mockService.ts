import {
  BUNDLED_RESOURCES,
  INITIAL_PLAN_V1,
  SAMPLE_PLAN_V2,
  SAMPLE_PROJECT,
  SAMPLE_TOPICS,
} from './fixtures'
import type {
  BatchUploadResult,
  CurriculumTopic,
  LearningProject,
  ReplanRequest,
  ResourceItem,
  SimulatedPlan,
  StudyScope,
} from './types'

const STORAGE_KEY_PROJECTS = 'learnnova.demo.projects.v2'
const STORAGE_KEY_ACTIVE_PROJECT = 'learnnova.demo.active_project.v2'
const STORAGE_KEY_PLANS = 'learnnova.demo.plans.v2'
const STORAGE_KEY_LOCAL_META = 'learnnova.demo.local_resources.v2'

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB
const SUPPORTED_EXTENSIONS = ['.pdf', '.txt', '.md', '.markdown']

function delay(ms = 120): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// In-memory file registry (keeps File objects in memory; never serializes raw files into localStorage)
const inMemoryFiles = new Map<string, File>()

class CurriculumMockService {
  private projects: LearningProject[] = []
  private resources: ResourceItem[] = []
  private plans: Record<string, SimulatedPlan[]> = {}
  private activeProjectId: string = SAMPLE_PROJECT.id

  constructor() {
    this.loadState()
  }

  private loadState(): void {
    // 1. Initialize bundled sample resources
    this.resources = BUNDLED_RESOURCES.map((r) => ({ ...r }))

    // 2. Load projects
    try {
      const storedProjects = localStorage.getItem(STORAGE_KEY_PROJECTS)
      if (storedProjects) {
        this.projects = JSON.parse(storedProjects)
      } else {
        this.projects = [{ ...SAMPLE_PROJECT }]
        this.persistProjects()
      }
    } catch {
      this.projects = [{ ...SAMPLE_PROJECT }]
    }

    // 3. Load active project pointer
    const active = localStorage.getItem(STORAGE_KEY_ACTIVE_PROJECT)
    if (active && this.projects.some((p) => p.id === active)) {
      this.activeProjectId = active
    } else {
      this.activeProjectId = this.projects[0]?.id ?? SAMPLE_PROJECT.id
    }

    // 4. Restore small local resource metadata if stored, but flag that File in-memory is lost if refreshed
    try {
      const storedLocalMeta = localStorage.getItem(STORAGE_KEY_LOCAL_META)
      if (storedLocalMeta) {
        const localMetaList: ResourceItem[] = JSON.parse(storedLocalMeta)
        for (const meta of localMetaList) {
          if (!this.resources.some((r) => r.id === meta.id)) {
            this.resources.push({
              ...meta,
              hasInMemoryFile: false,
              previewType: 'unavailable',
              previewNotice:
                'Local file content is no longer in memory. Because this is a browser prototype that does not upload files to a server, please select the file again from your device to preview.',
            })
          }
        }
      }
    } catch {
      // quota or JSON error fallback
    }

    // 5. Load plans (normalized to version arrays per project)
    try {
      const storedPlans = localStorage.getItem(STORAGE_KEY_PLANS)
      if (storedPlans) {
        const parsed = JSON.parse(storedPlans)
        this.plans = {}
        for (const [projId, val] of Object.entries(parsed)) {
          this.plans[projId] = Array.isArray(val) ? val : [val as SimulatedPlan]
        }
      } else {
        this.plans = { [SAMPLE_PROJECT.id]: [{ ...INITIAL_PLAN_V1 }] }
        this.persistPlans()
      }
    } catch {
      this.plans = { [SAMPLE_PROJECT.id]: [{ ...INITIAL_PLAN_V1 }] }
    }
  }

  private persistProjects(): void {
    try {
      localStorage.setItem(STORAGE_KEY_PROJECTS, JSON.stringify(this.projects))
    } catch {
      // ignore quota in private browsing
    }
  }

  private persistPlans(): void {
    try {
      localStorage.setItem(STORAGE_KEY_PLANS, JSON.stringify(this.plans))
    } catch {
      // ignore quota
    }
  }

  private persistLocalMeta(): void {
    try {
      const localOnly = this.resources
        .filter((r) => r.kind === 'local')
        .map(({ fullText, ...rest }) => rest) // strip fullText from localStorage to stay lightweight
      localStorage.setItem(STORAGE_KEY_LOCAL_META, JSON.stringify(localOnly))
    } catch {
      // ignore quota
    }
  }

  // --- Curriculum Topics ---
  async getTopics(): Promise<CurriculumTopic[]> {
    await delay(60)
    return [...SAMPLE_TOPICS]
  }

  // --- Learning Projects ---
  async listProjects(): Promise<LearningProject[]> {
    await delay(80)
    return this.projects.map((p) => ({ ...p }))
  }

  async getActiveProjectId(): Promise<string> {
    await delay(20)
    return this.activeProjectId
  }

  async setActiveProject(projectId: string): Promise<LearningProject> {
    await delay(60)
    const project = this.projects.find((p) => p.id === projectId)
    if (!project) throw new Error('Project not found')
    this.activeProjectId = projectId
    localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, projectId)
    return { ...project }
  }

  async getProject(projectId: string): Promise<LearningProject> {
    await delay(70)
    const project = this.projects.find((p) => p.id === projectId)
    if (!project) throw new Error('Project not found')
    return { ...project }
  }

  async createProject(title: string, description = ''): Promise<LearningProject> {
    await delay(150)
    const trimmedTitle = title.trim()
    if (!trimmedTitle) {
      throw new Error('Project name is required')
    }
    const newProject: LearningProject = {
      id: `proj-${Date.now().toString(36)}`,
      title: trimmedTitle,
      description: description.trim(),
      curriculumId: 'python-foundations-v1',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      resourceIds: ['res-python-basics'], // attach initial sample resource
      studyScope: {
        selectedTopicIds: ['variables'],
        selectedResourceIds: ['res-python-basics'],
        freeTextRequest: '',
        confirmedAt: new Date().toISOString(),
      },
    }

    this.projects.unshift(newProject)
    this.activeProjectId = newProject.id
    this.persistProjects()
    localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, newProject.id)
    return { ...newProject }
  }

  async deleteProject(projectId: string): Promise<void> {
    await delay(120)
    this.projects = this.projects.filter((p) => p.id !== projectId)
    delete this.plans[projectId]
    if (this.activeProjectId === projectId) {
      this.activeProjectId = this.projects[0]?.id ?? ''
      localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, this.activeProjectId)
    }
    this.persistProjects()
    this.persistPlans()
  }

  // --- Resource List & Details ---
  async listResources(projectId: string): Promise<ResourceItem[]> {
    await delay(80)
    const project = this.projects.find((p) => p.id === projectId)
    if (!project) return []

    // Return bundled resources + resources tied to this project
    return this.resources
      .filter((r) => r.kind === 'bundled' || (r.projectId === projectId && project.resourceIds.includes(r.id)))
      .map((r) => ({
        ...r,
        hasInMemoryFile: inMemoryFiles.has(r.id),
      }))
  }

  async getResourceDetail(resourceId: string): Promise<ResourceItem> {
    await delay(70)
    const resource = this.resources.find((r) => r.id === resourceId)
    if (!resource) throw new Error('Resource not found')

    const file = inMemoryFiles.get(resourceId)

    // For local text/markdown files in memory: read fresh text if available
    if (file && (resource.previewType === 'local-text' || file.name.endsWith('.md') || file.name.endsWith('.txt'))) {
      try {
        const textSlice = await file.slice(0, 50000).text()
        return {
          ...resource,
          fullText: textSlice,
          hasInMemoryFile: true,
          previewType: 'local-text',
        }
      } catch {
        // fallback
      }
    }

    return {
      ...resource,
      hasInMemoryFile: Boolean(file),
    }
  }

  getInMemoryFile(resourceId: string): File | undefined {
    return inMemoryFiles.get(resourceId)
  }

  // --- Multi-file Local Addition with Strict Validation & Honesty ---
  async addLocalFiles(
    projectId: string,
    files: File[],
    assignedTopicId: string
  ): Promise<BatchUploadResult> {
    await delay(200)
    const project = this.projects.find((p) => p.id === projectId)
    if (!project) throw new Error('Project not found')

    const added: ResourceItem[] = []
    const skipped: { filename: string; reason: string }[] = []

    const currentProjectResources = await this.listResources(projectId)

    for (const file of files) {
      const lowerName = file.name.toLowerCase()
      const extension = '.' + lowerName.split('.').pop()

      // 1. Check supported formats
      if (!SUPPORTED_EXTENSIONS.includes(extension)) {
        skipped.push({
          filename: file.name,
          reason: `Unsupported format (${extension}). Supported: PDF, TXT, Markdown.`,
        })
        continue
      }

      // 2. Check empty file
      if (file.size === 0) {
        skipped.push({
          filename: file.name,
          reason: 'File is empty (0 bytes).',
        })
        continue
      }

      // 3. Check file size limit
      if (file.size > MAX_FILE_SIZE) {
        skipped.push({
          filename: file.name,
          reason: `File exceeds 10 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`,
        })
        continue
      }

      // 4. Check duplicate in current project
      const duplicate = currentProjectResources.some(
        (r) => r.filename.toLowerCase() === file.name.toLowerCase()
      )
      if (duplicate) {
        skipped.push({
          filename: file.name,
          reason: 'A file with this name is already in the project.',
        })
        continue
      }

      // 5. Valid file: process locally
      const resourceId = `local-res-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
      inMemoryFiles.set(resourceId, file)

      let previewType: ResourceItem['previewType'] = 'unavailable'
      let initialText: string | undefined = undefined

      if (extension === '.pdf') {
        previewType = 'local-pdf'
      } else if (['.txt', '.md', '.markdown'].includes(extension)) {
        previewType = 'local-text'
        try {
          initialText = await file.slice(0, 50000).text()
        } catch {
          initialText = 'Unable to read local text file.'
        }
      }

      const newResource: ResourceItem = {
        id: resourceId,
        projectId,
        title: file.name,
        filename: file.name,
        kind: 'local',
        mimeType: file.type || 'text/plain',
        byteSize: file.size,
        topicIds: [assignedTopicId],
        sourceLabel: 'Local file',
        snippet: `Selected locally from your device (${(file.size / 1024).toFixed(1)} KB). In-memory prototype only.`,
        fullText: initialText,
        addedAt: new Date().toISOString(),
        hasInMemoryFile: true,
        previewType,
      }

      this.resources.push(newResource)
      project.resourceIds.push(resourceId)
      project.updatedAt = new Date().toISOString()
      added.push(newResource)
    }

    if (added.length > 0) {
      this.persistProjects()
      this.persistLocalMeta()
    }

    return { added, skipped }
  }

  // --- Resource Removal (Respects existing scope selections) ---
  async removeResource(projectId: string, resourceId: string): Promise<void> {
    await delay(100)
    const project = this.projects.find((p) => p.id === projectId)
    if (project) {
      // 1. Remove from project's resource list
      project.resourceIds = project.resourceIds.filter((id) => id !== resourceId)

      // 2. Clear affected selection from study scope if present
      if (project.studyScope?.selectedResourceIds.includes(resourceId)) {
        project.studyScope.selectedResourceIds = project.studyScope.selectedResourceIds.filter(
          (id) => id !== resourceId
        )
      }

      project.updatedAt = new Date().toISOString()
      this.persistProjects()
    }

    // 3. Remove local resource item and in-memory File
    inMemoryFiles.delete(resourceId)
    this.resources = this.resources.filter((r) => r.id !== resourceId || r.kind === 'bundled')
    this.persistLocalMeta()
  }

  private simulateFailure = false

  setSimulateFailure(fail: boolean): void {
    this.simulateFailure = fail
  }

  getSimulateFailure(): boolean {
    return this.simulateFailure
  }

  // --- Study Scope ---
  async saveStudyScope(
    projectId: string,
    selectedTopicIds: string[],
    selectedResourceIds: string[],
    freeTextRequest = '',
    unresolvedResourceIds: string[] = []
  ): Promise<StudyScope> {
    await delay(120)
    if (this.simulateFailure) {
      throw new Error('Deterministic test error: Simulated network timeout while saving study scope.')
    }
    const project = this.projects.find((p) => p.id === projectId)
    if (!project) throw new Error('Project not found')
    if (selectedTopicIds.length === 0 && selectedResourceIds.length === 0) {
      throw new Error('Please select at least one topic or resource to define your study scope.')
    }

    const scope: StudyScope = {
      selectedTopicIds: [...selectedTopicIds],
      selectedResourceIds: [...selectedResourceIds],
      freeTextRequest: freeTextRequest.trim(),
      confirmedAt: new Date().toISOString(),
      unresolvedResourceIds: [...unresolvedResourceIds],
    }

    project.studyScope = scope
    project.updatedAt = new Date().toISOString()
    this.persistProjects()
    return { ...scope }
  }

  async getStudyScope(projectId: string): Promise<StudyScope | null> {
    await delay(50)
    const project = this.projects.find((p) => p.id === projectId)
    return project?.studyScope ? { ...project.studyScope } : null
  }

  // --- Simulated Study Plans (Versioned) ---
  async getPlanVersions(projectId: string): Promise<SimulatedPlan[]> {
    await delay(50)
    const versions = this.plans[projectId] ?? []
    return JSON.parse(JSON.stringify(versions))
  }

  async getPlan(projectId: string, version?: number): Promise<SimulatedPlan> {
    await delay(80)
    const versions = this.plans[projectId]
    if (versions && versions.length > 0) {
      if (version != null) {
        const found = versions.find((v) => v.version === version)
        if (found) return JSON.parse(JSON.stringify(found))
      }
      return JSON.parse(JSON.stringify(versions[versions.length - 1]))
    }

    const project = this.projects.find((p) => p.id === projectId)
    const topics = project?.studyScope?.selectedTopicIds ?? ['variables', 'conditions']
    const entries = topics.flatMap((tId, idx) => {
      const topic = SAMPLE_TOPICS.find((t) => t.id === tId)
      const title = topic?.title ?? tId
      return [
        {
          entryId: `gen-${tId}-learn`,
          topicId: tId,
          topicTitle: title,
          activityKind: 'learn' as const,
          activityTitle: `Study ${title} concepts`,
          durationMinutes: 15,
          resourceIds: ['res-python-basics'],
          resourceName: 'Python Basics.pdf',
          scheduledDay: `Day ${idx + 1}`,
          sequence: 1,
          completed: false,
          summary: `Read foundation notes and review code patterns for ${title}.`,
          steps: [
            `Read core concepts and syntax notes for ${title}.`,
            `Analyze code patterns and usage conventions.`,
            `Verify key rules and edge-case boundaries.`,
          ],
          expectedOutcome: `Foundational understanding of ${title} rules and syntax.`,
        },
        {
          entryId: `gen-${tId}-practice`,
          topicId: tId,
          topicTitle: title,
          activityKind: 'practice' as const,
          activityTitle: `Practice ${title} exercises`,
          durationMinutes: 20,
          resourceIds: ['res-python-basics'],
          resourceName: 'Python Basics.pdf',
          scheduledDay: `Day ${idx + 1}`,
          sequence: 2,
          completed: false,
          summary: `Trace and solve practice items for ${title}.`,
          steps: [
            `Trace worked examples for ${title} step-by-step.`,
            `Solve 3 guided exercises on your local scratchpad.`,
            `Check your results against sample solutions.`,
          ],
          expectedOutcome: `Confidence applying ${title} in standalone snippets.`,
        },
      ]
    })

    const generatedPlan: SimulatedPlan = {
      planId: `plan-${projectId}-v1`,
      projectId,
      version: 1,
      status: 'active',
      feasibility: 'full',
      totalMinutes: entries.reduce((acc, curr) => acc + curr.durationMinutes, 0),
      createdAt: new Date().toISOString(),
      entries,
    }

    this.plans[projectId] = [generatedPlan]
    this.persistPlans()
    return JSON.parse(JSON.stringify(generatedPlan))
  }

  async toggleSessionCompletion(
    projectId: string,
    entryId: string,
    completed: boolean,
    version?: number
  ): Promise<SimulatedPlan> {
    await delay(80)
    if (this.simulateFailure) {
      throw new Error('Deterministic test error: Simulated network timeout while syncing session completion.')
    }
    const versions = this.plans[projectId]
    if (!versions || versions.length === 0) throw new Error('Plan not found')

    const targetPlan =
      version != null
        ? versions.find((p) => p.version === version) ?? versions[versions.length - 1]
        : versions[versions.length - 1]

    if (!targetPlan) throw new Error('Target plan version not found')

    const entry = targetPlan.entries.find((e) => e.entryId === entryId)
    if (entry) {
      entry.completed = completed
      this.persistPlans()
    }
    return JSON.parse(JSON.stringify(targetPlan))
  }

  async replanWithRequest(
    projectId: string,
    request: ReplanRequest
  ): Promise<{ plan: SimulatedPlan; isSupportedScenario: boolean; explanation: string }> {
    await delay(160)
    if (this.simulateFailure) {
      throw new Error('Deterministic test error: Simulated network timeout during replan.')
    }

    const currentPlan = await this.getPlan(projectId)
    const completedEntryIds = new Set(
      currentPlan.entries.filter((e) => e.completed).map((e) => e.entryId)
    )

    // Check if request matches the supported scenario ("Spend more time on loops and spread remaining work over more days")
    const isSupported =
      request.focusTopicIds.includes('loops') ||
      /loop|spread|more days|pace|slow/i.test(request.reason)

    const updatedPlan: SimulatedPlan = JSON.parse(JSON.stringify(SAMPLE_PLAN_V2))
    updatedPlan.projectId = projectId
    updatedPlan.planId = `plan-${projectId}-v2`
    updatedPlan.version = 2
    updatedPlan.createdAt = new Date().toISOString()

    // Strictly preserve completed work from earlier plan
    for (const entry of updatedPlan.entries) {
      if (completedEntryIds.has(entry.entryId)) {
        entry.completed = true
      }
    }

    let explanation = ''
    if (isSupported) {
      explanation =
        'Applied pre-authored sample replan: Preserved completed Day 1 sessions, added a 15-minute reinforcement drill for Loops on Day 3, and spread sessions across 5 days to cap daily study under 35 minutes.'
      updatedPlan.replanReason = request.reason || updatedPlan.replanReason
    } else {
      explanation =
        'Custom scheduling algorithms are handled by Person 3 during live planning integration. Your request has been preserved, and the supported sample replan (focus on loops across 5 days) is previewed below.'
      updatedPlan.replanReason = `${request.reason} (Previewed via bundled sample replan)`
    }

    // Persist new version alongside existing versions without overwriting version 1
    if (!this.plans[projectId]) {
      this.plans[projectId] = [currentPlan]
    }
    const existingV2Index = this.plans[projectId].findIndex((p) => p.version === 2)
    if (existingV2Index >= 0) {
      this.plans[projectId][existingV2Index] = updatedPlan
    } else {
      this.plans[projectId].push(updatedPlan)
    }

    this.persistPlans()
    return {
      plan: JSON.parse(JSON.stringify(updatedPlan)),
      isSupportedScenario: isSupported,
      explanation,
    }
  }

  async simulateReplan(projectId: string): Promise<SimulatedPlan> {
    const result = await this.replanWithRequest(projectId, {
      reason: 'Spend more time on loops and spread the remaining work over more days.',
      focusTopicIds: ['loops'],
      deadlineChanged: true,
      newTargetDate: '2026-11-04',
      dailyStudyMinutes: 35,
      preservePreferences: 'Keep completed Day 1 sessions and preserve original resource selections.',
    })
    return result.plan
  }

  // --- Reset Demo State ---
  async resetDemoState(): Promise<void> {
    await delay(120)
    localStorage.removeItem(STORAGE_KEY_PROJECTS)
    localStorage.removeItem(STORAGE_KEY_ACTIVE_PROJECT)
    localStorage.removeItem(STORAGE_KEY_PLANS)
    localStorage.removeItem(STORAGE_KEY_LOCAL_META)
    inMemoryFiles.clear()
    this.loadState()
  }
}

export const mockCurriculumService = new CurriculumMockService()
