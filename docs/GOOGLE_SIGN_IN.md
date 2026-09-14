# Enable Google sign-in for SimplyDoc

The sign-in screen includes **Continue with Google**. Existing users can choose **Connect Google** in their workspace after signing in with their password. The button becomes available once all three server configuration values below are set.

## 1. Create the Google OAuth client

1. Open [Google Cloud Console](https://console.cloud.google.com/) and choose or create your project.
2. Configure the Google Auth Platform consent screen. Use **SimplyDoc** as the app name, add the support/developer contact details, and select the appropriate audience. For a testing app, add the Google accounts that will test it.
3. Create an OAuth client with application type **Web application**.
4. Add this exact **Authorized redirect URI** for the local app:

       http://127.0.0.1:8000/api/auth/google/callback

5. For hosting, add a separate authorized redirect URI using your actual HTTPS domain:

       https://YOUR-APP-DOMAIN/api/auth/google/callback

6. Copy the client ID and client secret into the server environment. The client secret is not a browser key. Do not put it in React, source control, screenshots, or chat.

This implementation uses a server redirect flow, so it does not require a browser Google SDK or an Authorized JavaScript origin. Only the openid and email scopes are requested; no Gmail, Drive, or document access is requested.

See Google's [OpenID Connect guide](https://developers.google.com/identity/openid-connect/openid-connect) and [API reference](https://developers.google.com/identity/openid-connect/reference).

## 2. Configure SimplyDoc

Copy .env.example to .env at the project root if a configuration file does not exist. Preserve any existing settings. Add:

    GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
    GOOGLE_CLIENT_SECRET=your-client-secret
    GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/auth/google/callback

Set a persistent, random JWT_SECRET too if you want existing application sessions to survive server restarts.

Open the local app at **http://127.0.0.1:8000** and restart the backend after configuration changes. Use the same browser hostname as GOOGLE_REDIRECT_URI: localhost and 127.0.0.1 have different cookies. For Google sign-in testing, use the combined app on port 8000, rather than the Vite development origin.

For Render/Railway, put the three values in the service environment and redeploy. Set GOOGLE_REDIRECT_URI to your real HTTPS callback, and ensure that callback's origin is listed in ALLOWED_ORIGINS. Production requires HTTPS. The Render Blueprint declares these as dashboard-managed values; Docker Compose passes them through from .env.

Leave all three variables blank to keep Google sign-in disabled while retaining email/password login. A partially configured set is rejected at startup.

## 3. Verify it with your account

1. Refresh the sign-in page; Continue with Google should be enabled.
2. Click it and select one of your consent-screen test accounts.
3. Approve the requested identity access. You should return to your document library.
4. Sign out, then use Google again. Your existing library should return.
5. To connect an existing password account, sign in with its password and choose Connect Google in the workspace. Select the Google account with the matching email.
6. Try cancelling at Google. SimplyDoc should show a cancellation message and allow another attempt.

If Google rejects an embedded browser, open the app URL in a regular Chrome or Edge window. If Google reports redirect_uri_mismatch, compare the scheme, hostname, port and callback path character-for-character with the Google Cloud client configuration. If the app says the sign-in expired, restart the flow from the button using the configured hostname; challenges last ten minutes and work once.

## Account behavior

- New Google users receive a SimplyDoc account without a local password.
- A Google account is identified by its stable Google subject, even if its Google email later changes. The existing SimplyDoc contact email is retained.
- Matching an existing email does not automatically link accounts. The existing owner must sign in and explicitly connect Google.
- Linking cannot move a Google identity from another SimplyDoc account and does not replace an existing linked identity.
- Password login remains available for existing password accounts after linking.
- Google access/refresh tokens are not stored. SimplyDoc uses its own 24-hour HTTP-only session.
- Recovery, Google disconnect and changing a linked identity are outside this first implementation.
- Existing databases are upgraded additively at startup with two new tables. Existing documents are preserved.

## Security checks implemented

State is bound to a secure browser challenge and consumed atomically. The code exchange uses PKCE S256. The ID token is verified using Google's public signing keys with RS256, plus issuer, audience, expiry, nonce, authorized-party and verified-email checks. Redirects use only the server-configured origin. Callback code/state parameters are removed from Uvicorn's access log; configure equivalent redaction in hosting proxy logs.

## Validation status

Automated tests use real RSA-signed test tokens and mocked Google transport. They cover identity creation, subsequent login, explicit linking, unchanged document access, cancellation, expiration, replay, browser binding, session revocation, token validation and safe errors.

A real Google consent-and-login round trip still requires your OAuth client credentials and a configured test account. It has not been performed in this workspace.

## Branding

The button uses the Google-provided G asset from [Google's branding guidance](https://developers.google.com/identity/branding-guidelines), downloaded from https://developers.google.com/static/identity/images/g-logo.png. Google trademarks remain Google's property.
