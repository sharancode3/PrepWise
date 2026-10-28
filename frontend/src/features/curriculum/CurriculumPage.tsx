import { useEffect, useState } from 'react'
import { BookOpen, FolderPlus, Layers, Library, RefreshCw } from 'lucide-react'
import { Button, Eyebrow, Notice } from '../../components/ui'
import { CurriculumOverview } from './CurriculumOverview'
import { CurriculumPlanView } from './CurriculumPlanView'
import { CurriculumResourcesView } from './CurriculumResourcesView'
import { ProjectModal } from './ProjectModal'
import { liveCurriculumService } from './liveService'
import type {
  BatchUploadResult,
  CurriculumTopic,
  LearningProject,
  ReplanRequest,
  ResourceItem,
  SimulatedPlan,
} from './types'
import './curriculum.css'

type TabType = 'overview' | 'plan' | 'resources'

export function CurriculumPage() {
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [projects, setProjects] = useState<LearningProject[]>([])
  const [activeProject, setActiveProject] = useState<LearningProject | null>(null)
  const [topics, setTopics] = useState<CurriculumTopic[]>([])
  const [resources, setResources] = useState<ResourceItem[]>([])
  const [plan, setPlan] = useState<SimulatedPlan | null>(null)
  const [availableVersions, setAvailableVersions] = useState<number[]>([1])
  const [activePlanVersion, setActivePlanVersion] = useState<number>(1)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [reloadTrigger, setReloadTrigger] = useState(0)

  // Load initial data from mock service
  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    async function load() {
      try {
        const [loadedTopics, loadedProjects, activeId] = await Promise.all([
          liveCurriculumService.getTopics(),
          liveCurriculumService.listProjects(),
          liveCurriculumService.getActiveProjectId(),
        ])

        if (!active) return

        setTopics(loadedTopics)
        setProjects(loadedProjects)

        const currentProj =
          loadedProjects.find((p) => p.id === activeId) ?? loadedProjects[0] ?? null
        setActiveProject(currentProj)

        if (currentProj) {
          const [loadedRes, loadedPlan, loadedVersions] = await Promise.all([
            liveCurriculumService.listResources(currentProj.id),
            liveCurriculumService.getPlan(currentProj.id),
            liveCurriculumService.getPlanVersions(currentProj.id),
          ])
          if (!active) return
          setResources(loadedRes)
          setPlan(loadedPlan)
          const vers = loadedVersions.map((p) => p.version)
          setAvailableVersions(vers.length > 0 ? vers : [loadedPlan.version])
          setActivePlanVersion(loadedPlan.version)
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Could not load curriculum data.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [reloadTrigger])

  async function handleSwitchProject(projectId: string) {
    if (!projectId) return
    setLoading(true)
    try {
      const switched = await liveCurriculumService.setActiveProject(projectId)
      setActiveProject(switched)
      const [resList, planData, versList] = await Promise.all([
        liveCurriculumService.listResources(switched.id),
        liveCurriculumService.getPlan(switched.id),
        liveCurriculumService.getPlanVersions(switched.id),
      ])
      setResources(resList)
      setPlan(planData)
      const vers = versList.map((p) => p.version)
      setAvailableVersions(vers.length > 0 ? vers : [planData.version])
      setActivePlanVersion(planData.version)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not switch project.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateProject(title: string, description: string) {
    const created = await liveCurriculumService.createProject(title, description)
    setProjects([created, ...projects.filter((p) => p.id !== created.id)])
    setActiveProject(created)
    const [resList, planData, versList] = await Promise.all([
      liveCurriculumService.listResources(created.id),
      liveCurriculumService.getPlan(created.id),
      liveCurriculumService.getPlanVersions(created.id),
    ])
    setResources(resList)
    setPlan(planData)
    const vers = versList.map((p) => p.version)
    setAvailableVersions(vers.length > 0 ? vers : [planData.version])
    setActivePlanVersion(planData.version)
    setActiveTab('overview')
  }

  async function handleSelectVersion(version: number) {
    if (!activeProject) return
    const chosen = await liveCurriculumService.getPlan(activeProject.id, version)
    setPlan(chosen)
    setActivePlanVersion(version)
  }

  async function handleSaveScope(
    selectedTopics: string[],
    selectedResources: string[],
    freeText: string,
    unresolvedResources: string[] = []
  ) {
    if (!activeProject) return
    const updatedScope = await liveCurriculumService.saveStudyScope(
      activeProject.id,
      selectedTopics,
      selectedResources,
      freeText,
      unresolvedResources
    )
    setActiveProject({
      ...activeProject,
      studyScope: updatedScope,
    })
    const updatedPlan = await liveCurriculumService.getPlan(activeProject.id)
    setPlan(updatedPlan)
    const versList = await liveCurriculumService.getPlanVersions(activeProject.id)
    setAvailableVersions(versList.map((p) => p.version))
    setActivePlanVersion(updatedPlan.version)
  }

  async function handleUploadBatch(files: File[], topicId: string): Promise<BatchUploadResult> {
    if (!activeProject) return { added: [], skipped: [] }
    const result = await liveCurriculumService.addLocalFiles(activeProject.id, files, topicId)
    if (result.added.length > 0) {
      setResources((prev) => [...prev, ...result.added])
      setActiveProject((prev) =>
        prev ? { ...prev, resourceIds: [...prev.resourceIds, ...result.added.map((r) => r.id)] } : null
      )
    }
    return result
  }

  async function handleRemoveResource(resourceId: string) {
    if (!activeProject) return
    await liveCurriculumService.removeResource(activeProject.id, resourceId)
    setResources((prev) => prev.filter((r) => r.id !== resourceId))
    setActiveProject((prev) => {
      if (!prev) return null
      const updatedIds = prev.resourceIds.filter((id) => id !== resourceId)
      const updatedScope = prev.studyScope
        ? {
            ...prev.studyScope,
            selectedResourceIds: prev.studyScope.selectedResourceIds.filter((id) => id !== resourceId),
          }
        : null
      return {
        ...prev,
        resourceIds: updatedIds,
        studyScope: updatedScope,
      }
    })
  }

  async function handleToggleSession(entryId: string, completed: boolean) {
    if (!activeProject) return
    const updated = await liveCurriculumService.toggleSessionCompletion(
      activeProject.id,
      entryId,
      completed,
      activePlanVersion
    )
    setPlan(updated)
  }

  async function handleReplanWithRequest(request: ReplanRequest) {
    if (!activeProject) return
    const result = await liveCurriculumService.replanWithRequest(activeProject.id, request)
    setPlan(result.plan)
    setActivePlanVersion(result.plan.version)
    const versList = await liveCurriculumService.getPlanVersions(activeProject.id)
    setAvailableVersions(versList.map((p) => p.version))
  }

  async function handleSimulateReplan() {
    if (!activeProject) return
    const updated = await liveCurriculumService.simulateReplan(activeProject.id)
    setPlan(updated)
    setActivePlanVersion(updated.version)
    const versList = await liveCurriculumService.getPlanVersions(activeProject.id)
    setAvailableVersions(versList.map((p) => p.version))
  }

  async function handleResetDemo() {
    setLoading(true)
    await liveCurriculumService.resetDemoState()
    setReloadTrigger((n) => n + 1)
  }

  return (
    <section className="container page-section">
      <div className="workspace-header">
        <div>
          <div className="workspace-meta">
            <Eyebrow>Curriculum & Planning</Eyebrow>
            <span className="demo-badge">Demo workspace</span>
          </div>
          <h1 className="page-title" style={{ marginTop: 8, marginBottom: 4 }}>
            Curriculum workspace
          </h1>
          <p className="page-intro" style={{ margin: 0 }}>
            Review core foundations, manage resources, and prepare your study scope.
          </p>
        </div>

        <div className="project-controls">
          {projects.length > 0 && activeProject && (
            <select
              className="project-select"
              value={activeProject.id}
              onChange={(e) => handleSwitchProject(e.target.value)}
              aria-label="Select learning project"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          )}

          <Button onClick={() => setIsModalOpen(true)}>
            <FolderPlus size={16} aria-hidden="true" />
            Create project
          </Button>

          <Button variant="secondary" onClick={handleResetDemo} title="Reset demo state">
            <RefreshCw size={14} aria-hidden="true" />
          </Button>
        </div>
      </div>

      {error ? (
        <div style={{ marginTop: 24 }}>
          <Notice error>{error}</Notice>
          <div style={{ marginTop: 12 }}>
            <Button variant="secondary" onClick={() => setReloadTrigger((n) => n + 1)}>
              Try again
            </Button>
          </div>
        </div>
      ) : loading ? (
        <div style={{ marginTop: 32 }}>
          <Notice>Loading curriculum workspace…</Notice>
        </div>
      ) : !activeProject ? (
        <div className="section-card" style={{ marginTop: 24, textAlign: 'center', padding: '48px 24px' }}>
          <h2>No project selected</h2>
          <p className="section-desc">Create your first learning project to explore curriculum topics and plan study sessions.</p>
          <Button onClick={() => setIsModalOpen(true)}>
            <FolderPlus size={16} aria-hidden="true" />
            Create project
          </Button>
        </div>
      ) : (
        <div className="curriculum-workspace" style={{ marginTop: 24 }}>
          <div className="workspace-body">
            {/* Local Sidebar Navigation */}
            <aside className="workspace-sidebar" aria-label="Curriculum workspace sections">
              <button
                type="button"
                className={`sidebar-tab ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => setActiveTab('overview')}
              >
                <Layers size={17} aria-hidden="true" />
                Overview
              </button>
              <button
                type="button"
                className={`sidebar-tab ${activeTab === 'plan' ? 'active' : ''}`}
                onClick={() => setActiveTab('plan')}
              >
                <BookOpen size={17} aria-hidden="true" />
                Study plan
              </button>
              <button
                type="button"
                className={`sidebar-tab ${activeTab === 'resources' ? 'active' : ''}`}
                onClick={() => setActiveTab('resources')}
              >
                <Library size={17} aria-hidden="true" />
                Resources
              </button>
            </aside>

            {/* Tab Viewport */}
            <main className="workspace-viewport">
              {activeTab === 'overview' && (
                <CurriculumOverview
                  project={activeProject}
                  topics={topics}
                  resourceCount={resources.length}
                  onNavigateTab={setActiveTab}
                />
              )}

              {activeTab === 'plan' && (
                <CurriculumPlanView
                  project={activeProject}
                  topics={topics}
                  resources={resources}
                  plan={plan}
                  availableVersions={availableVersions}
                  activeVersion={activePlanVersion}
                  onSelectVersion={handleSelectVersion}
                  onSaveScope={handleSaveScope}
                  onToggleSession={handleToggleSession}
                  onReplanWithRequest={handleReplanWithRequest}
                  onSimulateReplan={handleSimulateReplan}
                />
              )}

              {activeTab === 'resources' && (
                <CurriculumResourcesView
                  resources={resources}
                  topics={topics}
                  onUploadBatch={handleUploadBatch}
                  onRemoveResource={handleRemoveResource}
                  onNavigateToPlan={() => setActiveTab('plan')}
                />
              )}
            </main>
          </div>
        </div>
      )}

      {/* Project Modal Dialog */}
      <ProjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateProject}
      />
    </section>
  )
}
