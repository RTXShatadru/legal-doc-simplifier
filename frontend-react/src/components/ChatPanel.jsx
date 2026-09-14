import {useEffect,useRef,useState} from "react";
import {api} from "../api";
import Icon from "./Icon";

function starters(type=""){
  if(/deed|sale|property/i.test(type))return ["Who are the buyer and seller?","What property area is described?","What is the sale consideration?"];
  if(/loan|credit/i.test(type))return ["What is the interest rate?","Are there late payment charges?","Can I repay the loan early?"];
  if(/research|academic|paper/i.test(type))return ["What method does the paper use?","What are the main findings?","What limitations are mentioned?"];
  if(/rent|lease/i.test(type))return ["How much is the rent?","How can I end the agreement?","What happens to the deposit?"];
  return ["What are my main obligations?","Which deadlines should I know about?","Explain section 1 in plain English."];
}
function Answer({message,onSource}){
  const sources=message.sources||[];
  return <><p>{message.content.split(/(\[\d+\])/g).map((part,i)=>{const match=/^\[(\d+)\]$/.exec(part);const source=match&&sources.find(s=>s.clause_index===Number(match[1])-1);return source?<button key={i} className="inline-citation" aria-label={"Open section "+match[1]+", page "+source.page} onClick={()=>onSource(source.clause_index)}>{part}</button>:part;})}</p>{sources.length>0&&<details className="chat-evidence"><summary>{sources.length} source {sources.length===1?"passage":"passages"} · check the original wording</summary>{sources.map(s=><div className="chat-evidence-item" key={s.clause_index}><button className="source-button" onClick={()=>onSource(s.clause_index)}><Icon name="file" size={14}/>Section {s.clause_index+1} · Page {s.page}</button><blockquote>{s.text}</blockquote></div>)}</details>}</>;
}
export default function ChatPanel({docId,onSource,documentType}){
  const [messages,setMessages]=useState([]),[input,setInput]=useState(""),[pending,setPending]=useState(""),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(""),[reload,setReload]=useState(0),[historyReady,setHistoryReady]=useState(false),[elapsed,setElapsed]=useState(0);
  const end=useRef(null),generation=useRef(0),sending=useRef(false),composer=useRef(null);
  useEffect(()=>{const run=++generation.current;api.getChatHistory(docId).then(m=>{if(generation.current===run){setMessages(m);setError("");setHistoryReady(true);}}).catch(e=>{if(generation.current===run)setError(e.message);}).finally(()=>{if(generation.current===run)setLoading(false);});return()=>{generation.current=run+1;};},[docId,reload]);
  useEffect(()=>{end.current?.scrollIntoView({behavior:"smooth",block:"nearest"});},[messages,busy]);
  useEffect(()=>{if(!busy)return;const started=Date.now();const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-started)/1000)),1000);return()=>clearInterval(timer);},[busy]);
  async function send(text=input){
    const question=text.trim();if(!question||sending.current||!historyReady)return;
    const run=generation.current;sending.current=true;setBusy(true);setElapsed(0);setPending(question);setError("");setInput("");
    try{const result=await api.sendChatMessage(docId,question);if(generation.current===run)setMessages(m=>[...m,{role:"user",content:question},{role:"assistant",content:result.answer,sources:result.sources}]);}
    catch(e){if(generation.current===run){setError(e.message);setInput(question);}}
    finally{sending.current=false;if(generation.current===run){setBusy(false);setPending("");composer.current?.focus();}}
  }
  return <section className="card chat-card"><header className="chat-heading"><div><h2>Ask your document</h2><p>English or Hindi · Answers with source references</p></div></header><div className="chat-log" role="log" aria-label="Document conversation" aria-live="polite" aria-busy={busy}>
    {loading?<p className="muted">Loading your conversation…</p>:<>{messages.length===0&&!pending&&historyReady&&<div className="chat-intro"><span className="upload-icon"><Icon name="chat" size={28}/></span><h3>What would you like to understand?</h3><p>Ask about a detail or a section number. Follow-up questions can refer to your previous question.</p><div className="suggestions">{starters(documentType).map(q=><button className="suggestion" key={q} onClick={()=>send(q)} disabled={busy}>{q}<Icon name="arrow" size={16}/></button>)}</div></div>}{messages.map((m,i)=><article className={"message "+m.role} key={i}><div className="message-label">{m.role==="user"?"YOU":"SimplyDoc"}</div>{m.role==="assistant"?<Answer message={m} onSource={onSource}/>:<p>{m.content}</p>}</article>)}</>}
    {pending&&<article className="message user"><div className="message-label">YOU</div><p>{pending}</p></article>}
    {busy&&<p className="typing" role="status"><span className="spinner small-spinner"/>{elapsed<15?"Reading the relevant passages…":"The analysis model is still working…"} <span aria-live="off">{elapsed}s</span></p>}<div ref={end}/></div>
    {error&&<div className="error-box" role="alert">{error}{!historyReady&&<button className="text-button" disabled={loading} onClick={()=>{setLoading(true);setHistoryReady(false);setReload(n=>n+1);}}>Reload conversation</button>}</div>}
    <form className="chat-form" onSubmit={e=>{e.preventDefault();send();}}><label htmlFor="question" className="sr-only">Question about this document</label><textarea ref={composer} id="question" rows={2} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}} maxLength={2000} placeholder="Ask about this document, or try ‘Explain section 3’…" disabled={!historyReady||busy}/><button className="button primary" disabled={busy||!historyReady||!input.trim()}>{busy?"Answering…":"Ask"}<Icon name="arrow"/></button></form><div className="chat-composer-note"><span>Enter to send · Shift+Enter for a new line</span><span>{input.length}/2000</span></div><p className="chat-disclaimer">Answers use selected passages and may miss context. Verify unclear OCR against the original PDF.</p></section>;
}
