# Clerk authentication

Clerk manages sign-in, sign-up, email verification, password recovery, Google sign-in (when enabled in your Clerk dashboard), and sign-out. FastAPI verifies Clerk session JWTs and maps the Clerk user ID to the existing local document owner.

## Activate

1. Create an application at https://dashboard.clerk.com. Enable email/password and optionally Google in User & Authentication. Keep personal accounts enabled. Use a development instance for localhost.
2. In this project's .env, set:

       AUTH_PROVIDER=clerk
       CLERK_PUBLISHABLE_KEY=pk_test_...
       CLERK_SECRET_KEY=sk_test_...
       CLERK_ISSUER=https://your-instance.clerk.accounts.dev

   Get the issuer from your Clerk Frontend API URL. All three values must belong to the same Clerk instance. The secret stays on the backend. Do not paste it into chat, source control or Vite environment variables.
3. Restart SimplyDoc. The public key is loaded from the backend at runtime, so no frontend rebuild is needed when changing keys. Set allowed frontend origins in ALLOWED_ORIGINS, including http://127.0.0.1:8000 and/or http://localhost:8000 as appropriate.
4. Sign in through the Clerk form. If your verified primary Clerk email matches an existing SimplyDoc account, enter that account's original password once to link its documents. Matching emails alone never merge accounts. An old Google-only account without a password needs a separately verified administrator migration; it cannot use this password-link flow.

Until keys are configured, leave AUTH_PROVIDER=local to keep the existing sign-in working. Selecting Clerk with missing/mismatched configuration prevents startup; it never silently falls back to password authentication.

## Security and deployment

Clerk mode rejects the legacy sign-up/login/Google OAuth endpoints and local session cookies for document access. Requests carry fresh Clerk bearer tokens. The backend checks RS256 signatures using the configured issuer's JWKS, issuer, expiry, not-before, session/user IDs, authorized origin and pending-session status. Standard short-lived Clerk session tokens are used; revocation may take effect when the current token expires. No custom JWT template is required.

New local accounts require a verified primary email fetched from Clerk's authenticated Backend API. Existing linked accounts are resolved by immutable Clerk subject, not by mutable email. Documents and chat never go to Clerk. Account deletion in Clerk removes access but does not automatically erase documents in SimplyDoc; no deletion webhook is implemented.

For deployment, set AUTH_PROVIDER and the three CLERK_* values on the backend, use your production Clerk instance and configure its domain and Google OAuth credentials. The app's Clerk-mode CSP allows only its configured Clerk frontend origin and documented Clerk image/protection/Cloudflare hosts. Google sign-in availability is controlled by Clerk, not the old GOOGLE_CLIENT_ID variables.

Verified locally with signed-token and mocked-profile tests. A real Clerk sign-in requires your own keys and remains untested until those are configured.

References: https://clerk.com/docs/react/getting-started/quickstart , https://clerk.com/docs/guides/sessions/manual-jwt-verification , https://clerk.com/docs/guides/secure/best-practices/csp-headers
