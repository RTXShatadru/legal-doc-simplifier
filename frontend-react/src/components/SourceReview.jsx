import {useEffect,useState} from "react";
import {api} from "../api";

export default function SourceReview({doc,onSaved,onClose}){
  const [sections,setSections]=useState(()=>doc.clauses.map(c=>({clause_index:c.clause_index,text:c.text})));
  const [pdf,setPdf]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{if(!pdf)return;return()=>URL.revokeObjectURL(pdf);},[pdf]);
  async function save(e){e.preventDefault();setBusy(true);setError("");try{await api.reviewSource(doc.doc_id,sections,doc.source_revision);onSaved();}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <section className="card source-review"><h2>Check extracted text</h2><p>Compare names, dates, amounts and property numbers with your PDF. Correct OCR mistakes below. Mark unreadable wording as [unclear] instead of guessing.</p>
    {(doc.extraction?.warnings||[]).map((w,i)=><p className="muted" key={i}>{w}</p>)}
    <label className="button secondary">Choose original PDF for comparison<input type="file" accept="application/pdf,.pdf" onChange={e=>{const f=e.target.files?.[0];if(f)setPdf(URL.createObjectURL(f));}}/></label>
    <p className="muted small">This preview stays in your browser. Saving replaces the previous analysis and chat with a fresh review of this text.</p>
    <div className={pdf?"source-review-columns":""}>{pdf&&<iframe title="Original PDF for comparison" src={pdf}/>}
    <form onSubmit={save}>{sections.map((c,i)=><div className="source-edit" key={c.clause_index}><label htmlFor={"source-"+c.clause_index}>Section {c.clause_index+1} · Page {doc.clauses[i].page}</label><textarea id={"source-"+c.clause_index} required maxLength={8000} rows={5} value={c.text} onChange={e=>setSections(s=>s.map((v,j)=>j===i?{...v,text:e.target.value}:v))}/>{doc.extraction?.original_sections?.find(v=>v.clause_index===c.clause_index)&&<details><summary>Original extraction</summary><p>{doc.extraction.original_sections.find(v=>v.clause_index===c.clause_index).text}</p></details>}</div>)}
    {error&&<p role="alert" className="error-box">{error}</p>}<button className="button primary" disabled={busy}>{busy?"Saving…":"Save text and analyze"}</button> {onClose&&<button className="button secondary" type="button" disabled={busy} onClick={onClose}>Cancel</button>}</form></div></section>;
}
