import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  FileCode,
  FileText,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react'
import { Button } from '../../components/ui'
import { liveCurriculumService } from './liveService'
import { mockCurriculumService } from './mockService'
import type { BatchUploadResult, CurriculumTopic, ResourceItem } from './types'

interface ResourcesViewProps {
  resources: ResourceItem[]
  topics: CurriculumTopic[]
  onUploadBatch: (files: File[], topicId: string) => Promise<BatchUploadResult>
  onRemoveResource: (resourceId: string) => Promise<void>
  onNavigateToPlan?: () => void
}

export function CurriculumResourcesView({
  resources,
  topics,
  onUploadBatch,
  onRemoveResource,
  onNavigateToPlan,
}: ResourcesViewProps) {
  const [selectedTopic, setSelectedTopic] = useState<string>(topics[0]?.id ?? 'variables')
  const [addingFiles, setAddingFiles] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchUploadResult | null>(null)
  const [previewResource, setPreviewResource] = useState<ResourceItem | null>(null)
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Manage temporary PDF object URL lifecycle and keyboard modal dismiss
  useEffect(() => {
    if (previewResource?.previewType === 'local-pdf') {
      const file = mockCurriculumService.getInMemoryFile(previewResource.id)
      if (file) {
        const url = URL.createObjectURL(file)
        setPdfBlobUrl(url)
        return () => {
          URL.revokeObjectURL(url)
          setPdfBlobUrl(null)
        }
      }
    } else {
      setPdfBlobUrl(null)
    }

    if (!previewResource) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        setPreviewResource(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [previewResource])

  async function handleProcessFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    const filesArray = Array.from(fileList)

    setAddingFiles(true)
    setBatchResult(null)
    try {
      const result = await onUploadBatch(filesArray, selectedTopic)
      setBatchResult(result)
    } finally {
      setAddingFiles(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    handleProcessFiles(e.target.files)
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)
    handleProcessFiles(e.dataTransfer.files)
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(true)
  }

  function handleDragLeave() {
    setIsDragOver(false)
  }

  async function openPreview(res: ResourceItem) {
    // Fetch detailed content for this resource
    try {
      const detail = await liveCurriculumService.getResourceDetail(res.id)
      setPreviewResource(detail)
    } catch {
      setPreviewResource(res)
    }
  }

  return (
    <div className="curriculum-resources-view">
      {/* 1. Resource Addition Studio (Local Files) */}
      <div className="section-card">
        <h2>Add study resources</h2>
        <p className="section-desc">
          Select course texts or personal notes (.pdf, .md, .txt) from your device. Files are kept locally in memory for this prototype session and are not sent to a remote server.
        </p>

        <div style={{ marginBottom: 16 }}>
          <label htmlFor="topic-assign-select" style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>
            Associate with topic
          </label>
          <select
            id="topic-assign-select"
            value={selectedTopic}
            onChange={(e) => setSelectedTopic(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid var(--dp-color-rule)',
              fontSize: 14,
              minWidth: 240,
            }}
          >
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        </div>

        <div
          className={`dropzone ${isDragOver ? 'drag-over' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Drop files here or press Enter to browse files from your computer"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              fileInputRef.current?.click()
            }
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.md,.txt,.markdown"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <UploadCloud size={34} className="dropzone-icon" aria-hidden="true" />
          <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--dp-color-ink)' }}>
            {addingFiles ? 'Processing local files…' : 'Drag and drop study files here, or click to browse'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--dp-color-ink-secondary)', marginTop: 4 }}>
            Supported formats: PDF, Markdown (.md), Plain Text (.txt) · Max 10 MB per file
          </div>
          <div style={{ marginTop: 12 }}>
            <Button
              type="button"
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation()
                fileInputRef.current?.click()
              }}
            >
              Browse files
            </Button>
          </div>
        </div>

        {/* Batch Validation & Feedback Results */}
        {batchResult && (
          <div
            style={{
              marginTop: 14,
              padding: '12px 16px',
              borderRadius: 8,
              background: 'var(--dp-color-ground-muted)',
              border: '1px solid var(--dp-color-rule)',
              fontSize: 14,
            }}
          >
            {batchResult.added.length > 0 && (
              <div style={{ color: '#1a7f37', marginBottom: batchResult.skipped.length > 0 ? 8 : 0 }}>
                <CheckCircle2 size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" />
                <strong>Added {batchResult.added.length} file(s) locally: </strong>
                {batchResult.added.map((f) => `${f.filename} (${(f.byteSize / 1024).toFixed(1)} KB)`).join(', ')}
              </div>
            )}

            {batchResult.added.length > 0 && onNavigateToPlan && (
              <div style={{ marginTop: 12 }}>
                <Button onClick={onNavigateToPlan}>
                  Next: choose what to study →
                </Button>
              </div>
            )}

            {batchResult.skipped.map((s, idx) => (
              <div key={idx} style={{ color: '#c93b2b', marginTop: 4 }}>
                <AlertCircle size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" />
                <strong>{s.filename}:</strong> {s.reason}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Resource Library */}
      <div className="section-card">
        <h2>Resource library</h2>
        <p className="section-desc">
          Study materials linked to this project. Previews display prewritten sample text for course resources or safely rendered local text for uploaded notes.
        </p>

        {resources.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--dp-color-ink-secondary)' }}>
            No resources selected for this project. Use the area above to add local files.
          </div>
        ) : (
          <>
            <div className="resource-list">
              {resources.map((res) => (
                <div key={res.id} className="resource-card">
                  <div className="resource-info">
                    <div className="resource-icon-box">
                      {res.filename.endsWith('.md') ? (
                        <FileCode size={20} aria-hidden="true" />
                      ) : (
                        <FileText size={20} aria-hidden="true" />
                      )}
                    </div>
                    <div>
                      <div className="resource-title">{res.title}</div>
                      <div className="resource-tags">
                        <span className={`source-badge ${res.kind === 'bundled' ? 'badge-sample' : 'badge-local'}`}>
                          {res.kind === 'bundled' ? 'Sample resource' : 'Local file'}
                        </span>
                        <span>{(res.byteSize / 1024).toFixed(1)} KB</span>
                        <span>·</span>
                        <span style={{ color: 'var(--dp-color-ink-secondary)' }}>
                          {res.previewType === 'bundled-text' && 'Sample text preview'}
                          {res.previewType === 'local-text' && 'Text preview'}
                          {res.previewType === 'local-pdf' && 'PDF preview'}
                          {res.previewType === 'unavailable' && 'Re-selection needed'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="resource-actions">
                    <Button variant="secondary" onClick={() => openPreview(res)}>
                      <Eye size={15} aria-hidden="true" /> Preview
                    </Button>

                    {res.kind === 'local' && (
                      <button
                        type="button"
                        onClick={() => onRemoveResource(res.id)}
                        className="close-btn"
                        title={`Remove ${res.title} from this project`}
                        aria-label={`Remove ${res.title} from this project`}
                      >
                        <Trash2 size={16} color="#c93b2b" aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {onNavigateToPlan && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--dp-color-rule)' }}>
                <Button onClick={onNavigateToPlan}>
                  Next: choose what to study →
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* 3. Document Preview Modal */}
      {previewResource && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="preview-modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setPreviewResource(null)
          }}
        >
          <div className="modal-content" style={{ maxWidth: 720 }}>
            <div className="modal-header">
              <div>
                <h3 id="preview-modal-title" style={{ margin: 0 }}>
                  {previewResource.title}
                </h3>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <span className="source-badge">
                    {previewResource.kind === 'bundled' ? 'Sample resource' : 'Local file'}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)' }}>
                    {(previewResource.byteSize / 1024).toFixed(1)} KB
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="close-btn"
                onClick={() => setPreviewResource(null)}
                aria-label="Close preview dialog"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>

            {/* Bundled sections or topic link */}
            {previewResource.sections && previewResource.sections.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <strong style={{ fontSize: 13 }}>Sample sections:</strong>
                <ul style={{ margin: '4px 0 0 18px', padding: 0, fontSize: 13, color: 'var(--dp-color-ink-secondary)' }}>
                  {previewResource.sections.map((sec, idx) => (
                    <li key={idx}>
                      {sec.title} {sec.pageNumber ? `(Page ${sec.pageNumber})` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Preview Body Renderer */}
            <div style={{ marginTop: 8 }}>
              {previewResource.previewType === 'unavailable' ? (
                <div style={{ padding: '24px 16px', background: '#fff9f0', border: '1px solid #fed8a5', borderRadius: 8, color: '#7a3e00', fontSize: 14 }}>
                  <strong>Local preview unavailable:</strong> {previewResource.previewNotice}
                </div>
              ) : previewResource.previewType === 'local-pdf' && pdfBlobUrl ? (
                <div>
                  <div style={{ fontSize: 12, color: 'var(--dp-color-ink-secondary)', marginBottom: 8 }}>
                    Rendered via your browser's local document viewer. No remote processing or extraction was performed.
                  </div>
                  <object
                    data={pdfBlobUrl}
                    type="application/pdf"
                    width="100%"
                    height="420px"
                    style={{ borderRadius: 8, border: '1px solid var(--dp-color-rule)' }}
                  >
                    <p style={{ padding: 16 }}>
                      Your browser cannot display embedded PDFs directly.{' '}
                      <a href={pdfBlobUrl} target="_blank" rel="noreferrer" className="text-link">
                        Open PDF in a new tab
                      </a>.
                    </p>
                  </object>
                </div>
              ) : previewResource.fullText ? (
                <pre
                  className="preview-body"
                  style={{
                    fontFamily: 'inherit',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {previewResource.fullText}
                </pre>
              ) : (
                <div className="preview-body">{previewResource.snippet}</div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
              <Button variant="secondary" onClick={() => setPreviewResource(null)}>
                Close preview
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
