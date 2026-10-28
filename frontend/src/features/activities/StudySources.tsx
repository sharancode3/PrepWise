import React from 'react'
import { FileText, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { SourceReference } from './types'

interface StudySourcesProps {
  sources: SourceReference[]
}

export const StudySources: React.FC<StudySourcesProps> = ({ sources }) => {
  if (!sources || sources.length === 0) {
    return (
      <p style={{ fontSize: '14px', color: 'var(--dp-color-ink-secondary)' }}>
        No external curriculum sources cited.
      </p>
    )
  }

  return (
    <div className="study-sources-list">
      {sources.map((src) => (
        <div key={src.resource_id} className="study-source-card">
          <div className="study-source-label">
            <FileText size={15} style={{ color: 'var(--dp-color-accent)' }} aria-hidden="true" />
            <span>{src.source_label}</span>
            <span style={{ fontSize: '11px', color: 'var(--dp-color-ink-secondary)', marginLeft: 'auto' }}>
              ID: {src.resource_id}
            </span>
          </div>

          <div className="study-source-excerpt">
            "{src.relevant_excerpt}"
          </div>
        </div>
      ))}

      <div style={{ marginTop: '12px' }}>
        <Link
          to="/curriculum"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--dp-color-accent)',
          }}
        >
          View all curriculum resources <ExternalLink size={13} aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}
