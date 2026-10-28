import React from 'react'
import type { DiagramData } from './types'

interface StudyDiagramProps {
  diagram: DiagramData
}

export const StudyDiagram: React.FC<StudyDiagramProps> = ({ diagram }) => {
  const { kind, title, headers, rows } = diagram

  if (!rows || rows.length === 0) {
    return null
  }

  const safeHeaders = headers || []
  const rowHeight = 44
  const headerHeight = 38
  const tableHeight = headerHeight + rows.length * rowHeight + 20
  const svgWidth = 620
  const colCount = Math.max(safeHeaders.length, rows[0]?.length || 1)
  const colWidth = (svgWidth - 40) / colCount

  return (
    <div className="study-diagram-panel">
      <div className="study-diagram-header">{title}</div>
      <svg
        role="img"
        aria-labelledby="study-diagram-title study-diagram-desc"
        viewBox={`0 0 ${svgWidth} ${tableHeight}`}
        width="100%"
        height="auto"
        style={{ display: 'block', maxWidth: '100%', fontVariantNumeric: 'tabular-nums' }}
      >
        <title id="study-diagram-title">{title}</title>
        <desc id="study-diagram-desc">
          Structured {kind} diagram showing {rows.length} steps: {safeHeaders.join(', ')}
        </desc>

        {/* Outer border & background */}
        <rect
          x="1"
          y="1"
          width={svgWidth - 2}
          height={tableHeight - 2}
          rx="8"
          fill="#fcfcfd"
          stroke="#dde0e6"
          strokeWidth="1"
        />

        {/* Header background */}
        <rect
          x="1"
          y="1"
          width={svgWidth - 2}
          height={headerHeight}
          rx="8"
          fill="#f3f4f6"
        />
        {/* Flat bottom for header to join cleanly */}
        <rect
          x="1"
          y={headerHeight - 8}
          width={svgWidth - 2}
          height="8"
          fill="#f3f4f6"
        />
        <line
          x1="1"
          y1={headerHeight}
          x2={svgWidth - 1}
          y2={headerHeight}
          stroke="#dde0e6"
          strokeWidth="1"
        />

        {/* Header labels */}
        {safeHeaders.map((hdr, idx) => (
          <text
            key={`hdr-${idx}`}
            x={20 + idx * colWidth + 8}
            y={24}
            fill="#16191f"
            fontSize="12"
            fontWeight="600"
            fontFamily="var(--font-display)"
            letterSpacing="-0.01em"
          >
            {hdr}
          </text>
        ))}

        {/* Table rows */}
        {rows.map((row, rowIdx) => {
          const y = headerHeight + rowIdx * rowHeight
          const isEven = rowIdx % 2 === 0
          return (
            <g key={`row-${rowIdx}`}>
              {/* Row subtle zebra background */}
              {isEven && (
                <rect
                  x="2"
                  y={y}
                  width={svgWidth - 4}
                  height={rowHeight}
                  fill="#fbfcfd"
                />
              )}

              {/* Row divider */}
              {rowIdx > 0 && (
                <line
                  x1="12"
                  y1={y}
                  x2={svgWidth - 12}
                  y2={y}
                  stroke="#dde0e6"
                  strokeWidth="0.8"
                  strokeDasharray="3 3"
                />
              )}

              {/* Connecting trace arrow on the left margin */}
              {rowIdx < rows.length - 1 && (
                <path
                  d={`M 14 ${y + 22} L 14 ${y + rowHeight + 10}`}
                  stroke="#074ce0"
                  strokeWidth="1.2"
                  strokeDasharray="2 2"
                  fill="none"
                />
              )}

              {/* Cells */}
              {row.map((cellText, cellIdx) => {
                const cellX = 20 + cellIdx * colWidth + 8
                const isFirstCol = cellIdx === 0

                return isFirstCol ? (
                  <g key={`cell-${rowIdx}-${cellIdx}`}>
                    <rect
                      x={cellX - 4}
                      y={y + 11}
                      width={Math.min(colWidth - 12, 60)}
                      height={22}
                      rx="4"
                      fill="#074ce012"
                      stroke="#074ce030"
                      strokeWidth="1"
                    />
                    <text
                      x={cellX + 2}
                      y={y + 26}
                      fill="#074ce0"
                      fontSize="11"
                      fontWeight="700"
                      fontFamily="var(--font-body)"
                    >
                      {cellText}
                    </text>
                  </g>
                ) : (
                  <text
                    key={`cell-${rowIdx}-${cellIdx}`}
                    x={cellX}
                    y={y + 26}
                    fill={cellIdx === 1 ? '#16191f' : '#454c58'}
                    fontSize="13"
                    fontWeight={cellIdx === 1 ? '500' : '400'}
                    fontFamily="var(--font-body)"
                  >
                    {cellText.length > 32 ? `${cellText.slice(0, 30)}...` : cellText}
                  </text>
                )
              })}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
