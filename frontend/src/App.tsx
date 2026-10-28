import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, Link } from 'react-router-dom'
import { ArrowUpRight, BookOpen } from 'lucide-react'
import { api } from './lib/api'
import { Home } from './features/home/Home'
import { Setup } from './features/planning/Setup'
import { PlanPage } from './features/planning/PlanPage'
import { CurriculumPage } from './features/curriculum/CurriculumPage'
import { FeaturePage } from './components/FeaturePage'

export function App() {
  const [online, setOnline] = useState<boolean | null>(null)
  useEffect(() => { let active = true; api('/health').then(() => { if (active) setOnline(true) }).catch(() => { if (active) setOnline(false) }); return () => { active = false } }, [])
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header container">
      <Link to="/" className="brand" aria-label="LearnNova home"><span className="brand-mark"><BookOpen size={19} aria-hidden="true" /></span>learnnova<span className="brand-dot">.</span></Link>
      <nav aria-label="Main navigation"><NavLink to="/curriculum">Curriculum</NavLink><NavLink to="/plan">My plan</NavLink><NavLink to="/progress">Progress</NavLink></nav>
      <Link to="/setup" className="header-action">Your workspace <ArrowUpRight size={16} aria-hidden="true" /></Link>
    </header>
    <main id="main" tabIndex={-1}><Routes>
      <Route path="/" element={<Home />} />
      <Route path="/setup" element={<Setup />} />
      <Route path="/curriculum" element={<CurriculumPage />} />
      <Route path="/plan" element={<PlanPage />} />
      <Route path="/study" element={<FeaturePage feature="Learning activities" title="Make every session meaningful." description="This feature will bring together focused activities, reviewed resources and clear learning objectives." owner="Member 1 · Activities" />} />
      <Route path="/progress" element={<FeaturePage feature="Progress and assessment" title="Understanding deserves evidence." description="Your completed sessions and independent checks will live here. No learning scores have been recorded by this foundation." owner="Member 4 · Progress" />} />
      <Route path="/changes" element={<FeaturePage feature="Plan comparison" title="See the reason behind every change." description="Compare saved plan versions and export your schedule once the planning and insights features are connected." owner="Member 5 · Insights" />} />
      <Route path="*" element={<FeaturePage feature="Page unavailable" title="Let’s get you back on track." description="This address isn’t part of your workspace." owner="Return to setup" />} />
    </Routes></main>
    <footer className="site-footer"><div className="container footer-inner"><Link to="/" className="footer-brand">learnnova.</Link><p>Built around your learning. One step at a time.</p><span className="connection"><span aria-hidden="true" className={online ? 'connection-dot connected' : 'connection-dot'} />{online === null ? 'Connecting to workspace' : online ? 'Local workspace connected' : 'Local server unavailable'}</span></div></footer>
  </>
}
