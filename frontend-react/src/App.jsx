import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import AuthScreen from "./components/AuthScreen";
import UploadZone from "./components/UploadZone";
import DocumentView from "./components/DocumentView";
import DocumentLibrary from "./components/DocumentLibrary";
import { statusLabel } from "./documentUtils";
import Icon, { Brand } from "./components/Icon";
import GoogleButton from "./components/GoogleButton";

function googleNotice() {
  const query = new URLSearchParams(window.location.search);
  const messages = {
    expired: "Your Google sign-in expired. Please try again in this browser.",
    cancelled: "Google sign-in was cancelled. You can try again or use your password.",
    failed: "Google sign-in couldn't finish. Please try again.",
    not_configured: "Google sign-in isn't enabled yet. Please use email and password.",
    email_exists: "This email already has an account. Sign in with your password, then choose Connect Google in your workspace.",
    email_mismatch: "Choose the Google account with the same email as your SimplyDoc account.",
    already_linked: "That Google account is already connected. No account changes were made.",
    conflict: "Another account update happened at the same time. Please try again."
  };
  return query.get("google") === "connected" ? "Google is connected. You can now use it to sign in." : messages[query.get("auth_error")] || "";
}

export default function App({ onSignOut }) {
  const [user, setUser] = useState(null), [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null), [docs, setDocs] = useState([]);
  const [active, setActive] = useState(null), [busy, setBusy] = useState(false), [notice, setNotice] = useState(googleNotice);
  const [providers, setProviders] = useState(null), [linking, setLinking] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false), [docsLoading, setDocsLoading] = useState(true), [docsError, setDocsError] = useState("");
  const uploadLock = useRef(false), menuButton = useRef(null), closeButton = useRef(null), sidebarRef = useRef(null);
  const refresh = useCallback(async () => {
    try { setDocs(await api.listDocuments()); setDocsError(""); }
    catch (e) { setDocsError(e.message); }
    finally { setDocsLoading(false); }
  }, []);
  const expired = useCallback(() => { setUser(null); setDocs([]); setActive(null); setMenuOpen(false); }, []);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has("auth_error") || url.searchParams.has("google")) {
      url.searchParams.delete("auth_error"); url.searchParams.delete("google");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
    api.providers().then(setProviders).catch(() => setProviders({ google: false }));
    api.health().then(setHealth).catch(() => {});
    api.me().then(data => { setUser(data); refresh(); }).catch(e => { if (e.status !== 401) setNotice(e.message); }).finally(() => setLoading(false));
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [expired, refresh]);
  // Keep library statuses fresh when the user leaves a running analysis.
  useEffect(() => {
    if (!user || !docs.some(d => ["queued", "processing"].includes(d.status))) return;
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [docs, user, refresh]);
  useEffect(() => {
    if (!menuOpen) return;
    const trigger = menuButton.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Wait for the drawer transition before focusing a previously hidden control.
    const focusTimer = setTimeout(() => {
      if (!sidebarRef.current?.contains(document.activeElement)) closeButton.current?.focus();
    }, 240);
    function keydown(e) {
      if (e.key === "Escape") setMenuOpen(false);
      if (e.key === "Tab") {
        const items = Array.from(sidebarRef.current.querySelectorAll('button:not(:disabled), a[href]')).filter(el => el.getClientRects().length);
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    }
    const desktop = window.matchMedia('(min-width: 901px)');
    const resized = e => { if (e.matches) setMenuOpen(false); };
    desktop.addEventListener('change', resized);
    window.addEventListener('keydown', keydown);
    return () => { clearTimeout(focusTimer); document.body.style.overflow = previousOverflow; window.removeEventListener('keydown', keydown); desktop.removeEventListener('change', resized); trigger?.focus(); };
  }, [menuOpen]);
  function openDocument(id) { setActive(id); setMenuOpen(false); window.scrollTo({ top: 0 }); }
  function authenticated(data) { setUser(data); setDocsLoading(true); refresh(); api.me().then(setUser).catch(e => setNotice(e.message)); }
  async function connectGoogle() {
    if (linking) return;
    setLinking(true);
    try { const result = await api.startGoogle(true); window.location.assign(result.url); }
    catch (e) { setNotice(e.message); setLinking(false); }
  }
  async function upload(file) {
    if (uploadLock.current) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) { setNotice('Please choose a PDF file.'); return; }
    if (!file.size) { setNotice('This file is empty. Please choose a readable PDF.'); return; }
    if (file.size > 10 * 1024 * 1024) { setNotice('Please choose a PDF smaller than 10 MB.'); return; }
    uploadLock.current = true; setBusy(true); setNotice(''); setMenuOpen(false);
    try { const result = await api.uploadDocument(file); await refresh(); openDocument(result.doc_id); }
    catch (e) { setNotice(e.message); }
    finally { uploadLock.current = false; setBusy(false); }
  }
  async function sample() {
    if (uploadLock.current) return;
    uploadLock.current = true; setBusy(true); setNotice('');
    try { const result = await api.sample(); await refresh(); openDocument(result.doc_id); }
    catch (e) { setNotice(e.message); }
    finally { uploadLock.current = false; setBusy(false); }
  }
  async function logout() {
    try { if (onSignOut) await onSignOut(); else await api.logout(); expired(); } catch (e) { setNotice(e.message); }
  }
  async function remove(id) {
    if (!window.confirm('Delete this document, its analysis, and its chat history? This cannot be undone.')) return;
    try { await api.deleteDocument(id); openDocument(null); await refresh(); }
    catch (e) { setNotice(e.message); }
  }
  if (loading) return <div className="full-loading"><Brand/><span className="spinner"/><p>Opening your workspace…</p></div>;
  const live = ['gemini', 'ollama', 'groq'].includes(health?.ai_provider);
  return <>{!user ? <AuthScreen onAuthenticated={authenticated} health={health} googleAvailable={providers?.google}/> : <div className="shell">
    <a href="#main-content" className="skip-link">Skip to content</a>
    {menuOpen && <div className="sidebar-overlay" onClick={() => setMenuOpen(false)} aria-hidden="true"/>}
    <aside ref={sidebarRef} id="workspace-navigation" className={'sidebar ' + (menuOpen ? 'is-open' : '')} aria-label="Workspace navigation" role={menuOpen ? 'dialog' : undefined} aria-modal={menuOpen || undefined}>
      <div className="sidebar-brand"><Brand/><button ref={closeButton} className="icon-button mobile-only" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><Icon name="close"/></button></div>
      <div className="workspace-label"><span className="workspace-avatar">P</span><div>Personal workspace<small>Make room for clarity</small></div><Icon name="chevron" size={14}/></div>
      <UploadZone compact onFileSelected={upload} busy={busy}/>
      <button className={'library-home ' + (!active ? 'selected' : '')} onClick={() => openDocument(null)}><Icon name="grid"/>All documents <span>{docs.length}</span></button>
      <div className="sidebar-label">RECENT DOCUMENTS <Icon name="clock" size={13}/></div><div className="doc-list">
        {docs.length === 0 && <p className="sidebar-empty">A home for your documents.<br/>Upload one to get started.</p>}
        {docs.slice(0, 12).map(d => <button key={d.id} title={d.filename} className={'doc-item ' + (d.id === active ? 'selected' : '')} onClick={() => openDocument(d.id)}><Icon size={17}/><span className="doc-item-text">{d.filename}<small><i className={'status-dot ' + d.status}/>{statusLabel(d.status)}</small></span></button>)}
      </div><div className="sidebar-bottom">{providers?.google && (user.google_connected ? <p className="google-connected">Google connected</p> : <GoogleButton label="Connect Google" onClick={connectGoogle} busy={linking}/>)}<div className="sidebar-assurance"><Icon name="shield"/><div><strong>A little peace of mind.</strong><span>Your documents belong to your account. You control when to delete them.</span></div></div><div className="user-bar"><span className="user-avatar">{user.email[0].toUpperCase()}</span><div><strong>Personal account</strong><span title={user.email}>{user.email}</span></div><button className="icon-button" aria-label="Sign out" title="Sign out" onClick={logout}><Icon name="exit" size={18}/></button></div></div>
    </aside>
    <div className="workspace" inert={menuOpen || undefined}><header className="topbar"><div className="breadcrumb"><button ref={menuButton} className="icon-button mobile-only" aria-label="Open navigation" aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={() => setMenuOpen(true)}><Icon name="menu"/></button><Icon name="grid" size={16}/><span>Workspace</span><span className="slash">/</span><strong>{active ? 'Document review' : 'All documents'}</strong></div><span className={'mode-pill ' + (live ? 'live' : '')}>{health ? health.ai_provider === 'groq' ? (health.ai_model === 'llama-3.1-8b-instant' ? 'Groq · Llama 8B' : 'Groq AI') : health.ai_provider === 'ollama' ? 'Local AI' : health.ai_provider === 'gemini' ? 'Gemini AI' : 'Local demo' : 'Connecting…'}</span></header>
    {health?.ai_provider === 'ollama' && <div className="extraction-banner provider-banner" role="status"><strong>{health.ai_ready ? 'Local model ready' : 'Local model setup needed'}</strong><p>{health.ai_message}</p><button className="text-button" onClick={() => api.health().then(setHealth).catch(e => setNotice(e.message))}>Check again</button></div>}
    {active ? <DocumentView key={active} docId={active} onReady={refresh} onDelete={remove} onBack={() => openDocument(null)}/> : <DocumentLibrary docs={docs} busy={busy} onUpload={upload} onSample={sample} onOpen={openDocument} health={health} loading={docsLoading} error={docsError} onRefresh={refresh}/>}
    </div></div>}
    {notice && <div className="notice" role="alert"><Icon name="alert" size={19}/><span>{notice}</span><button className="icon-button" aria-label="Dismiss message" onClick={() => setNotice('')}><Icon name="close"/></button></div>}
  </>;
}
