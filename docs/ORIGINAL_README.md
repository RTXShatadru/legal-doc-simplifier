# SimplyDoc — Legal Document Simplifier

A complete first-stage SaaS MVP built from the supplied starter: React + FastAPI, authenticated document libraries, PDF extraction, plain-language analysis, risky-clause flags, and document-scoped chat with source citations.

**Three explicit modes:** Qwen3 4B via Ollama needs no API key; the local demo works without credentials; the real AI mode uses Gemini Flash-Lite (free tier available) with local retrieval; Voyage semantic retrieval is optional. No model was fine-tuned. Demo output is rules and excerpts, not an AI summary or legal advice.

## Start locally

Requirements: Python 3.11+ and Node.js 22.12+. For scanned PDFs, install Tesseract with Hindi and English models: see [OCR setup](docs/OCR.md). Docker includes these models.

Windows, from this project folder:

    .\start.ps1

macOS/Linux:

    sh start.sh

Open **http://127.0.0.1:8000**, create an account, and choose **Try a sample rental agreement** or upload a PDF. Startup installs dependencies, builds React, and serves the frontend and API together.

The supplied .env.example selects Qwen3 4B through Ollama. See [local AI setup](docs/LOCAL_AI.md) to install the model. For an immediate demo without model installation, set AI_PROVIDER=demo. Demo mode is offline and rule-based with a persistent SQLite database in backend/app_data.db. No default account is created. Without JWT_SECRET, the development signing key changes when the server restarts; documents remain stored, but you must sign in again.

Copy .env.example to .env and set a random JWT_SECRET of at least 32 characters to keep sessions across restarts. Generate one with:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

If shell-script execution is restricted, use the individual commands:

    python -m venv .venv
    .venv\Scripts\python -m pip install -r backend/requirements.lock.txt
    cd frontend-react
    npm ci
    npm run build
    cd ..
    .venv\Scripts\python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000

For frontend development, run the backend and then npm run dev from frontend-react. Vite proxies /api to port 8000; no frontend API key or separate CORS setup is necessary.

## Scanned Hindi documents

SimplyDoc removes scanner watermarks and uses local Hindi/English OCR for image pages. It recognizes property sale deeds and provides bilingual topic search with page citations. Re-upload older documents to run the improved extraction; original PDFs are not retained. Up to 12 scanned pages are supported per upload. Text extraction quality and missing pages appear above the report. Handwritten text, maps and stamp values require checking the original. OCR confidence is an engine score, not a probability of correctness.

Local mode provides excerpts and a document-type overview, not Hindi translation or a complete legal analysis. Configure the AI service below for grounded explanations. Scan text is only sent to external AI/embedding providers when those providers are enabled.

## Use PostgreSQL locally

With Docker Desktop/Engine running:

    docker compose up --build

This runs the app and a PostgreSQL 16 database with pgvector. PostgreSQL data stays in the plainly_db Docker volume. Both ports bind only to localhost. Stop any existing local app on port 8000 first.

To run only the database:

    docker compose up -d db

Then configure DATABASE_URL in .env:

    DATABASE_URL=postgresql://plainly:plainly-local-only@localhost:5432/plainly

The Compose credentials are for local development only. Use a managed secret for hosting. Use a fresh database for this version: the supplied starter's schema is not a migration target.

## Qwen3 4B (selected configuration)

Install Ollama, run `ollama pull qwen3:4b-instruct-2507-q4_K_M`, and use AI_PROVIDER=ollama with EMBEDDING_PROVIDER=local. No key is needed. [Setup, hardware requirements and deployment](docs/LOCAL_AI.md). Qwen3 4B is the default lightweight local model. Set OLLAMA_MODEL to override it. Performance depends on available memory.

## Optional Gemini API analysis

Create a key in [Google AI Studio](https://aistudio.google.com/apikey). Keep the project on the Free tier without enabling billing for free-quota use. Copy .env.example to .env (preserve an existing .env), then set:

    AI_PROVIDER=gemini
    EMBEDDING_PROVIDER=local
    GEMINI_API_KEY=<your own key>
    GEMINI_MODEL=gemini-2.5-flash-lite

Restart the server and re-upload your document for a new AI report. Without a key the explicit local demo remains available. Google OAuth sign-in credentials are separate from the Gemini API key. Never paste keys in chat or frontend code.

The free tier is subject to eligibility and quotas. SimplyDoc cannot determine your project's billing tier and never automatically switches providers, models or billing on quota errors. Wait for quota reset before retrying. Free-tier content may be used to improve Google products; use redacted/sample documents for demos. See [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

Keys stay on the backend. Local retrieval and OCR require no API key. Optional Voyage requires its own key and may incur charges. PostgreSQL is optional locally and required for production.

Voyage uses 1,024-dimensional semantic vectors. The explicit local demo uses 384-dimensional hashed lexical vectors. The database records the embedding profile and refuses a silent switch of model/provider. To change the profile, use a fresh database, or implement a migration that rebuilds and re-embeds every clause. Merely changing an environment variable is insufficient.

Analysis reads all bounded document clauses to reduce the chance of missing a provision. It retrieves matching review patterns from the curated JSON reference set, requests structured output from Gemini, validates its shape and source indices, and verifies every risk quote against the actual clause. Chat retrieves six relevant clauses scoped to the requested, owned document, includes recent questions for follow-up context, and validates citation indices. Citation validation does not prove every interpretation is correct.

## What is included

- Signup, login, HTTP-only session cookies, and logout that revokes existing sessions.
- Google sign-in and explicit linking for existing password accounts; see [Google setup](docs/GOOGLE_SIGN_IN.md).
- Per-user document library, with ownership checks on read, chat, retry and delete.
- PDF upload, Hindi/English OCR, extraction-quality warnings, page references, and bounded clause extraction.
- Overview, key terms, potential risk flags, original extracted text, and cited chat.
- Downloadable plain-text review, including the source text.
- Persistent analysis queue, background processing, failure state, and retry.
- PostgreSQL/pgvector deployment path and SQLite local fallback.
- Ten curated, jurisdiction-neutral risk-review patterns.
- Request limits, quotas, global daily AI-operation caps, strict same-origin browser requests, and security headers.
- Docker, Render Blueprint, Railway configuration, CI, automated tests, and evaluation fixtures.

Original duplicate backend variants and the standalone HTML client were consolidated into one maintained backend and one React frontend. The original user ZIP remains unchanged.

## Deploy on Render

1. Put this project at the root of a Git repository you control and push it.
2. Create a Render Blueprint from render.yaml.
3. Supply GEMINI_API_KEY, VOYAGE_API_KEY, and ALLOWED_ORIGINS. The latter must be the actual HTTPS app origin, for example https://your-service.onrender.com, without a trailing slash.
4. The Blueprint creates a database and generates JWT_SECRET. First startup enables the vector extension before creating its columns.
5. Wait for /api/health to pass. Create an account, upload the sample, wait for Ready, and ask about a deposit. Confirm source citations before inviting others.

The frontend and backend share one origin and Docker image. Production refuses startup without a strong secret, PostgreSQL, and HTTPS allowed origins.

The Blueprint explicitly selects free preview instances. Render's free database expires after 30 days, and free web services can sleep; choose suitable paid resources for ongoing use. AI provider usage is separately billed. See [Render free-service limitations](https://render.com/docs/free) and [Blueprint configuration](https://render.com/docs/blueprint-spec).

## Deploy on Railway

Create a project from the Git repository. Railway detects Dockerfile; railway.toml configures the health check. Add a PostgreSQL service with pgvector installed (for example the pgvector/pgvector:pg16 image with a persistent data volume), then set DATABASE_URL and the production/AI variables described above. Generate a public HTTPS domain and set ALLOWED_ORIGINS to that exact origin. Do not assume a generic PostgreSQL image contains the vector extension.

See [Railway Docker deployment](https://docs.railway.com/builds/dockerfiles) and [configuration as code](https://docs.railway.com/config-as-code/reference).

**Deployment status:** source and configurations are supplied; no public Render/Railway deployment or paid API request has been performed. A hosting account/repository and provider credentials are required to complete that step.

## Tests and evaluation

    .venv\Scripts\python -m pip install pytest
    .venv\Scripts\python -m pytest tests -q
    cd frontend-react
    npm run lint
    npm run build

Unit/API tests use a temporary database and synthetic PDFs. They exercise the real PDF parser, queue, persistence, auth and demo retrieval. Provider tests use mocks, so they do not verify live model quality or provider credentials.

To additionally test a real PostgreSQL/pgvector instance, set TEST_POSTGRES_URL to a disposable database and run tests/test_postgres.py. This test creates unique records and deletes its own users/documents after testing; it also creates the application schema and extension. CI runs it with a fresh pgvector service.

    .venv\Scripts\python evaluation/evaluate.py

The evaluation uses small authored synthetic examples for smoke testing. Its scores are not a legal accuracy benchmark. See docs/DEMO.md for a presentation sequence and docs/ARCHITECTURE.md for the design.

## Limits of this first version

- Educational MVP, not a fully operated commercial SaaS: no billing, email verification, password recovery, teams, or trained LoRA weights.
- PDFs: 10 MB, 80 pages, 120,000 extracted characters and 256 sections maximum. Up to 12 scanned pages use Hindi/English OCR when the engine is installed. Tables, handwriting, signatures, maps and cross-page clauses may require checking the original PDF.
- The source PDF is discarded after extraction. Extracted text, clauses, vectors, results and chat are retained until deletion. Deletion cascades through application tables; hosting backups follow the provider's retention policy.
- Review patterns are authored prompts, not a legal database of current laws. They do not establish illegality or enforceability. The demo's lexical matching can miss synonyms, negation scope, and cross-clause context.
- Exact cosine search is used within each bounded document. Approximate global indexing is unnecessary at this document size and can reduce recall after filtering.
- One application instance / one Uvicorn worker is the supported deployment. Work is persisted in the database. A job interrupted while processing becomes failed after a 15-minute lease and can then be retried. Queued jobs survive restart. Larger deployments should use a dedicated job queue with heartbeat leases and idempotent provider requests.
- Sessions expire after 24 hours; logout invalidates all sessions for that user.
- Limits: 50 stored documents/user; 10 uploads/hour/user; 5 retries/hour/user; 60 chat questions/hour/user. Configurable MAX_ANALYSES_PER_DAY (default 100) and MAX_CHATS_PER_DAY (default 1000) cap service-wide operations in fixed time windows. Invalid/failed attempts can consume quotas. These are request caps, not a currency spending cap.
- Have a qualified reviewer assess your evaluation set and jurisdiction before relying on generated legal interpretations. Verify important statements against the original agreement.

## Primary implementation references

- [Gemini models](https://ai.google.dev/gemini-api/docs/models)
- [Voyage embedding API and dimensions](https://docs.voyageai.com/docs/embeddings)
- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [Render PostgreSQL](https://render.com/docs/postgresql)

Dependency licenses remain their authors' licenses; review them before redistribution, including PyMuPDF's licensing terms.

## Long document reviews

The local model reviews long documents in bounded parts automatically. Progress is shown in the document view. Validated parts are saved and reused on retry, while changed input/model/prompt invalidates those checkpoints. Every source section is covered; the final overview combines part summaries, with original page citations. Non-contract texts such as academic papers receive topic summaries rather than legal risk flags. This does not establish completeness of cross-part reasoning.

## Clerk sign-in

[Enable Clerk authentication](docs/CLERK.md) with your Clerk application keys. The integration supports verified sessions, managed sign-in/sign-up and explicit password-protected linking of existing SimplyDoc document libraries. Existing sign-in remains active until Clerk keys are supplied and AUTH_PROVIDER=clerk is selected.


## Check scanned text before analysis
Scanned uploads pause at **Check extracted text**. Select the original PDF for a browser-only comparison, correct OCR mistakes, mark unreadable wording as [unclear], then choose **Save text and analyze**. Existing documents have a correction button too. Saving clears the old review and chat; original extracted text remains available. Key terms include source quotes and pages, with scanned or uncertain values marked for verification. Quote matching verifies wording, not legal correctness.
