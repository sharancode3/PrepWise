import React from 'react'
import { Sparkles, BookOpen, Layers, CheckCircle2, FileText, RefreshCw, Zap } from 'lucide-react'
import type { SupportMode } from './types'

interface SectionItem {
  id: string
  label: string
  icon: React.ReactNode
}

interface StudyOutlineProps {
  activeSection: string
  onSelectSection: (id: string) => void
  currentMode: SupportMode
  generatingMode: SupportMode | null
  onRequestMode: (mode: SupportMode) => void
  hasSources: boolean
}

export const StudyOutline: React.FC<StudyOutlineProps> = ({
  activeSection,
  onSelectSection,
  currentMode,
  generatingMode,
  onRequestMode,
  hasSources,
}) => {
  const sections: SectionItem[] = [
    { id: 'overview', label: 'Overview', icon: <BookOpen size={15} aria-hidden="true" /> },
    { id: 'learn', label: 'Learn', icon: <Sparkles size={15} aria-hidden="true" /> },
    { id: 'worked-example', label: 'Worked Example', icon: <Layers size={15} aria-hidden="true" /> },
    { id: 'practice', label: 'Practice', icon: <CheckCircle2 size={15} aria-hidden="true" /> },
  ]

  if (hasSources) {
    sections.push({ id: 'sources', label: 'Sources', icon: <FileText size={15} aria-hidden="true" /> })
  }

  const isPending = generatingMode !== null

  return (
    <aside className="study-sidebar" aria-label="Lesson Navigation">
      <div className="study-sidebar-heading">Lesson Outline</div>
      <nav className="study-outline-nav">
        {sections.map((sec) => {
          const isActive = activeSection === sec.id
          return (
            <button
              key={sec.id}
              type="button"
              className={`study-outline-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectSection(sec.id)}
              aria-current={isActive ? 'true' : undefined}
            >
              <span className="study-outline-dot" aria-hidden="true" />
              {sec.icon}
              <span>{sec.label}</span>
            </button>
          )
        })}
      </nav>

      <div className="study-mode-box">
        <div className="study-mode-label">Adaptive Support</div>
        <div className="study-mode-buttons">
          <button
            type="button"
            className={`study-mode-btn ${currentMode === 'normal' ? 'active' : ''}`}
            disabled={isPending}
            onClick={() => onRequestMode('normal')}
          >
            <RefreshCw size={13} className={generatingMode === 'normal' ? 'spin' : ''} aria-hidden="true" />
            <span>Standard Pacing</span>
          </button>

          <button
            type="button"
            className={`study-mode-btn ${currentMode === 'simpler' ? 'active' : ''}`}
            disabled={isPending}
            onClick={() => onRequestMode('simpler')}
          >
            <Zap size={13} className={generatingMode === 'simpler' ? 'spin' : ''} aria-hidden="true" />
            <span>Explain More Simply</span>
          </button>

          <button
            type="button"
            className={`study-mode-btn ${currentMode === 'another_example' ? 'active' : ''}`}
            disabled={isPending}
            onClick={() => onRequestMode('another_example')}
          >
            <Layers size={13} className={generatingMode === 'another_example' ? 'spin' : ''} aria-hidden="true" />
            <span>Another Example</span>
          </button>
        </div>
      </div>
    </aside>
  )
}
