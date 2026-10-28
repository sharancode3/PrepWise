import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Sparkles, X, Send, Trash2, ArrowUpRight, BookOpen, AlertCircle } from 'lucide-react'
import { useAssistant } from './useAssistant'
import type { AssistantSection, SuggestedAction } from './types'
import './assistant.css'

interface AskPrepWiseProps {
  currentTopicId?: string | null
  currentResourceId?: string | null
}

export function AskPrepWise({ currentTopicId, currentResourceId }: AskPrepWiseProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [inputValue, setInputValue] = useState('')
  const feedEndRef = useRef<HTMLDivElement>(null)

  // Derive initial section from route
  const getRouteSection = (): AssistantSection => {
    const path = location.pathname
    if (path.startsWith('/study')) return 'study'
    if (path.startsWith('/curriculum')) return 'resources'
    if (path.startsWith('/plan') || path.startsWith('/setup')) return 'my_plan'
    if (path.startsWith('/progress')) return 'progress'
    if (path.startsWith('/changes')) return 'changes'
    return 'study'
  }

  const {
    isOpen,
    openAssistant,
    closeAssistant,
    section,
    setSection,
    scopeDisplay,
    starterQuestions,
    messages,
    status,
    sendQuestion,
    clearChat,
  } = useAssistant({
    initialSection: getRouteSection(),
    topicId: currentTopicId,
    resourceId: currentResourceId,
  })

  // Synchronize section when route changes and user opens drawer
  useEffect(() => {
    setSection(getRouteSection())
  }, [location.pathname])

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        closeAssistant()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, closeAssistant])

  // Auto-scroll feed
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, status])

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!inputValue.trim() || status === 'loading') return
    const q = inputValue
    setInputValue('')
    sendQuestion(q)
  }

  const handleActionClick = (action: SuggestedAction) => {
    if (action.action_type === 'switch_scope' && action.payload) {
      setSection(action.payload as AssistantSection)
    } else if (action.path && action.path !== '#') {
      closeAssistant()
      navigate(action.path)
    }
  }

  return (
    <>
      {/* Floating Entry Point Trigger */}
      <button
        type="button"
        className="ask-prepwise-trigger"
        onClick={openAssistant}
        aria-label="Ask PrepWise assistant"
      >
        <Sparkles size={16} aria-hidden="true" />
        <span>Ask PrepWise</span>
      </button>

      {/* Slide-over Drawer Panel */}
      {isOpen && (
        <>
          <div
            className="assistant-backdrop"
            onClick={closeAssistant}
            aria-hidden="true"
          />
          <aside
            className="assistant-drawer"
            role="dialog"
            aria-label="PrepWise Assistant"
            aria-modal="true"
          >
            {/* Header */}
            <header className="assistant-header">
              <div className="assistant-header-top">
                <div className="assistant-title-group">
                  <h2 className="assistant-title">
                    <Sparkles size={18} color="var(--color-primary, #074ce0)" aria-hidden="true" />
                    Ask PrepWise
                  </h2>
                </div>
                <div className="assistant-actions">
                  {messages.length > 0 && (
                    <button
                      type="button"
                      className="assistant-icon-btn"
                      onClick={clearChat}
                      title="Clear chat"
                      aria-label="Clear chat"
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  )}
                  <button
                    type="button"
                    className="assistant-icon-btn"
                    onClick={closeAssistant}
                    title="Close assistant"
                    aria-label="Close assistant"
                  >
                    <X size={18} aria-hidden="true" />
                  </button>
                </div>
              </div>

              {/* Scope Bar */}
              <div className="assistant-scope-bar">
                <span className="assistant-scope-badge" title={scopeDisplay}>
                  <BookOpen size={12} aria-hidden="true" />
                  {scopeDisplay}
                </span>

                <select
                  className="assistant-scope-select"
                  value={section}
                  onChange={(e) => setSection(e.target.value as AssistantSection)}
                  aria-label="Select assistant scope"
                >
                  <option value="study">Study (Current Lesson)</option>
                  <option value="resources">Curriculum Documents</option>
                  <option value="my_plan">My Schedule & Goals</option>
                  <option value="progress">Progress & Evidence</option>
                  <option value="changes">Plan Comparisons</option>
                  <option value="general_learning">General Learning</option>
                </select>
              </div>
            </header>

            {/* Message Feed */}
            <div className="assistant-feed">
              {messages.length === 0 ? (
                <div className="assistant-empty">
                  <div className="assistant-empty-icon">
                    <Sparkles size={22} aria-hidden="true" />
                  </div>
                  <h3>Context-Aware Learning Support</h3>
                  <p>
                    I understand what you’re currently studying and retrieve supporting curriculum
                    material when you need it.
                  </p>

                  {starterQuestions.length > 0 && (
                    <div className="starter-chips-container">
                      {starterQuestions.map((q, idx) => (
                        <button
                          key={idx}
                          type="button"
                          className="starter-chip"
                          onClick={() => sendQuestion(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                messages.map((msg) => (
                  <div key={msg.id} className={`message-bubble ${msg.role}`}>
                    {msg.role === 'user' ? (
                      <div className="user-bubble-content">{msg.content}</div>
                    ) : (
                      <div className="assistant-bubble-content">
                        {msg.isPending ? (
                          <div className="assistant-pending-dots">
                            <span className="dot-pulse" />
                            <span>Thinking with local model...</span>
                          </div>
                        ) : (
                          <>
                            {msg.scopeUsed && (
                              <span className="assistant-bubble-scope">
                                Grounded in: {msg.scopeUsed}
                              </span>
                            )}
                            <div className="assistant-text">{msg.content}</div>

                            {/* Limitations callout */}
                            {msg.limitations && (
                              <div className="assistant-limitations-box">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                                  <AlertCircle size={13} aria-hidden="true" />
                                  <span>Scope Boundary</span>
                                </div>
                                <div>{msg.limitations}</div>
                              </div>
                            )}

                            {/* Reference cards */}
                            {msg.references && msg.references.length > 0 && (
                              <div className="assistant-references-card">
                                <span className="references-heading">Supporting Excerpts</span>
                                {msg.references.map((ref, i) => (
                                  <div key={i} className="reference-pill-item">
                                    <div className="reference-pill-header">
                                      <span>{ref.locator || ref.title}</span>
                                      {ref.link && (
                                        <button
                                          type="button"
                                          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                                          onClick={() => {
                                            closeAssistant()
                                            navigate(ref.link!)
                                          }}
                                          title="View reference"
                                        >
                                          <ArrowUpRight size={13} aria-hidden="true" />
                                        </button>
                                      )}
                                    </div>
                                    <div className="reference-pill-snippet">{ref.snippet}</div>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Suggested actions */}
                            {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                              <div className="assistant-actions-container">
                                {msg.suggestedActions.map((action, i) => (
                                  <button
                                    key={i}
                                    type="button"
                                    className="assistant-action-chip"
                                    onClick={() => handleActionClick(action)}
                                  >
                                    <span>{action.label}</span>
                                    <ArrowUpRight size={12} aria-hidden="true" />
                                  </button>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
              <div ref={feedEndRef} />
            </div>

            {/* Input Bar */}
            <footer className="assistant-footer">
              <form className="assistant-input-form" onSubmit={handleSubmit}>
                <input
                  type="text"
                  className="assistant-input-field"
                  placeholder="Ask a question about this lesson or plan..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  disabled={status === 'loading'}
                  aria-label="Ask a question"
                />
                <button
                  type="submit"
                  className="assistant-send-btn"
                  disabled={!inputValue.trim() || status === 'loading'}
                  aria-label="Send question"
                >
                  <Send size={15} aria-hidden="true" />
                </button>
              </form>
            </footer>
          </aside>
        </>
      )}
    </>
  )
}
