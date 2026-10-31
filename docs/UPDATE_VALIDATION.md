> Inherited base-project documentation. For the unified edition, see [INTEGRATION.md](INTEGRATION.md), [VALIDATION.md](VALIDATION.md), and the root README.

# Frontend and Groq update — validation

- Production frontend build: passed (`npm run build`).
- Frontend lint: passed, no warnings (`npm run lint`).
- Backend: 101 passed, 1 skipped (`python -m pytest tests -q`).
- The skipped check needs a disposable PostgreSQL/pgvector instance via `TEST_POSTGRES_URL`.
- Groq tests use mocked HTTP; no live Groq inference was run without a user API key.
- Browser checks use an isolated SQLite database and fictional sample documents, with the existing explicit local demo mode.
- Verified sign-up, PDF upload/loading, sample review, library search/filter/sort, risk filters, expansion, source navigation, and chat with citations.
- Checked page widths at 320, 390, 768, 1024, and 1440 pixels; no page overflow observed.
- Checked mobile drawer focus, focus wrapping, Escape closure, and return to the navigation trigger.
- No browser console errors were observed during the tested flows.
- No deployment was performed. Google/Clerk and OCR services retain their existing integration and need their own configured environments for end-to-end checks.

Screenshots are local demo previews, not live Groq output. The deliverable excludes temporary accounts, test data, installed dependencies, caches, and real credentials.
