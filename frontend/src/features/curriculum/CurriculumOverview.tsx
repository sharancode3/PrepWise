import { ArrowRight, BookOpen, Clock, FileText, Layers } from 'lucide-react'
import { Button } from '../../components/ui'
import { PrerequisiteMap } from './PrerequisiteMap'
import type { CurriculumTopic, LearningProject } from './types'

interface OverviewProps {
  project: LearningProject
  topics: CurriculumTopic[]
  resourceCount: number
  onNavigateTab: (tab: 'overview' | 'plan' | 'resources') => void
}

export function CurriculumOverview({
  project,
  topics,
  resourceCount,
  onNavigateTab,
}: OverviewProps) {
  const selectedCount = project.studyScope?.selectedTopicIds.length ?? 0
  const totalStudyMinutes = topics.reduce(
    (acc, t) => acc + t.learn_minutes + t.practice_minutes,
    0
  )

  return (
    <div className="curriculum-overview">
      <div className="section-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ margin: '0 0 6px 0' }}>{project.title}</h2>
            <p className="section-desc" style={{ marginBottom: 12 }}>
              {project.description || 'No description provided for this project.'}
            </p>
          </div>
          <Button onClick={() => onNavigateTab('plan')}>
            Open study plan <ArrowRight size={16} aria-hidden="true" />
          </Button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 14 }}>
          <div style={{ padding: '12px 16px', background: 'var(--dp-color-ground-muted)', borderRadius: 8 }}>
            <div style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Layers size={14} aria-hidden="true" /> Curriculum topics
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--dp-color-ink)', marginTop: 4 }}>
              {topics.length} topics
            </div>
          </div>

          <div style={{ padding: '12px 16px', background: 'var(--dp-color-ground-muted)', borderRadius: 8 }}>
            <div style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <FileText size={14} aria-hidden="true" /> Study resources
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--dp-color-ink)', marginTop: 4 }}>
              {resourceCount} files
            </div>
          </div>

          <div style={{ padding: '12px 16px', background: 'var(--dp-color-ground-muted)', borderRadius: 8 }}>
            <div style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <BookOpen size={14} aria-hidden="true" /> Scope selected
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--dp-color-ink)', marginTop: 4 }}>
              {selectedCount > 0 ? `${selectedCount} chosen` : 'Not selected'}
            </div>
          </div>

          <div style={{ padding: '12px 16px', background: 'var(--dp-color-ground-muted)', borderRadius: 8 }}>
            <div style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Clock size={14} aria-hidden="true" /> Total content time
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--dp-color-ink)', marginTop: 4 }}>
              {totalStudyMinutes} min
            </div>
          </div>
        </div>
      </div>

      <div className="section-card">
        <h2>Prerequisite roadmap</h2>
        <p className="section-desc">
          Foundation concepts must be mastered before dependent topics can be scheduled. Click any topic node to view its objectives and prerequisites.
        </p>

        {/* Interactive SVG Prerequisite Diagram */}
        <PrerequisiteMap topics={topics} />

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
          <Button variant="secondary" onClick={() => onNavigateTab('resources')}>
            View study resources <ArrowRight size={16} aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  )
}
