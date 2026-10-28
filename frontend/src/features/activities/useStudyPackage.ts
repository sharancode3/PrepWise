import { useState, useEffect, useCallback, useRef } from 'react'
import { api, ApiError } from '../../lib/api'
import type { StudyPackage, SupportMode } from './types'

export function useStudyPackage(initialMode: SupportMode = 'normal', topicId?: string | null) {
  const [pkg, setPkg] = useState<StudyPackage | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [generatingMode, setGeneratingMode] = useState<SupportMode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentMode, setCurrentMode] = useState<SupportMode>(initialMode)
  const [revealedHintsCount, setRevealedHintsCount] = useState<number>(0)
  const [showSolution, setShowSolution] = useState<boolean>(false)
  const [activeSection, setActiveSection] = useState<string>('overview')
  const [statusAnnouncement, setStatusAnnouncement] = useState<string>('')

  const activeRequestRef = useRef<number>(0)
  const pkgRef = useRef<StudyPackage | null>(null)
  pkgRef.current = pkg

  const fetchPackage = useCallback(
    async (modeToFetch: SupportMode = 'normal', requestedTopicId: string | null = topicId || null) => {
      const requestId = ++activeRequestRef.current
      setError(null)

      if (pkgRef.current) {
        setGeneratingMode(modeToFetch)
        setStatusAnnouncement(`Generating ${modeToFetch} explanation locally...`)
      } else {
        setLoading(true)
        setStatusAnnouncement('Loading study package...')
      }

      try {
        const queryParams = new URLSearchParams()
        queryParams.set('mode', modeToFetch)
        if (requestedTopicId) {
          queryParams.set('topic_id', requestedTopicId)
        }

        const data = await api<StudyPackage>(`/study/sample?${queryParams.toString()}`)

        // Discard stale responses
        if (requestId !== activeRequestRef.current) return

        setPkg(data)
        setCurrentMode(modeToFetch)
        setRevealedHintsCount(0)
        setShowSolution(false)
        setStatusAnnouncement(`Loaded ${data.title} (${data.provenance.origin})`)
      } catch (err: unknown) {
        if (requestId !== activeRequestRef.current) return
        const msg = err instanceof ApiError ? err.message : 'Unable to connect to study engine.'
        setError(msg)
        setStatusAnnouncement(`Error: ${msg}`)
      } finally {
        if (requestId === activeRequestRef.current) {
          setLoading(false)
          setGeneratingMode(null)
        }
      }
    },
    [topicId]
  )

  useEffect(() => {
    fetchPackage(initialMode, topicId)
    return () => {
      activeRequestRef.current++
    }
  }, [fetchPackage, initialMode, topicId])

  const revealNextHint = useCallback(() => {
    if (!pkgRef.current) return
    const total = pkgRef.current.hints.length
    setRevealedHintsCount((prev) => {
      const next = Math.min(prev + 1, total)
      setStatusAnnouncement(`Revealed hint ${next} of ${total}`)
      return next
    })
  }, [])

  const toggleSolution = useCallback(() => {
    setShowSolution((prev) => {
      const next = !prev
      setStatusAnnouncement(next ? 'Solution revealed' : 'Solution hidden')
      return next
    })
  }, [])

  const requestMode = useCallback(
    (newMode: SupportMode) => {
      if (generatingMode !== null) return
      fetchPackage(newMode, topicId)
    },
    [generatingMode, fetchPackage, topicId]
  )

  const scrollToSection = useCallback((sectionId: string) => {
    setActiveSection(sectionId)
    const el = document.getElementById(sectionId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [])

  return {
    pkg,
    loading,
    generatingMode,
    error,
    currentMode,
    revealedHintsCount,
    showSolution,
    activeSection,
    statusAnnouncement,
    fetchPackage,
    revealNextHint,
    toggleSolution,
    requestMode,
    scrollToSection,
  }
}
