import { useState } from 'react'
import type { CurriculumTopic } from './types'

interface PrerequisiteMapProps {
  topics: CurriculumTopic[]
  selectedTopicId?: string
  onSelectTopic?: (topicId: string) => void
}

export function PrerequisiteMap({
  topics,
  selectedTopicId,
  onSelectTopic,
}: PrerequisiteMapProps) {
  const [internalSelected, setInternalSelected] = useState<string>(
    selectedTopicId || topics[0]?.id || 'variables'
  )

  const activeId = selectedTopicId || internalSelected
  const activeTopic = topics.find((t) => t.id === activeId) ?? topics[0]

  function handleSelect(id: string) {
    setInternalSelected(id)
    onSelectTopic?.(id)
  }

  // Node coordinates for 4 sequential topics in SVG
  const nodeWidth = 120
  const nodeHeight = 52
  const nodes = [
    { id: 'variables', x: 20, y: 35, title: 'Variables' },
    { id: 'conditions', x: 190, y: 35, title: 'Conditions' },
    { id: 'loops', x: 360, y: 35, title: 'Loops' },
    { id: 'functions', x: 530, y: 35, title: 'Functions' },
  ]

  return (
    <div className="prerequisite-map-container" style={{ margin: '16px 0' }}>
      {/* 1. Responsive SVG Diagram */}
      <div style={{ width: '100%', overflowX: 'auto', background: 'var(--dp-color-ground)', padding: '16px 12px', borderRadius: 8, border: '1px solid var(--dp-color-rule)' }}>
        <svg
          viewBox="0 0 680 120"
          width="100%"
          height="120"
          role="img"
          aria-label="Interactive curriculum prerequisite flow chart"
          style={{ display: 'block', margin: '0 auto', maxWidth: 680 }}
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--dp-color-accent)" />
            </marker>
          </defs>

          {/* Connecting Arrows */}
          <line x1={140} y1={61} x2={186} y2={61} stroke="var(--dp-color-accent)" strokeWidth="2" markerEnd="url(#arrow)" />
          <line x1={310} y1={61} x2={356} y2={61} stroke="var(--dp-color-accent)" strokeWidth="2" markerEnd="url(#arrow)" />
          <line x1={480} y1={61} x2={526} y2={61} stroke="var(--dp-color-accent)" strokeWidth="2" markerEnd="url(#arrow)" />

          {/* Nodes */}
          {nodes.map((node, index) => {
            const isSelected = node.id === activeId
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={`Topic ${index + 1}: ${node.title}. Click or press Enter to view objectives.`}
                onClick={() => handleSelect(node.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleSelect(node.id)
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                <rect
                  x={node.x}
                  y={node.y}
                  width={nodeWidth}
                  height={nodeHeight}
                  rx={8}
                  fill={isSelected ? '#eef3ff' : '#ffffff'}
                  stroke={isSelected ? 'var(--dp-color-accent)' : 'var(--dp-color-rule)'}
                  strokeWidth={isSelected ? 2 : 1}
                />
                <text
                  x={node.x + 10}
                  y={node.y + 20}
                  fill={isSelected ? 'var(--dp-color-accent)' : 'var(--dp-color-ink-secondary)'}
                  fontSize="10"
                  fontWeight="700"
                  fontFamily="inherit"
                >
                  STEP 0{index + 1}
                </text>
                <text
                  x={node.x + 10}
                  y={node.y + 38}
                  fill="var(--dp-color-ink)"
                  fontSize="13"
                  fontWeight="600"
                  fontFamily="inherit"
                >
                  {node.title}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* 2. Selected Topic Details Card */}
      {activeTopic && (
        <div
          style={{
            marginTop: 12,
            padding: '14px 18px',
            background: 'var(--dp-color-panel)',
            border: '1px solid var(--dp-color-rule)',
            borderRadius: 8,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
            <strong style={{ fontSize: 16 }}>{activeTopic.title}</strong>
            <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)', background: 'var(--dp-color-ground-muted)', padding: '2px 8px', borderRadius: 4 }}>
              Difficulty {activeTopic.difficulty}/5 · {activeTopic.learn_minutes}m learn · {activeTopic.practice_minutes}m practice
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 14, color: 'var(--dp-color-ink-secondary)', lineHeight: 1.5 }}>
            {activeTopic.objective}
          </p>
          <div style={{ marginTop: 8, fontSize: 13, color: 'var(--dp-color-ink)' }}>
            <strong>Prerequisites: </strong>
            {activeTopic.prerequisites.length
              ? activeTopic.prerequisites
                  .map((pid) => topics.find((t) => t.id === pid)?.title ?? pid)
                  .join(', ')
              : 'None (Foundational starting point)'}
          </div>
        </div>
      )}

      {/* 3. Accessible Screen-reader / Text Equivalent List */}
      <details style={{ marginTop: 12, fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
        <summary style={{ cursor: 'pointer', fontWeight: 500 }}>
          View accessible linear topic list
        </summary>
        <ol style={{ paddingLeft: 20, margin: '8px 0' }}>
          {topics.map((t, idx) => (
            <li key={t.id} style={{ marginBottom: 4 }}>
              <strong>{t.title}</strong> — {t.objective} ({t.learn_minutes + t.practice_minutes} min)
              {t.prerequisites.length > 0 && ` [Requires: ${t.prerequisites.join(', ')}]`}
            </li>
          ))}
        </ol>
      </details>
    </div>
  )
}
