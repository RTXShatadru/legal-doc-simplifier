import { useState } from "react";
import { api } from "../api";
import Icon, { Brand } from "./Icon";
import GoogleButton from "./GoogleButton";

export default function AuthScreen({ onAuthenticated, health, googleAvailable }) {
  const [mode, setMode] = useState('signup'), [email, setEmail] = useState(''), [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [googleBusy, setGoogleBusy] = useState(false), [showPassword, setShowPassword] = useState(false);
  async function googleSignIn() {
    if (busy || googleBusy) return;
    setGoogleBusy(true); setError('');
    try { const result = await api.startGoogle(); window.location.assign(result.url); }
    catch (e) { setError(e.message); setGoogleBusy(false); }
  }
  async function submit(e) {
    e.preventDefault();
    if (busy || googleBusy) return;
    setBusy(true); setError('');
    try { onAuthenticated(await api[mode](email, password)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <main className="auth-layout"><section className="auth-story"><Brand/>
    <div className="auth-story-content"><span className="auth-kicker"><span/> LESS JARGON. MORE CLARITY.</span><h1>The fine print.<br/><em>Finally, clear.</em></h1><p>Understand what your documents say,<br className="desktop-break"/> what matters, and what to ask next.</p>
    <div className="auth-document-art"><div className="art-document"><div className="art-doc-top"><Icon size={23}/><span>RENTAL AGREEMENT<small>A closer look at your document</small></span><span className="art-page">01</span></div><span className="art-line"/><span className="art-line short"/><p className="art-excerpt">“The lessee shall remit payment prior to the fifth day of each calendar month.”</p><span className="art-line"/><span className="art-line medium"/><span className="art-line short"/><div className="art-doc-footer">SOURCE · PAGE 1 <Icon name="check" size={16}/></div></div>
    <div className="art-insight"><span><Icon name="sparkles" size={17}/> IN PLAIN ENGLISH</span><p>You need to pay your rent<br/><strong>before the 5th of each month.</strong></p><span className="art-source"><Icon name="file" size={12}/> Page 1 · Illustrative example</span></div></div>
    <div className="auth-benefits"><span><Icon name="check" size={15}/> Plain-language summaries</span><span><Icon name="check" size={15}/> Source-backed answers</span></div></div>
    <p className="auth-footnote">A clearer way forward. <span>Not legal advice.</span></p></section>
    <section className="auth-form-wrap"><div className="auth-top-note"><Icon name="shield" size={16}/> YOUR PERSONAL DOCUMENT WORKSPACE</div><div className="auth-form"><span className="form-step">LET’S GET YOU STARTED</span><h2>{mode === 'signup' ? 'Clarity starts here.' : 'Good to see you again.'}</h2><p>{mode === 'signup' ? 'Create your account. Make sense of your next document.' : 'Sign in and pick up where you left off.'}</p>
    <div className="auth-mode-tabs" aria-label="Account access"><button className={mode === 'signup' ? 'active' : ''} aria-pressed={mode === 'signup'} disabled={busy || googleBusy} onClick={() => { setMode('signup'); setError(''); }}>Create account</button><button className={mode === 'login' ? 'active' : ''} aria-pressed={mode === 'login'} disabled={busy || googleBusy} onClick={() => { setMode('login'); setError(''); }}>Sign in</button></div>
    {googleAvailable && <><GoogleButton onClick={googleSignIn} disabled={busy} busy={googleBusy}/><div className="auth-divider"><span>or continue with email</span></div></>}
    <form onSubmit={submit}><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} placeholder="you@example.com" disabled={busy || googleBusy}/><label htmlFor="password">Password</label><div className="password-field"><input id="password" type={showPassword ? 'text' : 'password'} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} required minLength={8} maxLength={128} placeholder="At least 8 characters" disabled={busy || googleBusy}/><button type="button" className="icon-button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword(v => !v)}><Icon name={showPassword ? 'eyeOff' : 'eye'} size={18}/></button></div>
    {mode === 'signup' && <p className="password-hint">Use 8 or more characters to keep your account secure.</p>}{error && <p className="error-box" role="alert">{error}</p>}<button className="button primary wide" disabled={busy || googleBusy}>{busy ? 'Opening your workspace…' : mode === 'signup' ? 'Create your account' : 'Sign in to SimplyDoc'}{busy ? <span className="spinner small-spinner"/> : <Icon name="arrow" size={18}/>}</button></form>
    <div className="privacy-note"><Icon name="shield" size={19}/><p>Documents stay scoped to your account. {health?.ai_provider === 'groq' ? 'Groq processes extracted text using your configured model for analysis and chat.' : health?.ai_provider === 'gemini' ? 'Gemini receives extracted text; free-tier content may be used to improve Google products.' : health?.ai_provider === 'ollama' ? 'Text is processed on the configured Ollama server.' : 'Local demo analysis uses rules and excerpts.'} {health?.embedding_provider === 'voyage' && 'Voyage AI receives text for retrieval.'} Delete your documents at any time.</p></div></div>
    <p className="auth-legal">AI-assisted document analysis for informational purposes.<br/>Not a substitute for professional legal advice.</p></section></main>;
}
