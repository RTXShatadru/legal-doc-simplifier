# Unified integration validation

Checked 15 October 2026 on Windows.

- Backend suite: **117 passed, 1 skipped**. The skipped check requires a live PostgreSQL service; SQLite was tested.
- Frontend: production Vite build and oxlint passed.
- Live Groq: synthetic property, finance, employment, medical, court and resume documents all passed schema/source validation using `openai/gpt-oss-20b`.
- Real HTTP workflow: signup, DOCX resume upload, background AI job, profile persistence, job match and saved-match retrieval passed. A synthetic Python/SQL/ReactJS profile compared against required Python/Docker produced 50% overlap, as expected.
- Browser: login, domain routing/filtering, resume profile, live match, JSON/text export, evidence links and mobile drawer keyboard focus passed with no page errors.
- Responsive widths: 320, 390, 768, 1024 and 1440 CSS pixels, with no horizontal document overflow. Desktop, mobile and resume screenshots were inspected.
- API tests cover all five domains, invalid domain/workflow inputs, owner isolation, match invalidation on source edits, cascade deletion, reclassification, exact medical values/ranges, deadline validation, and lossless splitting of large Unicode source sections.
- Optional medical vision: mocked request/response test, uncertainty preservation and image-upload extraction test passed. **No live image-model test** was performed; users must configure an available image-capable model explicitly.
- Windows PowerShell and Git Bash launcher syntax checked. The full first-time installer was not rerun; the integration tests used the installed locked backend dependencies.

## Not verified

PostgreSQL deployment, public hosting, production Clerk/Google sign-in and clinical/legal correctness were not end-to-end verified in this integration. Existing auth tests include mocked Clerk/Google flows. Domain vocabulary is adapted from the supplied source, not an authoritative statutory dataset. Original user data and credentials were not used as test fixtures.

Screenshots show fictional demonstration documents; the release itself starts with an empty library.

## Document chat update

- Backend: **135 passed, 1 skipped**. The skipped test requires PostgreSQL; SQLite was exercised. Regression tests include repeated follow-ups on long Unicode sections, new-topic retrieval and stale-excerpt rejection.

- Chat is enabled in every workspace, including employment and resume review.
- Frontend: 14 DOM component tests passed, including saved history, domain suggestions, source citations, failed-send recovery, document isolation, draft preservation, and pending replies while switching tabs. Production build and lint passed.
- Live Groq smoke checks passed for synthetic resume questions, a follow-up clarification, and a synthetic medical report; cited answers and persisted conversation history were verified through the API. No private document was used.
- Long sections use byte-bounded source excerpts with original citation indices. This update is covered by regression tests for Unicode text, total context size and source integrity.
- Browser automation was unavailable for this update; UI behavior was checked using DOM component tests. Earlier screenshots describe the initial integrated release.
