import { useState, useMemo } from 'react'
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
    selectedTopicId || topics[0]?.id || ''
  )

  const activeId = selectedTopicId || internalSelected
  const activeTopic = topics.find((t) => t.id === activeId) ?? topics[0]

  function handleSelect(id: string) {
    setInternalSelected(id)
    onSelectTopic?.(id)
  }

  // Compute topological levels and layout coordinates dynamically
  const { nodes, edges, svgWidth, svgHeight } = useMemo(() => {
    if (!topics || topics.length === 0) {
      return { nodes: [], edges: [], svgWidth: 600, svgHeight: 120 }
    }

    const nodeWidth = 130
    const nodeHeight = 50
    const xGap = 60
    const yGap = 30

    // Build dependency map
    const topicMap = new Map(topics.map((t) => [t.id, t]))
    const depthMap: Record<string, number> = {}

    function getDepth(tid: string, visited: Set<string>): number {
      if (depthMap[tid] !== undefined) return depthMap[tid]
      if (visited.has(tid)) return 0 // Cycle safeguard
      visited.add(tid)

      const topic = topicMap.get(tid)
      if (!topic || !topic.prerequisites || topic.prerequisites.length === 0) {
        depthMap[tid] = 0
        return 0
      }

      let maxP = 0
      for (const p of topic.prerequisites) {
        maxP = Math.max(maxP, 1 + getDepth(p, new Set(visited)))
      }
      depthMap[tid] = maxP
      return maxP
    }

    for (const t of topics) {
      getDepth(t.id, new Set())
    }

    // Group by level
    const levels: Record<number, CurriculumTopic[]> = {}
    for (const t of topics) {
      const lvl = depthMap[t.id] || 0
      if (!levels[lvl]) levels[lvl] = []
      levels[lvl].push(t)
    }

    const maxLevel = Math.max(0, ...Object.keys(levels).map(Number))
    let maxLevelCount = 1

    const nodeCoords: { id: string; x: number; y: number; width: number; height: number; title: string }[] = []
    const coordMap: Record<string, { x: number; y: number }> = {}

    for (let l = 0; l <= maxLevel; l++) {
      const col = levels[l] || []
      maxLevelCount = Math.max(maxLevelCount, col.length)
      col.forEach((topic, rowIdx) => {
        const x = 30 + l * (nodeWidth + xGap)
        const y = 30 + rowIdx * (nodeHeight + yGap)
        nodeCoords.push({
          id: topic.id,
          x,
          y,
          width: nodeWidth,
          height: nodeHeight,
          title: topic.title,
        })
        coordMap[topic.id] = { x, y }
      })
    }

    // Build edges from prerequisites
    const edgesList: { fromId: string; toId: string; x1: number; y1: number; x2: number; y2: number }[] = []
    for (const t of topics) {
      if (!t.prerequisites) continue
      const targetCoord = coordMap[t.id]
      if (!targetCoord) continue

      for (const p of t.prerequisites) {
        const sourceCoord = coordMap[p]
        if (sourceCoord) {
          edgesList.push({
            fromId: p,
            toId: t.id,
            x1: sourceCoord.x + nodeWidth,
            y1: sourceCoord.y + nodeHeight / 2,
            x2: targetCoord.x,
            y2: targetCoord.y + nodeHeight / 2,
          })
        }
      }
    }

    const totalW = Math.max(680, 60 + (maxLevel + 1) * (nodeWidth + xGap))
    const totalH = Math.max(120, 60 + maxLevelCount * (nodeHeight + yGap))

    return {
      nodes: nodeCoords,
      edges: edgesList,
      svgWidth: totalW,
      svgHeight: totalH,
    }
  }, [topics])

  if (!topics || topics.length === 0) {
    return (
      <div style={{ padding: '1rem', color: 'var(--dp-color-ink-muted)' }}>
        No topics found in this curriculum.
      </div>
    )
  }

  return (
    <div className="prerequisite-map-container" style={{ margin: '16px 0' }}>
      {/* 1. Responsive Topological SVG Diagram */}
      <div
        style={{
          width: '100%',
          overflowX: 'auto',
          background: 'var(--dp-color-ground)',
          padding: '16px 12px',
          borderRadius: 8,
          border: '1px solid var(--dp-color-rule, var(--dp-color-border))',
        }}
      >
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          width={svgWidth}
          height={svgHeight}
          role="img"
          aria-label="Interactive curriculum prerequisite dependency graph"
        >
          <defs>
            <marker
              id="dynamic-arrow-head"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--dp-color-rule, #94a3b8)" />
            </marker>
          </defs>

          {/* Dependency Connections */}
          {edges.map((e, idx) => (
            <line
              key={`${e.fromId}-${e.toId}-${idx}`}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              stroke="var(--dp-color-rule, #94a3b8)"
              strokeWidth="2"
              markerEnd="url(#dynamic-arrow-head)"
            />
          ))}

          {/* Interactive Topic Nodes */}
          {nodes.map((node) => {
            const isSelected = node.id === activeId
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={`Select topic: ${node.title}`}
                onClick={() => handleSelect(node.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleSelect(node.id)
                  }
                }}
                style={{ cursor: 'pointer', outline: 'none' }}
              >
                <rect
                  x={node.x}
                  y={node.y}
                  width={node.width}
                  height={node.height}
                  rx="6"
                  ry="6"
                  fill={isSelected ? '#074ce0' : '#ffffff'}
                  stroke={isSelected ? '#074ce0' : 'var(--dp-color-rule, #cbd5e1)'}
                  strokeWidth={isSelected ? '2' : '1.5'}
                />
                <text
                  x={node.x + node.width / 2}
                  y={node.y + node.height / 2 + 5}
                  textAnchor="middle"
                  fill={isSelected ? '#ffffff' : '#16191f'}
                  fontSize="13"
                  fontWeight={isSelected ? '600' : '500'}
                  fontFamily="inherit"
                >
                  {node.title.length > 14 ? `${node.title.slice(0, 12)}…` : node.title}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* 2. Selected Node Details */}
      {activeTopic && (
        <div
          style={{
            marginTop: 12,
            padding: '12px 16px',
            background: 'var(--dp-color-muted, #f8fafc)',
            borderRadius: 6,
            fontSize: '0.85rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <div>
            <strong style={{ color: 'var(--dp-color-ink, #0f172a)', fontSize: '0.95rem' }}>
              {activeTopic.title}
            </strong>
            <p style={{ margin: '2px 0 0 0', color: 'var(--dp-color-ink-muted, #64748b)' }}>
              {activeTopic.objective || 'Focus on foundational concepts and structured exercises.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12, fontSize: '0.8rem', color: 'var(--dp-color-ink-muted, #64748b)' }}>
            <span>Learn: {activeTopic.learn_minutes}m</span>
            <span>Practice: {activeTopic.practice_minutes}m</span>
            <span>
              Prerequisites:{' '}
              {activeTopic.prerequisites && activeTopic.prerequisites.length > 0
                ? activeTopic.prerequisites.join(', ')
                : 'None (Root topic)'}
            </span>
          </div>
        </div>
      )}

      {/* 3. Accessible Linear Prerequisite List */}
      <details style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--dp-color-ink-muted, #64748b)' }}>
        <summary style={{ cursor: 'pointer' }}>View linear prerequisite sequence (Screen Reader accessible)</summary>
        <ol style={{ paddingLeft: 20, marginTop: 4 }}>
          {topics.map((t) => (
            <li key={t.id}>
              <strong>{t.title}</strong>{' '}
              {t.prerequisites && t.prerequisites.length > 0
                ? `(Requires: ${t.prerequisites.join(', ')})`
                : '(No prerequisite foundations required)'}
            </li>
          ))}
        </ol>
      </details>
    </div>
  )
}
