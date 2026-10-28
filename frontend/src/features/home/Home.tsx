import { BookOpen, Clock3, Target, ArrowRight, Layers3, Check, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ActionLink, Button, Eyebrow } from '../../components/ui'
import demoState from '../../demoState.json'

export function Home() {
  const navigate = useNavigate()
  const activeGoal = localStorage.getItem('learnnova.goal-id')

  const handleLoadDemo = () => {
    localStorage.setItem('learnnova.token', demoState.token)
    localStorage.setItem('learnnova.goal-id', demoState.goalId)
    localStorage.setItem('learnnova.demo.active_project.v2', demoState.projectId)
    navigate('/plan')
  }

  return <>
    <section className="container hero">
      <div className="hero-copy">
        <Eyebrow>A little structure. A clearer direction.</Eyebrow>
        <h1>Make room<br />for <span>what’s next.</span></h1>
        <p>A study plan shaped around your curriculum, your time, and the way you’re progressing.</p>
        <div className="hero-actions" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          {activeGoal ? (
            <ActionLink to="/plan">Continue your study plan</ActionLink>
          ) : (
            <ActionLink to="/setup">Start with your goal</ActionLink>
          )}
          <Button variant="secondary" onClick={handleLoadDemo} title="Load Alex's Programming Foundations assessment scenario">
            <Sparkles size={15} aria-hidden="true" />
            Open demo workspace
          </Button>
          <a href="#how-it-works" className="text-link">See how it works <ArrowRight size={16} aria-hidden="true" /></a>
        </div>
        <div className="hero-note"><span className="small-rule" />Your learning, with a little more intention.</div>
      </div>
      <div className="product-diagram" aria-label="Your curriculum, available time and learning goals come together in a personal study plan">
        <div className="diagram-grid" aria-hidden="true" /><div className="diagram-label">A plan that connects the dots</div>
        <div className="input-tile tile-one"><BookOpen size={17} aria-hidden="true" /><span>Your curriculum</span><span className="tile-plus" aria-hidden="true">+</span></div>
        <div className="input-tile tile-two"><Clock3 size={17} aria-hidden="true" /><span>Your available time</span><span className="tile-plus" aria-hidden="true">+</span></div>
        <div className="input-tile tile-three"><Target size={17} aria-hidden="true" /><span>Your learning goals</span><span className="tile-plus" aria-hidden="true">+</span></div>
        <div className="diagram-connector" aria-hidden="true" />
        <div className="plan-tile"><div className="plan-tile-top"><span className="diagram-symbol"><Layers3 size={22} aria-hidden="true" /></span><span>Made for your next step</span></div><h2>A little clarity.<br />Every day.</h2><div className="diagram-divider" /><div className="diagram-check"><Check size={15} aria-hidden="true" />A focused learning path</div><div className="diagram-check"><Check size={15} aria-hidden="true" />Room for real life</div></div>
        <div className="diagram-footnote">Curriculum → priorities → a practical plan</div>
      </div>
    </section>
    <div className="container principle-strip"><span><span>01</span> Grounded in your curriculum</span><span><span>02</span> Built around your time</span><span><span>03</span> Designed to adapt</span></div>
    <section className="muted-section"><div className="container"><div className="section-heading"><Eyebrow>A thoughtful starting point</Eyebrow><h2>Less figuring out.<br />More moving forward.</h2><p>Bring the essentials. Give every study session a clear purpose.</p></div><div className="feature-grid">{[{Icon:BookOpen,title:'Know where to begin.',text:'Start from a clear curriculum, with the foundations connected to what comes next.'},{Icon:Clock3,title:'Make the time count.',text:'Tell us the time you actually have. A useful plan starts with a realistic day.'},{Icon:Target,title:'Keep your goal in view.',text:'Choose what matters to you, with a path that can evolve as you learn.'}].map(({Icon,title,text})=><article key={title}><span className="icon-tile"><Icon size={23} aria-hidden="true" /></span><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>
    <section className="dark-section" id="how-it-works"><div className="container"><Eyebrow>From intention to a next step</Eyebrow><h2>Good learning has a rhythm.</h2><div className="process-grid">{[['01','Set your direction','Choose a curriculum, your goals and the time you have.'],['02','Follow a focused plan','Give each session a topic, a purpose and a realistic allocation.'],['03','Reflect and adjust','Use progress and independent checks to guide the next plan.']].map(([n,title,text])=><article key={n}><span className="step-number">{n}</span><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>
    <section className="container closing-section"><div><Eyebrow>Begin with what you know</Eyebrow><h2>Your next chapter<br />starts with a small step.</h2><p>Your profile and study goals are saved in your local workspace. Explore your personalized schedule, interactive study sessions, and progress tracking.</p></div>{activeGoal ? <ActionLink to="/plan">View your study plan</ActionLink> : <ActionLink to="/setup">Set up your workspace</ActionLink>}</section>
  </>
}
