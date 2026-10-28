import { ArrowUpRight, Layers3 } from 'lucide-react'
import { ActionLink, Eyebrow, Notice, Panel } from './ui'

export function FeaturePage({
  feature,
  title,
  description,
  owner,
  secondaryAction,
}: {
  feature: string
  title: string
  description: string
  owner: string
  secondaryAction?: { to: string; label: string }
}) {
  return (
    <section className="container page-section">
      <Eyebrow>{feature}</Eyebrow>
      <h1 className="page-title">{title}</h1>
      <p className="page-intro">{description}</p>
      <Panel className="empty-state">
        <span className="icon-tile">
          <Layers3 size={26} aria-hidden="true" />
        </span>
        <h2>A space ready to build on.</h2>
        <p>The shared foundation is ready. This feature is assigned to its implementation owner.</p>
        <Notice>{owner} · Feature implementation pending</Notice>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', marginTop: '16px' }}>
          <ActionLink to="/setup">Set up your learning</ActionLink>
          {secondaryAction && (
            <ActionLink to={secondaryAction.to} secondary>
              {secondaryAction.label}
            </ActionLink>
          )}
        </div>
      </Panel>
      <a className="text-link" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
        API reference <ArrowUpRight size={15} aria-hidden="true" />
      </a>
    </section>
  )
}
