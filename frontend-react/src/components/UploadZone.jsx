import { useRef, useState } from "react";
import Icon from "./Icon";
export default function UploadZone({ onFileSelected, busy, compact = false, accept=".pdf", description="Contracts, agreements, policies. Let’s make them clearer." }) {
  const input = useRef(null), dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  return <div className={(compact ? "upload-compact" : "upload-zone") + (dragging && !busy ? " dragging" : "")} aria-busy={busy}
    onDragEnter={e => { e.preventDefault(); dragDepth.current++; setDragging(true); }}
    onDragOver={e => e.preventDefault()}
    onDragLeave={e => { e.preventDefault(); if (--dragDepth.current <= 0) setDragging(false); }}
    onDrop={e => { e.preventDefault(); dragDepth.current = 0; setDragging(false); if (!busy && e.dataTransfer.files[0]) onFileSelected(e.dataTransfer.files[0]); }}>
    <input ref={input} type="file" accept={accept} aria-label="Upload a document" hidden disabled={busy} onChange={e => { if (!busy && e.target.files[0]) onFileSelected(e.target.files[0]); e.target.value = ""; }}/>
    {compact ? <button className="button primary wide" onClick={() => input.current.click()} disabled={busy}><Icon name="plus"/>{busy ? "Uploading…" : "New document"}</button> : <>
      <span className="upload-icon">{busy ? <span className="spinner"/> : <Icon name="upload" size={27}/>}</span>
      <h3>{busy ? "Getting your document ready…" : dragging ? "Drop your document to get started" : "Drop your document here"}</h3>
      <p>{busy ? "Extracting the text. Scanned PDFs can take up to 90 seconds." : description}</p>
      <button className="button primary" onClick={() => input.current.click()} disabled={busy}>{busy ? "Uploading & reading…" : "Browse files"}{!busy && <Icon name="arrow" size={17}/>}</button>
      {busy ? <div className="upload-progress" role="status"><span/>Reading your PDF before analysis</div> : <span className="upload-limits">{accept.replaceAll(".", "").toUpperCase()} up to 10 MB <span>·</span> 80 pages (12 scanned)</span>}
      <div className="upload-types"><span>Private library</span><span>Source references</span><span>Saved progress</span></div>
    </>}
  </div>;
}
