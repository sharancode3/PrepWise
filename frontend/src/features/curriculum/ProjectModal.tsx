import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { X } from 'lucide-react'
import { Button } from '../../components/ui'

interface ProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (title: string, description: string) => Promise<void>
}

export function ProjectModal({ isOpen, onClose, onSubmit }: ProjectModalProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isOpen) return

    setTitle('')
    setDescription('')
    setError('')
    setSaving(false)
    const timer = setTimeout(() => inputRef.current?.focus(), 50)

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !saving) {
        e.preventDefault()
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      clearTimeout(timer)
    }
  }, [isOpen, onClose, saving])

  if (!isOpen) return null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const cleanTitle = title.trim()
    if (!cleanTitle) {
      setError('Please enter a project title.')
      return
    }
    setError('')
    setSaving(true)
    try {
      await onSubmit(cleanTitle, description)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create project.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-project-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose()
      }}
    >
      <div className="modal-content">
        <div className="modal-header">
          <h3 id="new-project-title">Create project</h3>
          <button
            type="button"
            className="close-btn"
            onClick={onClose}
            aria-label="Close dialog"
            disabled={saving}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="notice" role="alert" style={{ marginBottom: 16 }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label htmlFor="project-name-input" style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>
              Project name
            </label>
            <input
              id="project-name-input"
              ref={inputRef}
              type="text"
              required
              maxLength={120}
              placeholder="For example, Python Fundamentals"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 6,
                border: '1px solid var(--dp-color-rule)',
                fontSize: 15,
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label htmlFor="project-desc-input" style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>
              Description <span style={{ fontWeight: 400, color: 'var(--dp-color-ink-secondary)' }}>(optional)</span>
            </label>
            <textarea
              id="project-desc-input"
              rows={3}
              maxLength={500}
              placeholder="What are you aiming to learn or prepare for?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 6,
                border: '1px solid var(--dp-color-rule)',
                fontSize: 15,
                boxSizing: 'border-box',
                fontFamily: 'inherit',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Creating project…' : 'Create project'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
