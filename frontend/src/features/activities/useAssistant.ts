import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../lib/api'
import type {
  AssistantQuery,
  AssistantResponse,
  AssistantSection,
  ContextPack,
  ChatMessage,
  SuggestedAction,
} from './types'

export interface UIMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  scopeUsed?: string
  references?: Array<{
    title: string
    locator: string
    snippet: string
    reference_type: string
    link?: string | null
  }>
  limitations?: string | null
  suggestedActions?: SuggestedAction[]
  isPending?: boolean
}

interface UseAssistantOptions {
  initialSection?: AssistantSection
  topicId?: string | null
  resourceId?: string | null
  goalId?: string | null
  planId?: string | null
}

export function useAssistant(options: UseAssistantOptions = {}) {
  const [isOpen, setIsOpen] = useState(false)
  const [section, setSectionState] = useState<AssistantSection>(options.initialSection || 'study')
  const [scopeDisplay, setScopeDisplay] = useState<string>('PrepWise Assistant')
  const [starterQuestions, setStarterQuestions] = useState<string[]>([])
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  const activeTopicId = options.topicId || null
  const activeResourceId = options.resourceId || null
  const activeGoalId = options.goalId || null
  const activePlanId = options.planId || null

  const messagesRef = useRef(messages)
  messagesRef.current = messages

  // Load context facts & starter questions whenever section or topic changes
  const loadContext = useCallback(async (sec: AssistantSection) => {
    try {
      const params = new URLSearchParams()
      params.set('section', sec)
      if (activeTopicId) params.set('topic_id', activeTopicId)
      if (activeResourceId) params.set('resource_id', activeResourceId)
      if (activeGoalId) params.set('goal_id', activeGoalId)
      if (activePlanId) params.set('plan_id', activePlanId)

      const pack = await api<ContextPack>(`/assistant/context?${params.toString()}`)
      setScopeDisplay(pack.scope_display)
      setStarterQuestions(pack.starter_questions || [])
    } catch {
      setScopeDisplay(sec === 'general_learning' ? 'General Learning' : 'PrepWise Assistant')
    }
  }, [activeTopicId, activeResourceId, activeGoalId, activePlanId])

  useEffect(() => {
    if (isOpen) {
      loadContext(section)
    }
  }, [isOpen, section, loadContext])

  const setSection = useCallback((newSection: AssistantSection) => {
    setSectionState(newSection)
    loadContext(newSection)
  }, [loadContext])

  const sendQuestion = useCallback(async (questionText: string) => {
    const text = questionText.trim()
    if (!text || status === 'loading') return

    const userMsgId = 'msg-' + Date.now()
    const assistantMsgId = 'asst-' + (Date.now() + 1)

    const userMessage: UIMessage = {
      id: userMsgId,
      role: 'user',
      content: text,
    }

    const pendingAssistantMessage: UIMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isPending: true,
    }

    setMessages((prev) => [...prev, userMessage, pendingAssistantMessage])
    setStatus('loading')
    setError(null)

    // Build short bounded history
    const history: ChatMessage[] = messagesRef.current
      .filter((m) => !m.isPending && m.content)
      .slice(-4)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))

    const payload: AssistantQuery = {
      question: text,
      section: section,
      topic_id: activeTopicId || undefined,
      resource_id: activeResourceId || undefined,
      goal_id: activeGoalId || undefined,
      plan_id: activePlanId || undefined,
      history,
    }

    try {
      const response = await api<AssistantResponse>('/assistant/query', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: response.answer,
                scopeUsed: response.scope_used,
                references: response.references as any,
                limitations: response.limitations,
                suggestedActions: response.suggested_actions,
                isPending: false,
              }
            : msg
        )
      )
      setStatus('idle')
    } catch (err: any) {
      const fallbackMsg = 'The assistant was unable to process your request. Please try again.'
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: fallbackMsg,
                limitations: err.message || 'Connection failure',
                isPending: false,
              }
            : msg
        )
      )
      setError(err.message || fallbackMsg)
      setStatus('error')
    }
  }, [status, section, activeTopicId, activeResourceId, activeGoalId, activePlanId])

  const clearChat = useCallback(async () => {
    setMessages([])
    setError(null)
    setStatus('idle')
    try {
      await api('/assistant/clear', { method: 'POST' })
    } catch {
      // ignore
    }
  }, [])

  return {
    isOpen,
    openAssistant: () => setIsOpen(true),
    closeAssistant: () => setIsOpen(false),
    toggleAssistant: () => setIsOpen((prev) => !prev),
    section,
    setSection,
    scopeDisplay,
    starterQuestions,
    messages,
    status,
    error,
    sendQuestion,
    clearChat,
  }
}
