import { useEffect, useState } from "react";
import { api } from "../api";
import Icon from "./Icon";

export function LegalPeriod({ value, onChange, disabled = false, id = "legal-period" }) {
  return <label className="legal-filter" htmlFor={id}>Date of alleged conduct
    <select id={id} value={value} onChange={event => onChange(event.target.value)} disabled={disabled}>
      <option value="unknown">Unknown · show IPC and BNS</option>
      <option value="before">Before 1 July 2024</option>
      <option value="after">From 1 July 2024</option>
    </select>
  </label>;
}

export default function LegalReferences({ docId, onSource, onAsk }) {
  const [result, setResult] = useState(null);
  const [input, setInput] = useState(""), [query, setQuery] = useState("");
  const [period, setPeriod] = useState("unknown"), [act, setAct] = useState("all");
  const [browse, setBrowse] = useState(false), [reload, setReload] = useState(0);
  const requestKey = JSON.stringify([docId, query, period, act, browse, reload]);
  const loading = result?.key !== requestKey, data = !loading ? result?.data : null, error = !loading ? result?.error : "";
  useEffect(() => {
    let alive = true;
    api.getLegalReferences(docId, { q: query, period, act, browse }).then(value => {
      if (alive) setResult({ key: requestKey, data: value });
    }).catch(e => { if (alive) setResult({ key: requestKey, error: e.message }); });
    return () => { alive = false; };
  }, [docId, query, period, act, browse, requestKey]);
  function search(value) { setInput(value); setQuery(value.trim()); }
  return <section className="legal-library" aria-label="Central Indian legal references">
    <header className="card legal-intro">
      <div className="section-heading"><Icon name="book"/><h2>Legal references</h2><span className="pill">INDIA · CENTRAL LAWS</span></div>
      <p>Explore selected laws alongside your document. Topic matches help you decide what to check with a lawyer; they do not determine whether a law applies.</p>
      <form className="legal-search" onSubmit={event => { event.preventDefault(); setQuery(input.trim()); }}>
        <label htmlFor="law-search" className="sr-only">Search laws or sections</label>
        <input id="law-search" value={input} onChange={event => setInput(event.target.value)} maxLength={200} placeholder="Try IPC 420, BNS 318, registration or forgery…"/>
        <button className="button primary" type="submit">Search<Icon name="search" size={17}/></button>
      </form>
      <div className="legal-controls">
        <label className="legal-filter" htmlFor="law-act">Act<select id="law-act" value={act} onChange={event => setAct(event.target.value)}>
          <option value="all">All included acts</option><option value="IPC">IPC · historical</option><option value="BNS">BNS</option>
          <option value="TPA">Transfer of Property Act</option><option value="REG">Registration Act</option><option value="ICA">Indian Contract Act</option>
        </select></label>
        <LegalPeriod value={period} onChange={setPeriod}/>
        <label className="legal-toggle"><input type="checkbox" checked={browse} onChange={event => setBrowse(event.target.checked)}/>Browse full collection</label>
      </div>
      <p className="muted small">The conduct date is not the document or upload date. A specifically requested IPC/BNS section stays visible regardless of the period filter.</p>
      <div className="legal-examples">Try:{["sale deed", "registration", "IPC 420", "forgery"].map(text => <button className="suggestion" key={text} onClick={() => search(text)}>{text}</button>)}{query && <button className="text-button" onClick={() => search("")}>Clear search</button>}</div>
    </header>
    {loading ? <p role="status" className="muted">Finding legal references…</p> : error ? <div className="error-box" role="alert">{error}<button className="text-button" onClick={() => setReload(n => n + 1)}>Try again</button></div> : data && <>
      <div className="legal-results-heading"><h3>{query ? "Search results" : browse ? "Included provisions" : "Topics found in your document"}</h3><span>{data.entries.length} references</span></div>
      {data.missing_requested?.length > 0 && <p role="status">Some requested sections are outside this collection. Only covered provisions are shown.</p>}
      {data.entries.length === 0 && <div className="card legal-empty"><Icon name="book"/><h3>No matching reference in this collection</h3><p>This does not mean no law applies. Try another topic or browse the selected provisions.</p><button className="button secondary" onClick={() => { search(""); setBrowse(true); setAct("all"); }}>Browse collection</button></div>}
      <div className="legal-grid">{data.entries.map(entry => <article className="card legal-entry" key={entry.id}>
        <div className="legal-entry-meta"><span className="eyebrow">{entry.act} · SECTION {entry.section}</span>{entry.status === "historical" && <span className="pill historical">HISTORICAL IPC</span>}</div>
        <h3>{entry.title}</h3><p className="muted small">{entry.act_name}</p>
        <p>{entry.summary}</p><span className="legal-summary-label">Edited summary · not a statutory quotation</span>
        <div className="legal-match"><strong>{entry.reason}</strong>{entry.evidence.map(evidence => <button key={evidence.clause_index} className="source-button" onClick={() => onSource(evidence.clause_index)} title={evidence.reason}>Document section {evidence.clause_index + 1} · Page {evidence.page}<Icon name="arrow" size={14}/></button>)}</div>
        {entry.related.length > 0 && <p className="legal-related">Related provisions: {entry.related.map(related => <button key={related.id} className="text-button" onClick={() => { setAct("all"); search(related.label); }}>{related.label}</button>)}<span className="muted small">Check wording and scope; not necessarily identical.</span></p>}
        <details className="legal-provenance"><summary>About this source</summary><p>{entry.source_note}</p><p>Source checked: {entry.checked_on}. This library is not automatically updated.</p></details>
        <div className="legal-entry-actions"><a className="button secondary" href={entry.source_url} target="_blank" rel="noopener noreferrer">Official source<Icon name="arrow" size={15}/></a><button className="button primary" onClick={() => onAsk({ text: `Explain ${entry.act} section ${entry.section} and what I should verify in this document.`, period })}><Icon name="chat" size={16}/>Ask about this</button></div>
      </article>)}</div>
      <aside className="legal-scope card"><h3>Coverage and dates</h3><p>{data.notice}</p><p>{data.transition}</p><p><a href={data.commencement_url} target="_blank" rel="noopener noreferrer">Commencement note (India Code)</a> · <a href={data.mapping_url} target="_blank" rel="noopener noreferrer">Official IPC/BNS comparison</a></p><p className="muted small">{data.count} selected provisions · Source check {data.checked_on} · Library {data.version}</p></aside>
    </>}
  </section>;
}
