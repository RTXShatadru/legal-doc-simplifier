# Validation record

Validated locally on Windows with Python 3.11 and Node.js. This records what actually ran; it is not a production certification.

- Backend behavior suite: 42 passed (including 24 Google authentication cases).
- Google authentication: RSA signature and token-claim checks, state/nonce/PKCE, single-use browser-bound challenges, signup/login, cancellation, failure states, and explicit linking with document ownership preserved all passed using locally signed tokens and mocked Google transport.
- Real Google consent/login: not run; OAuth credentials and a Google test account must be configured first. The running app reports Google login disabled until configuration is present.
- Real PostgreSQL integration test: supplied but skipped locally because no working PostgreSQL/pgvector server was available. The Docker CLI was installed, but the local engine did not become responsive. CI is configured to run this test against a fresh pgvector container.
- React lint: passed without warnings.
- React production build: passed.
- Docker Compose configuration validation: passed.
- Live HTTP: frontend and health routes returned HTTP 200.
- Live local round trip using the supplied sample PDF: signup, upload, background processing, ready analysis (5 sections, 2 demo flags), cited deposit answer, persisted chat, deletion and logout passed.
- PostgreSQL vector table DDL compilation: passed. This is a syntax/type check, not a replacement for running the real database integration.
- Synthetic rule evaluation: all 14 authored cases matched their expected flags (precision/recall 1.0 on this small rule smoke set). This is not an independent legal-quality benchmark.
- Live Gemini/Voyage calls: not run; no provider key supplied. Structured provider boundaries were exercised with mocks.
- Docker image build and public hosting: not run.
- Browser visual/interaction automation: not run.

The test framework emitted two upstream deprecation warnings concerning Starlette's httpx/AnyIO test adapters; they did not affect the tests.

## Gemini provider update

53 backend tests passed, 1 optional PostgreSQL test skipped. React production build and lint passed. Mocked Gemini HTTP tests cover structured requests, key-in-header handling, untrusted document separation, incomplete/blocked responses, quota/access errors, and error propagation to document analysis and chat. No live Gemini accuracy claim is made without a configured key.

## GPT-OSS 20B adapter

Mocked Ollama requests verify structured responses, document/instruction separation, reasoning exclusion, context limits, concurrency, missing models, incomplete responses and memory errors. Live model inference was not run: Ollama is not installed, and the development laptop had only about 2 GB free RAM.

## Completed local inference verification — September 10, 2026

Ollama 0.33.3 and gpt-oss:20b (MXFP4) installed. Live sample upload, model analysis, two risk flags, cited chat, history and deletion passed. 60 automated tests passed; 1 PostgreSQL test skipped. Typographic quote normalization preserves the exact source substring and still rejects altered facts. The bundled sample PDF now uses wrapped text so clauses are not clipped. The full private Hindi document was not re-benchmarked with GPT-OSS in this check.

## Long-document and Clerk updates

72 tests passed, 1 optional PostgreSQL test skipped; React build and lint passed. The reported 14-page document completed all 81 sections in 11 parts and is stored as a ready academic-paper report. Clerk signed-token, account-linking, rejection, ownership and verified-email tests passed; live Clerk login awaits application keys.


## Scanned-document reliability update

75 tests passed, 1 optional PostgreSQL test skipped. Added strict Hindi quote repair, one bounded validation retry, smaller review parts and output budgets, and request-sized Ollama context allocation. The supplied six-page scan has low-confidence OCR on every page. Live inference encountered five-minute timeouts under severe memory pressure; successful completion is not established by the automated tests.


## Qwen3 and source review

Qwen3 4B Instruct Q4_K_M installed and selected. Added source editing with an optional browser-only original PDF comparison; scanned uploads wait for text review. Editing preserves original extraction and invalidates previous analysis, vectors, checkpoints and chat. Ownership, stale edits, missing sections, OCR gating and invented source quotes are tested. Full suite: 78 passed, 1 optional PostgreSQL test skipped before the final grammar adjustment; 10 focused inference/source tests passed afterward, including the new grammar regression. Frontend build and lint passed. Automatic approval review blocked a separate UI test server, so no end-to-end browser check was completed. A live structured sample passed. Live Hindi document verification is tracked separately.

Live Qwen check: a clean rental clause completed in 15 seconds with a validated source quote; chat returned the correct monthly rent and clause index. The six-page Hindi scan completed one of four parts but failed source-citation validation on the next part after regeneration. It is now awaiting user OCR review; no complete or accurate report is claimed for this scan.


## Ask your document optimization

Chat now uses three relevant passages with a source-byte budget, short history and a 650-token answer budget. Follow-up and explicit section retrieval, missing inline citations, one bounded citation-repair attempt, no-evidence handling and source-revision checks are covered. Search computes document frequencies once. The UI shows pending questions immediately, elapsed time, document-specific starters, multiline input, clickable citations and expandable original passages. Failed drafts are preserved and duplicate sends are blocked. 83 tests passed plus the added focused citation-repair regression; PostgreSQL was skipped. Frontend build and lint passed. A live Qwen question on the stored sale document completed in 32.3 seconds with two valid citation references. This checks citation consistency, not factual or legal accuracy.
