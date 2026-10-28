import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, Link, useLocation } from 'react-router-dom'
import {
  ArrowUpRight,
  Award,
  BookOpen,
  Calendar,
  GitCompare,
  GraduationCap,
  Home as HomeIcon,
  Menu,
  Sparkles,
  Target,
  X,
} from 'lucide-react'
import { api } from './lib/api'
import { Home } from './features/home/Home'
import { Setup } from './features/planning/Setup'
import { CurriculumPage } from './features/curriculum/CurriculumPage'
import { StudyPage, AskPrepWise } from './features/activities'
import { ChangesPage } from './features/insights'
import { ProgressPage } from './features/progress'
import { PlanPage } from './features/planning/PlanPage'
import { FeaturePage } from './components/FeaturePage'
import './styles/sidebar.css'

export function App() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeGoalId, setActiveGoalId] = useState<string | null>(() => localStorage.getItem('learnnova.goal-id'))
  const location = useLocation()

  // Track health
  useEffect(() => {
    let active = true
    api('/health')
      .then(() => {
        if (active) setOnline(true)
      })
      .catch(() => {
        if (active) setOnline(false)
      })
    return () => {
      active = false
    }
  }, [])

  // Sync active goal from storage & close mobile drawer on route transition
  useEffect(() => {
    setMobileOpen(false)
    const stored = localStorage.getItem('learnnova.goal-id')
    if (stored !== activeGoalId) {
      setActiveGoalId(stored)
    }
  }, [location.pathname])

  // Close mobile drawer on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileOpen) {
        setMobileOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [mobileOpen])

  // Compute view label for the compact desktop topbar
  const getViewTitle = () => {
    const p = location.pathname
    if (p === '/') return 'Home'
    if (p.startsWith('/setup')) return 'Goals & Availability'
    if (p.startsWith('/curriculum')) return 'Curriculum Resources'
    if (p.startsWith('/plan')) return 'My Study Plan'
    if (p.startsWith('/study')) return 'Study Experience'
    if (p.startsWith('/progress')) return 'Progress & Assessment'
    if (p.startsWith('/changes')) return 'Plan Comparison & Export'
    return 'Learning Workspace'
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <div className="app-layout">
        {/* Desktop Persistent Left Sidebar */}
        <aside className="app-sidebar" aria-label="Workspace navigation">
          <div className="sidebar-brand-wrapper">
            <Link to="/" className="brand" aria-label="PrepWise home">
              <span className="brand-mark">
                <BookOpen size={19} aria-hidden="true" />
              </span>
              prepwise<span className="brand-dot">.</span>
            </Link>
            <div className="sidebar-goal-badge">
              <span className="sidebar-goal-dot" aria-hidden="true" />
              <span>{activeGoalId ? 'Goal in progress' : 'No active goal'}</span>
            </div>
          </div>

          <nav className="sidebar-nav-section" aria-label="Main navigation">
            <div className="sidebar-section-label">Learning Workspace</div>
            <NavLink
              to="/"
              end
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <HomeIcon size={17} aria-hidden="true" />
              <span>Home</span>
            </NavLink>
            <NavLink
              to="/setup"
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <Target size={17} aria-hidden="true" />
              <span>Goals & availability</span>
            </NavLink>
            <NavLink
              to="/curriculum"
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <BookOpen size={17} aria-hidden="true" />
              <span>Resources</span>
            </NavLink>
            <NavLink
              to="/plan"
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <Calendar size={17} aria-hidden="true" />
              <span>My Plan</span>
            </NavLink>
            <NavLink
              to="/study"
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <GraduationCap size={17} aria-hidden="true" />
              <span>Study</span>
            </NavLink>
            <NavLink
              to="/progress"
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <Award size={17} aria-hidden="true" />
              <span>Progress</span>
            </NavLink>
            <NavLink
              to="/changes"
              className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
            >
              <GitCompare size={17} aria-hidden="true" />
              <span>Changes & export</span>
            </NavLink>
          </nav>

          <div className="sidebar-footer">
            <span className="connection">
              <span
                aria-hidden="true"
                className={online ? 'connection-dot connected' : 'connection-dot'}
              />
              {online === null
                ? 'Connecting to workspace'
                : online
                ? 'Local workspace connected'
                : 'Local server unavailable'}
            </span>
          </div>
        </aside>

        {/* Accessible Mobile Drawer */}
        {mobileOpen && (
          <div
            className="mobile-drawer-backdrop"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
        )}
        {mobileOpen && (
          <div
            className="mobile-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Mobile navigation"
          >
            <div className="mobile-drawer-header">
              <Link to="/" className="brand" onClick={() => setMobileOpen(false)}>
                <span className="brand-mark">
                  <BookOpen size={18} aria-hidden="true" />
                </span>
                prepwise<span className="brand-dot">.</span>
              </Link>
              <button
                type="button"
                className="mobile-menu-btn"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
              >
                <X size={22} aria-hidden="true" />
              </button>
            </div>

            <nav className="sidebar-nav-section" aria-label="Mobile navigation menu">
              <div className="sidebar-section-label">Learning Workspace</div>
              <NavLink
                to="/"
                end
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <HomeIcon size={17} aria-hidden="true" />
                <span>Home</span>
              </NavLink>
              <NavLink
                to="/setup"
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <Target size={17} aria-hidden="true" />
                <span>Goals & availability</span>
              </NavLink>
              <NavLink
                to="/curriculum"
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <BookOpen size={17} aria-hidden="true" />
                <span>Resources</span>
              </NavLink>
              <NavLink
                to="/plan"
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <Calendar size={17} aria-hidden="true" />
                <span>My Plan</span>
              </NavLink>
              <NavLink
                to="/study"
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <GraduationCap size={17} aria-hidden="true" />
                <span>Study</span>
              </NavLink>
              <NavLink
                to="/progress"
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <Award size={17} aria-hidden="true" />
                <span>Progress</span>
              </NavLink>
              <NavLink
                to="/changes"
                className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <GitCompare size={17} aria-hidden="true" />
                <span>Changes & export</span>
              </NavLink>
            </nav>
          </div>
        )}

        {/* Main Content Area */}
        <div className="app-content-wrapper">
          {/* Mobile Header Bar */}
          <header className="mobile-topbar" aria-label="Mobile header">
            <button
              type="button"
              className="mobile-menu-btn"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation menu"
              aria-expanded={mobileOpen}
            >
              <Menu size={22} aria-hidden="true" />
            </button>
            <Link to="/" className="brand" aria-label="PrepWise home">
              <span className="brand-mark">
                <BookOpen size={18} aria-hidden="true" />
              </span>
              prepwise<span className="brand-dot">.</span>
            </Link>
            <Link to="/plan" className="header-action" style={{ fontSize: '13px' }}>
              Plan <ArrowUpRight size={14} aria-hidden="true" />
            </Link>
          </header>

          {/* Desktop compact view topbar */}
          <div className="app-topbar">
            <div className="app-topbar-title">
              <span>{getViewTitle()}</span>
            </div>
            <div className="app-topbar-actions">
              {activeGoalId ? (
                <Link to="/plan" className="header-action" title="View scheduled plan for active goal">
                  Active goal <ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              ) : (
                <Link to="/setup" className="header-action">
                  Set goal <ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              )}
            </div>
          </div>

          <main id="main" tabIndex={-1} style={{ flex: 1 }}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/setup" element={<Setup />} />
              <Route path="/curriculum" element={<CurriculumPage />} />
              <Route path="/plan" element={<PlanPage />} />
              <Route path="/study" element={<StudyPage />} />
              <Route path="/progress" element={<ProgressPage />} />
              <Route path="/changes" element={<ChangesPage />} />
              <Route
                path="*"
                element={
                  <FeaturePage
                    feature="Page unavailable"
                    title="Let’s get you back on track."
                    description="This address isn’t part of your workspace."
                    owner="Return to setup"
                  />
                }
              />
            </Routes>
          </main>

          <footer className="site-footer">
            <div className="container footer-inner">
              <Link to="/" className="footer-brand">
                prepwise.
              </Link>
              <p>Built around your learning. One step at a time.</p>
              <span className="connection">
                <span
                  aria-hidden="true"
                  className={online ? 'connection-dot connected' : 'connection-dot'}
                />
                {online === null
                  ? 'Connecting to workspace'
                  : online
                  ? 'Local workspace connected'
                  : 'Local server unavailable'}
              </span>
            </div>
          </footer>
        </div>
      </div>

      <AskPrepWise />
    </>
  )
}
