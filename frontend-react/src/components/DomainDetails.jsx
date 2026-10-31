import { useState } from 'react';
import { api } from '../api';
import Icon from './Icon';

function Evidence({ item, onSource }) {
  return <><blockquote>{item.quote}</blockquote><button className="source-button" onClick={() => onSource(item.clause_index)}>Section {item.clause_index+1} · Page {item.page} <Icon name="arrow" size={14}/></button></>;
}

export function ResumeProfile({ profile, onSource }) {
  if (!profile) return null;
  return <section className="card domain-detail-card"><div className="section-heading"><Icon name="file"/><h2>Resume profile</h2></div>
    <div className="profile-contact">{['name','email','phone'].map(k=><div key={k}><span className="eyebrow">{k}</span>{profile[k]?.length ? profile[k].map((f,i)=><p key={i}>{f.value} <button className="text-button" onClick={()=>onSource(f.clause_index)}>Source</button></p>) : <p className="muted">Not extracted</p>}</div>)}</div>
    <h3>Skills</h3><div className="skill-tags">{profile.skills_clean.map(s=><span key={s}>{s}</span>)}</div>{!profile.skills_clean.length&&<p>No supported skills were extracted.</p>}
    <details><summary>Skill normalization and evidence</summary>{profile.skills_detail.map((s,i)=><div className="insight-item" key={i}><strong>{s.value} → {s.canonical}</strong><p className="muted small">{s.recognized?'Matched to the shared skill vocabulary':'Kept as written; outside the current vocabulary'}</p><Evidence item={s} onSource={onSource}/></div>)}</details>
    {[['experience','Experience'],['education','Education'],['project','Projects'],['certification','Certifications'],['achievement','Achievements'],['language','Languages']].map(([key,label])=><div key={key}><h3>{label}</h3>{profile[key]?.length?profile[key].map((f,i)=><article className="insight-item" key={i}><strong>{f.value}</strong><p>{f.detail}</p><Evidence item={f} onSource={onSource}/></article>):<p className="muted">No supported entries extracted.</p>}</div>)}
  </section>;
}

export function DomainInsights({ analysis:a, onSource }) {
  return <div className="domain-insights">
    {a.action_items?.length>0&&<section className="card domain-detail-card"><h2>Actions & stated deadlines</h2><p className="muted">Confirm dates and the responsible party against the original document.</p>{a.action_items.map((item,i)=><article className="insight-item" key={i}><h3>{item.action}</h3><p className="deadline-label">{item.deadline||'No deadline extracted for this action'}</p><Evidence item={item} onSource={onSource}/></article>)}</section>}
    {a.flagged_values?.length>0&&<section className="card domain-detail-card"><h2>Values to verify</h2><p className="muted">Document-reported values and ranges. These are not a diagnosis.</p>{a.flagged_values.map((item,i)=><article className="insight-item" key={i}><h3>{item.test_name}</h3><div className="value-pair"><p>Reported<strong>{item.reported_value}</strong></p><p>Printed range<strong>{item.normal_range}</strong></p></div><p>{item.why_flagged}</p><Evidence item={item} onSource={onSource}/></article>)}</section>}
    {!!a.unclear_items?.length&&<section className="card domain-detail-card"><h2>Unclear readings</h2><ul>{a.unclear_items.map((x,i)=><li key={i}>{x}</li>)}</ul></section>}
    <section className="card domain-detail-card"><h2>Questions to clarify</h2>{a.questions_to_ask?.length?<ul>{a.questions_to_ask.map((x,i)=><li key={i}>{x}</li>)}</ul>:<p>No additional questions were generated. Review the source and flags.</p>}
      {!!a.checklist?.length&&<><h3>Full-document checklist</h3><p className="muted small">Check where these topics are addressed. This list does not mean they are missing.</p><ul>{a.checklist.map(x=><li key={x}>{x}</li>)}</ul></>}
    </section>
    <section className="card domain-detail-card"><h2>Plain-language glossary</h2><p className="muted small">General vocabulary from the supplied domain guides; not a determination of how a term applies.</p>{a.glossary?.length?a.glossary.map(x=><article className="insight-item" key={x.term}><h3>{x.term}</h3><p>{x.meaning}</p></article>):<p>No terms from this domain’s glossary matched the extracted text.</p>}</section>
  </div>;
}

export function JobMatch({ doc }) {
  const [description,setDescription]=useState(''),[result,setResult]=useState(doc.job_match),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function match(e){e.preventDefault();if(busy)return;setBusy(true);setError('');try{setResult(await api.matchResume(doc.doc_id,description));}catch(e){setError(e.message);}finally{setBusy(false);}}
  function download(){const url=URL.createObjectURL(new Blob([JSON.stringify({resume_profile:doc.analysis.resume_profile,job_match:result},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='resume-profile-and-match.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <section className="card domain-detail-card job-match"><div className="section-heading"><div><p className="eyebrow">FROM YOUR RESUME TO THE ROLE</p><h2>Explore a job match</h2></div><button className="button secondary" onClick={download}><Icon name="download"/>Export JSON</button></div>
    <p>Compare the skills documented in your resume with a job description. This measures skill overlap, not your suitability or probability of being hired.</p>
    <form onSubmit={match}><label htmlFor="job-description">Job description</label><textarea id="job-description" value={description} onChange={e=>setDescription(e.target.value)} minLength={30} maxLength={6000} required rows={8} placeholder="Paste the role and its required and preferred skills…"/><div className="match-form-footer"><small>{description.length}/6,000 characters</small><button className="button primary" disabled={busy||description.trim().length<30}>{busy?'Comparing skills…':'Compare with resume'}<Icon name="arrow"/></button></div></form>
    {error&&<div className="error-box" role="alert">{error}</div>}{busy&&<p role="status">Reading the job requirements. API limits may add a short wait.</p>}
    {result&&<div className="match-results"><p className="eyebrow">LAST SAVED MATCH · {result.job_requirements.job_title||'ROLE NOT SPECIFIED'}</p><div className="match-score">{result.match.match_score===null?'—':result.match.match_score+'%'}<span>{result.match.match_score===null?'No required skills identified':'required-skill overlap'}</span></div><p className="muted small">{result.match.method}</p><div className="match-columns">{[['matched_skills','Found in resume'],['missing_skills','Not evidenced in resume'],['nice_to_have_matched','Preferred skills found'],['nice_to_have_missing','Preferred skills not evidenced']].map(([k,label])=><section key={k}><h3>{label}</h3><div className="skill-tags">{result.match[k].map(x=><span key={x}>{x}</span>)}</div>{!result.match[k].length&&<p className="muted">None</p>}</section>)}</div></div>}
  </section>;
}
