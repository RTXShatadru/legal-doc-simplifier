import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Icon from "./Icon";
import { LegalPeriod } from "./LegalReferences";

function starters(domain, workflow, type = "") {
  if (workflow === "resume") return ["Which skills are listed in my resume?", "What work experience does my resume describe?", "What education is listed?"];
  if (domain === "hr") return ["What salary and benefits are stated?", "What is the notice period?", "What does the probation clause mean?"];
  if (domain === "medical") return ["Explain the results printed in this report.", "Which values are outside the printed reference ranges?", "Which details in the report need clarification?"];
  if (domain === "court") return ["What action does this notice ask for?", "Which deadlines are stated?", "Who is named in this document?"];
  if (/rent|lease/i.test(type)) return ["How much is the rent?", "How can I end the agreement?", "What happens to the deposit?"];
  if (/deed|sale|property/i.test(type)) return ["Who are the buyer and seller?", "What property area is described?", "What is the sale consideration?"];
  if (domain === "finance" || /loan|credit/i.test(type)) return ["What interest and fees are stated?", "Are there late payment charges?", "What are the repayment terms?"];
  return ["Explain section 1 in plain language.", "What payment terms are stated?", "Which deadlines are mentioned?"];
}

function Answer({ message, onSource }) {
  const sources = (message.sources || []).filter(source => source.kind !== "law");
  const laws = (message.sources || []).filter(source => source.kind === "law" && /^https:\/\//.test(source.url));
  return <>
    <p>{message.content.split(/(\[\d+\]|\[LAW:[^\]]+\])/g).map((part, i) => {
      const law = laws.find(source => part === `[LAW:${source.id}]`);
      if (law) return <a key={i} className="inline-citation" href={law.url} target="_blank" rel="noopener noreferrer" aria-label={"Official source: " + law.label}>{law.label.split(" · ")[0]}</a>;
      const match = /^\[(\d+)\]$/.exec(part);
      const source = match && sources.find(s => s.clause_index === Number(match[1]) - 1);
      return source ? <button key={i} className="inline-citation" aria-label={"Open section " + match[1] + ", page " + source.page} onClick={() => onSource(source.clause_index)}>{part}</button> : part;
    })}</p>
    {sources.length > 0 && <details className="chat-evidence">
      <summary>{sources.length} source {sources.length === 1 ? "passage" : "passages"} · check the original wording</summary>
      {sources.map(s => <div className="chat-evidence-item" key={s.clause_index}>
        <button className="source-button" onClick={() => onSource(s.clause_index)}><Icon name="file" size={14}/>Section {s.clause_index + 1} · Page {s.page}</button>
        {s.is_excerpt && <p className="muted small">Selected excerpt. Open the source section for the full context.</p>}
        <blockquote>{s.text}</blockquote>
      </div>)}
    </details>}
    {laws.length > 0 && <details className="chat-evidence legal-chat-evidence">
      <summary>{laws.length} legal {laws.length === 1 ? "reference" : "references"} · central India</summary>
      {laws.map(law => <div className="chat-evidence-item" key={law.id}><a href={law.url} target="_blank" rel="noopener noreferrer">{law.label}</a>{law.status === "historical" && <span className="pill historical">Historical IPC</span>}<p>{law.summary}</p><p className="muted small">Edited summary · source checked {law.checked_on} · Library {law.version}</p></div>)}
    </details>}
  </>;
}

export default function ChatPanel({ docId, onSource, documentType, domain, workflow, filename, active = true, legalQuestion }) {
  const [messages, setMessages] = useState([]), [input, setInput] = useState("");
  const [pending, setPending] = useState(""), [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [reload, setReload] = useState(0), [historyReady, setHistoryReady] = useState(false), [elapsed, setElapsed] = useState(0);
  const log = useRef(null), generation = useRef(0), sending = useRef(false), composer = useRef(null);
  const [includeLaw, setIncludeLaw] = useState(Boolean(legalQuestion)), [legalPeriod, setLegalPeriod] = useState(legalQuestion?.period || "unknown");
  const [lastLegalQuestion, setLastLegalQuestion] = useState(null);
  const incomingLegalQuestion = useRef(legalQuestion);
  useEffect(() => { incomingLegalQuestion.current = legalQuestion; }, [legalQuestion]);
  // A new library selection replaces the draft once; later typing is preserved.
  if (legalQuestion && legalQuestion !== lastLegalQuestion) {
    setLastLegalQuestion(legalQuestion); setInput(legalQuestion.text); setIncludeLaw(true); setLegalPeriod(legalQuestion.period);
  }

  useEffect(() => {
    const run = ++generation.current;
    api.getChatHistory(docId).then(history => {
      if (generation.current === run) {
        setMessages(history); setHistoryReady(true);
        const previousLaw = history.filter(message => message.role === "assistant").at(-1)?.sources?.find(source => source.kind === "law");
        if (previousLaw && !incomingLegalQuestion.current) { setIncludeLaw(true); setLegalPeriod(previousLaw.period || "unknown"); }
      }
    }).catch(e => {
      if (generation.current === run) setError(e.message);
    }).finally(() => {
      if (generation.current === run) setLoading(false);
    });
    return () => { generation.current = run + 1; };
  }, [docId, reload]);
  useEffect(() => {
    if (active && historyReady && !busy) composer.current?.focus({ preventScroll: true });
  }, [active, historyReady, busy]);
  useEffect(() => {
    if (active && log.current) log.current.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, active]);
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  async function send(text = input) {
    const question = text.trim();
    if (!question || sending.current || !historyReady) return;
    const run = generation.current;
    sending.current = true; setBusy(true); setElapsed(0); setPending(question); setError(""); setInput("");
    try {
      const result = includeLaw ? await api.sendChatMessage(docId, question, { include_law: true, legal_period: legalPeriod }) : await api.sendChatMessage(docId, question);
      if (generation.current === run) setMessages(previous => [...previous, { role: "user", content: question }, { role: "assistant", content: result.answer, sources: result.sources }]);
    } catch (e) {
      if (generation.current === run) { setError(e.message); setInput(question); }
    } finally {
      sending.current = false;
      if (generation.current === run) {
        setBusy(false); setPending("");
      }
    }
  }

  return <section className="card chat-card" aria-label="Document chat">
    <header className="chat-heading">
      <span className="chat-heading-icon"><Icon name="chat" size={22}/></span>
      <div><h2>Document chat</h2><p>Ask in English or Hindi. Follow the references to check each answer.</p></div>
    </header>
    {filename && <div className="chat-document-context"><Icon name="file" size={15}/><span title={filename}>{filename}</span><span className="chat-saved-note">Conversation saved</span></div>}
    <div ref={log} className="chat-log" role="log" aria-label="Document conversation" aria-live="polite" aria-busy={busy}>
      {loading ? <p className="muted">Loading your conversation…</p> : <>
        {messages.length === 0 && !pending && historyReady && <div className="chat-intro">
          <span className="upload-icon"><Icon name="chat" size={28}/></span>
          <h3>Let’s make it clearer.</h3><p>Ask about a detail, explain a difficult term, or clarify a section. Answers stay focused on this document.</p>
          <div className="suggestions">{starters(domain, workflow, documentType).map(question => <button className="suggestion" key={question} onClick={() => send(question)} disabled={busy}>{question}<Icon name="arrow" size={16}/></button>)}</div>
        </div>}
        {messages.map((message, i) => <article className={"message " + message.role} key={i}>
          <div className="message-label">{message.role === "user" ? "YOU" : "SimplyDoc"}</div>
          {message.role === "assistant" ? <Answer message={message} onSource={onSource}/> : <p>{message.content}</p>}
        </article>)}
      </>}
      {pending && <article className="message user"><div className="message-label">YOU</div><p>{pending}</p></article>}
      {busy && <p className="typing" role="status"><span className="spinner small-spinner"/>{elapsed < 15 ? "Reading the relevant passages…" : "Still checking your document…"} <span aria-live="off">{elapsed}s</span></p>}
    </div>
    {historyReady && !busy && messages.some(message => message.role === "assistant") && <div className="chat-followups" aria-label="Follow-up suggestions">
      <span>Keep asking</span>{["Explain that more simply.", "Which section supports that?"].map(question => <button key={question} onClick={() => send(question)}>{question}</button>)}
    </div>}
    {error && <div className="error-box" role="alert">{error}{!historyReady ? <button className="text-button" disabled={loading} onClick={() => { setLoading(true); setHistoryReady(false); setError(""); setReload(value => value + 1); }}>Reload conversation</button> : <p>Your question is still in the box. You can try sending it again.</p>}</div>}
    <div className="legal-chat-controls">
      <label className="legal-toggle"><input type="checkbox" checked={includeLaw} disabled={busy} onChange={event => setIncludeLaw(event.target.checked)}/>Include central Indian law references</label>
      {includeLaw && <><LegalPeriod id="chat-legal-period" value={legalPeriod} onChange={setLegalPeriod} disabled={busy}/><p className="muted small">Selected IPC, BNS, property, registration and contract provisions. Name the law or topic. State laws and case law are not included.</p></>}
    </div>
    <form className="chat-form" onSubmit={event => { event.preventDefault(); send(); }}>
      <label htmlFor="question" className="sr-only">Question about this document</label>
      <textarea ref={composer} id="question" rows={2} value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(); }
      }} maxLength={2000} placeholder="What would you like to clarify? You can also ask ‘Explain section 3’…" disabled={!historyReady || busy}/>
      <button type="submit" className="button primary" disabled={busy || !historyReady || !input.trim()}>{busy ? "Answering…" : "Send"}<Icon name="arrow"/></button>
    </form>
    <div className="chat-composer-note"><span>Enter to send · Shift+Enter for a new line</span><span>{input.length}/2000</span></div>
    <p className="chat-disclaimer">Answers use selected document passages and may miss context. Verify important details against the original document.</p>
  </section>;
}
