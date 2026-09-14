import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import Icon from "./Icon";
import SourceReview from "./SourceReview";
import ChatPanel from "./ChatPanel";
import RiskList from "./RiskList";

const names={summary:"Overview",risks:"Risk flags",clauses:"Source text",chat:"Ask a question"};
export default function DocumentView({docId,onReady,onDelete,onBack}){
  const [doc,setDoc]=useState(null),[tab,setTab]=useState("summary"),[error,setError]=useState("");
  const [selected,setSelected]=useState(null),[reload,setReload]=useState(0),[retrying,setRetrying]=useState(false);
  const [editing,setEditing]=useState(false);
  const sourceRef=useRef(null);
  useEffect(()=>{
    let alive=true,timer;
    async function poll(){
      try{const next=await api.getDocument(docId);if(!alive)return;setDoc(next);setError("");
        if(["queued","processing"].includes(next.status))timer=setTimeout(poll,1800);else onReady();
      }catch(e){if(alive)setError(e.message);}
    }
    poll();return()=>{alive=false;clearTimeout(timer);};
  },[docId,onReady,reload]);
  useEffect(()=>{if(tab==="clauses"&&selected!==null)sourceRef.current?.querySelector('[data-clause="'+selected+'"]')?.scrollIntoView({behavior:"smooth",block:"center"});},[tab,selected]);
  const source=useCallback(index=>{setSelected(index);setTab("clauses");},[]);
  async function retry(){setRetrying(true);try{await api.retry(docId);setDoc(d=>({...d,status:"queued",error:null}));setReload(n=>n+1);}catch(e){setError(e.message);}finally{setRetrying(false);}}
  function download(){
    const a=doc.analysis;
    const report=["SimplyDoc · DOCUMENT REVIEW",doc.filename,"Mode: "+a.model,"Explanation only; not legal advice.",a.plain_summary,a.review_note||"",a.coverage?`Reviewed ${a.coverage.reviewed_sections} of ${a.coverage.total_sections} sections in ${a.coverage.batches} parts.`:"",...(doc.extraction?.warnings||[]),"KEY TERMS",
      ...a.key_terms.map(t=>t.term+": "+t.value+"\n"+t.explanation+" [Clause "+(t.clause_index+1)+", page "+(t.page||"see source")+"]\n"+(t.quote||"")+"\n"+(t.verification==="source_matched"?"Source quote matched; verify interpretation.":"Needs verification against original.")),"CLAUSES TO REVIEW",
      ...a.risky_clauses.map(r=>r.risk_level.toUpperCase()+": "+r.title+"\n"+r.reason+'\n"'+r.quote+'"\nClause '+(r.clause_index+1)+", page "+r.page+"\nAsk: "+r.question),
      "SOURCE TEXT",...doc.clauses.map(c=>"["+(c.clause_index+1)+"] Page "+c.page+"\n"+c.text)].join("\n\n");
    const url=URL.createObjectURL(new Blob([report],{type:"text/plain;charset=utf-8"}));
    const link=document.createElement("a");link.href=url;link.download=doc.filename.replace(/\.pdf$/i,"")+" - review.txt";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  if(!doc)return <main className="document-main" id="main-content" tabIndex={-1}>{error?<div className="error-box" role="alert">{error}<button onClick={()=>setReload(n=>n+1)}>Try again</button></div>:<div className="state-card" role="status"><span className="spinner"/><h2>Opening your document…</h2></div>}</main>;
  const a=doc.analysis,risks=[...(a?.risky_clauses||[])].sort((x,y)=>({high:0,medium:1,low:2}[x.risk_level]-{high:0,medium:1,low:2}[y.risk_level]));
  return <main className="document-main" id="main-content" tabIndex={-1}>
    <button className="text-button back-button" onClick={onBack}><Icon name="arrow" size={15}/> Back to all documents</button>
    <div className="document-heading"><div className="document-title-icon"><Icon size={26}/></div><div className="document-title"><p className="eyebrow">{a?.document_type||"DOCUMENT REVIEW"}</p><h1>{doc.filename}</h1><p>{doc.page_count} {doc.page_count === 1 ? "page" : "pages"} · {doc.clauses.length} {doc.clauses.length === 1 ? "section" : "sections"} · {new Date(doc.uploaded_at*1000).toLocaleDateString()}</p></div><div className="document-actions">{a&&<button className="button secondary" onClick={download}><Icon name="download"/>Download report</button>}<button className="icon-button" aria-label="Delete document" onClick={()=>onDelete(docId)}><Icon name="trash"/></button></div></div>
    {error&&<div role="alert" className="error-box">{error} <button className="text-button" onClick={()=>setReload(n=>n+1)}>Refresh</button></div>}
    {!["queued","processing","needs_review"].includes(doc.status)&&!editing&&<button className="button secondary source-edit-toggle" onClick={()=>setEditing(true)}>Check or correct extracted text</button>}
    {editing||doc.status==="needs_review"?<SourceReview doc={doc} onClose={doc.status==="needs_review"?undefined:()=>setEditing(false)} onSaved={()=>{setEditing(false);setDoc(d=>({...d,status:"queued",analysis:null,error:null}));setReload(n=>n+1);onReady();}}/>:["queued","processing"].includes(doc.status)?<div className="state-card" role="status"><span className="spinner"/><span className="eyebrow">READING THE FINE PRINT</span><h2>{doc.status==="queued"?"Your document is in the queue.":"A clearer picture is on its way."}</h2><p>{doc.progress?`Reviewed ${doc.progress.completed} of ${doc.progress.total} parts. Large documents are processed automatically in smaller parts.`:"Checking clauses and preparing document search."}<br/>You can return to this document while analysis continues.</p></div>:
    doc.status==="failed"?<div className="state-card"><Icon name="alert" size={32}/><h2>We couldn't finish this review.</h2><p>{doc.error}</p><button className="button primary" disabled={retrying} onClick={retry}>Retry analysis</button></div>:
    <>{a?.mode==="demo"&&<div className="demo-banner"><span className="pill">LOCAL DEMO</span><p>Rule-based flags and selected excerpts. AI summaries and answers require the configured AI service.</p></div>}
    {doc.extraction?.ocr_pages?.length>0&&<section className="extraction-banner" aria-label="Text extraction quality"><strong>Read using OCR · {doc.extraction.language} · {doc.extraction.ocr_pages.length} scanned pages</strong><p>This review covers extracted text only. Maps, signatures and handwriting are not interpreted.</p>{doc.extraction.warnings.map((warning,i)=><p key={i}>{warning}</p>)}</section>}
    <nav className="tabs" aria-label="Document sections">{Object.entries(names).map(([key,label])=><button key={key} className={tab===key?"active":""} aria-current={tab===key?"page":undefined} onClick={()=>setTab(key)}>{key==="chat"&&<Icon name="chat" size={18}/>} {label}{key==="risks"&&<span className="count-badge">{risks.length}</span>}</button>)}</nav>
    {tab==="summary"&&<div className="overview-grid"><section className="card overview-card"><div className="section-heading"><Icon name="book"/><h2>{a.mode==="demo"?"Document overview":"In plain language"}</h2></div><p className="summary-text">{a.plain_summary}</p>{a.coverage&&<p className="muted small">Reviewed {a.coverage.reviewed_sections} of {a.coverage.total_sections} sections in {a.coverage.batches} parts. {a.review_note}</p>}<hr/><h2>Key terms at a glance</h2>{a.key_terms.length===0?<p>No key terms identified. Read the original wording in Source text.</p>:a.key_terms.map((t,i)=><div className="key-term" key={i}><h3>{t.term}</h3><p>{t.value}</p><span className="muted small">{t.explanation}</span><p className="muted small">{t.verification==="source_matched"?"Source quote matched · verify interpretation":"Needs verification against the original"}</p>{t.quote&&<blockquote>{t.quote}</blockquote>}<button className="source-button" onClick={()=>source(t.clause_index)}>Clause {t.clause_index+1} · Page {t.page||doc.clauses.find(c=>c.clause_index===t.clause_index)?.page}<Icon name="arrow" size={14}/></button></div>)}</section>
    <aside className="review-rail"><section className="card signal-card"><span className="eyebrow">CLOSER LOOK</span><div className="risk-total">{risks.length}<span>potential concerns</span></div><p>Flags help you decide what to clarify. They do not determine whether a contract is safe or enforceable.</p><div className="risk-breakdown">{["high","medium","low"].map(level=><div key={level}><span><i className={"status-dot "+level}/>{level==="high"?"High attention":level==="medium"?"Worth reviewing":"Note"}</span><strong>{risks.filter(r=>r.risk_level===level).length}</strong></div>)}</div><button className="button secondary wide" onClick={()=>setTab("risks")}>Review the flags <Icon name="arrow"/></button></section><section className="rail-note"><Icon name="chat"/><h3>Something unclear?</h3><p>Ask about a payment, a notice period, or a specific clause.</p><button className="text-button" onClick={()=>setTab("chat")}>Ask your document <Icon name="arrow" size={16}/></button></section></aside></div>}
    {tab==="risks"&&<RiskList risks={risks} onSource={source}/>}
    {tab==="clauses"&&<section ref={sourceRef} className="source-section"><h2>The original wording</h2><p className="muted">Extracted text; formatting may differ. Check the original PDF for tables and signatures.</p>{doc.clauses.map(c=><article data-clause={c.clause_index} tabIndex={0} className={"card source-clause "+(selected===c.clause_index?"highlighted":"")} key={c.clause_index}><div className="source-meta"><span>CLAUSE {c.clause_index+1}</span><span>PAGE {c.page}{doc.extraction?.ocr_pages?.includes(c.page)?" · OCR — verify wording":""}</span></div><p>{c.text}</p></article>)}</section>}
    {tab==="chat"&&<ChatPanel documentType={a.document_type} docId={docId} onSource={source}/>}
    <footer className="review-footer"><Icon name="shield" size={16}/><span>AI-assisted document analysis for informational purposes. Not a substitute for professional legal advice.</span></footer></>}
  </main>;
}
