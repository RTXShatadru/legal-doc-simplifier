import {useEffect,useState} from "react";
import {ClerkProvider,SignIn,useAuth,useClerk} from "@clerk/react";
import App from "./App";
import {api,setTokenGetter} from "./api";
import {Brand} from "./components/Icon";

function ClerkWorkspace(){
  const {isLoaded,isSignedIn,userId,getToken}=useAuth();
  const {signOut}=useClerk();
  const [ready,setReady]=useState(false),[error,setError]=useState(null),[password,setPassword]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{
    let active=true;
    setTokenGetter(getToken);
    if(isLoaded&&isSignedIn)api.me().then(()=>{if(active)setReady(userId);}).catch(e=>{if(active)setError(Object.assign(e,{userId}));});
    return()=>{active=false;setTokenGetter(null);};
  },[getToken,isLoaded,isSignedIn,userId]);
  async function link(e){
    e.preventDefault();setBusy(true);
    try{await api.linkClerk(password);setPassword("");setReady(userId);setError(null);}
    catch(err){setError(Object.assign(err,{userId}));}finally{setBusy(false);}
  }
  const failure=error?.userId===userId?error:null;
  if(!isLoaded)return <div className="full-loading"><Brand/><p>Loading secure sign-in…</p></div>;
  if(!isSignedIn)return <div className="clerk-screen"><Brand/><SignIn routing="hash" fallbackRedirectUrl="/"/></div>;
  if(ready===userId)return <App key={userId} onSignOut={()=>signOut({redirectUrl:"/"})}/>;
  return <div className="clerk-screen"><Brand/>{failure?<section className="card"><h2>{failure.status===409?"Connect your existing documents":"Could not open your workspace"}</h2><p role="alert">{failure.message}</p>{failure.status===409&&<form onSubmit={link}><label htmlFor="legacy-password">Original SimplyDoc password</label><input id="legacy-password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required maxLength={128}/><button className="button primary" disabled={busy}>{busy?"Connecting…":"Link existing account"}</button></form>}<button className="text-button" onClick={()=>signOut({redirectUrl:"/"})}>Sign out</button></section>:<p>Opening your workspace…</p>}</div>;
}

export default function AuthRoot(){
  const [settings,setSettings]=useState(null),[error,setError]=useState("");
  useEffect(()=>{api.providers().then(setSettings).catch(e=>setError(e.message));},[]);
  if(error)return <div className="full-loading"><Brand/><p role="alert">{error}</p><button onClick={()=>window.location.reload()}>Retry</button></div>;
  if(!settings)return <div className="full-loading"><Brand/><p>Loading SimplyDoc…</p></div>;
  if(settings.auth_provider!=="clerk")return <App/>;
  return <ClerkProvider publishableKey={settings.clerk_publishable_key} afterSignOutUrl="/"><ClerkWorkspace/></ClerkProvider>;
}
