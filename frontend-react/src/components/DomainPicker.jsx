import Icon from './Icon';
import { workspaces } from '../workspaces';

export default function DomainPicker({ value, onChange, docs, disabled }) {
  return <section className="domain-section" aria-labelledby="domain-title">
    <div className="section-heading"><div><p className="eyebrow">ONE WORKSPACE. EVERY PERSPECTIVE.</p><h2 id="domain-title">What would you like to understand?</h2></div>
    <button className="text-button" disabled={disabled} aria-pressed={value === 'all'} onClick={() => onChange('all')}>All domains</button></div>
    <div className="domain-grid">{workspaces.map(w => <button key={w.id} style={{'--domain-color':w.color}} disabled={disabled} className={'domain-card '+(value===w.id?'active':'')} aria-pressed={value===w.id} onClick={() => onChange(w.id)}>
      <div className="domain-card-top"><span className="domain-icon"><Icon name={w.icon}/></span><span className="domain-count">{docs.filter(d => (d.domain||'property') === w.id).length} docs</span></div>
      <h3>{w.name}</h3><p>{w.description}</p><span className="domain-card-bottom">{w.label}<Icon name="arrow" size={15}/></span>
    </button>)}</div>
  </section>;
}
