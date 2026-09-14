import googleLogo from "../google-logo.png";
export default function GoogleButton({onClick,disabled,busy,label="Continue with Google"}){
  return <button type="button" className="google-button" onClick={onClick} disabled={disabled||busy}>
    <img src={googleLogo} alt="" width="20" height="20"/>
    <span>{busy?"Opening Google…":label}</span>
  </button>;
}
