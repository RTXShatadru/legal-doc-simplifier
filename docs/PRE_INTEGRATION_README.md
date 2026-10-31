# SimplyDoc

A responsive document workspace for understanding PDFs, reviewing potentially risky clauses, checking source text, and chatting with citations. This version improves your existing React + FastAPI project and adds **Groq with Llama 3.1 8B** as the selected AI provider.

> This application provides AI-assisted document analysis for informational purposes and is not a substitute for professional legal advice.

## What changed

- A sage and forest-green interface with clear typography and a redesigned sign-in screen.
- Dashboard counts based on your actual documents, search, status filters, and sorting.
- A mobile navigation drawer with keyboard focus management and Escape-to-close.
- Responsive upload, review, source editing, and chat screens.
- Severity filters and expandable source wording/questions in risk cards.
- Upload/loading/error states, disabled duplicate submissions, and processing-status refresh.
- Groq analysis and chat, JSON/schema/source validation, one repair attempt for invalid analysis, and clear provider errors.
- Existing account access, Google/Clerk integrations, OCR review, report export, and deletion remain available.

## Quick start — Windows

Requirements: Python 3.11+ and Node.js 22.12+ (or Node 20.19+). The archive includes the built frontend, but the start script rebuilds it from source.

1. Extract the archive and open a terminal in `legal-doc-simplifier`.
2. Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

3. Open `.env` in your editor and set:

```dotenv
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
EMBEDDING_PROVIDER=local
```

Create a key at [Groq Console](https://console.groq.com/keys). Keep it in the root `.env` on the server. **Never use a `VITE_GROQ_API_KEY` variable or put the key in React.** No Anthropic key is required.

4. Generate a session secret, then paste the result into `JWT_SECRET` in `.env`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

5. Run:

```powershell
.\start.ps1
```

Open [SimplyDoc locally](http://127.0.0.1:8000). Create an account, upload your PDF, or choose **Try a sample document**.

If PowerShell blocks the start script, use these commands without changing your execution policy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
cd frontend-react
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

## macOS / Linux

Copy `.env.example` to `.env`, configure Groq as above, and run:

```sh
sh start.sh
```

Or run the individual commands:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.lock.txt
cd frontend-react
npm ci
npm run build
cd ..
uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

## Frontend development

Keep the backend running on port 8000, then in another terminal:

```sh
cd frontend-react
npm ci
npm run dev
```

Open the URL printed by Vite. Requests to `/api` are proxied to FastAPI. After editing React, run `npm run build` to refresh the frontend served on port 8000. The backend serves `frontend-react/dist`, not the source files.

Styles are divided into `src/styles/base.css`, `workspace.css`, `auth.css`, and `review.css`. The import order in `src/index.css` keeps responsive overrides after the base styles. No extra frontend library was added.

## Groq model and configuration

The selected model is `llama-3.1-8b-instant`, Meta's Llama 3.1 with 8 billion parameters, available on Groq. The older `llama3-8b-8192` model is retired. See [Groq's model documentation](https://console.groq.com/docs/model/llama-3.1-8b-instant) and [deprecations](https://console.groq.com/docs/deprecations).

The server calls Groq's Chat Completions endpoint using the existing `httpx` dependency. Llama 3.1 supports JSON object mode; Pydantic validates the schema and the application checks quotes/citations against source text. Invalid analysis JSON or unsupported source references get one repair attempt. Provider failures are surfaced rather than silently switching to another model.

| Variable | Purpose |
| --- | --- |
| `AI_PROVIDER=groq` | Use Groq for document analysis and chat. |
| `GROQ_API_KEY` | Server-side Groq credential. Required for Groq mode. |
| `GROQ_MODEL=llama-3.1-8b-instant` | Selected 8B model; can be changed to an available Groq model. |
| `EMBEDDING_PROVIDER=local` | Existing local word-based retrieval; no embedding API key needed. |
| `DATABASE_URL` | Optional in development; PostgreSQL required in production. |
| `JWT_SECRET` | Random 32+ character secret for persistent sessions. |
| `ALLOWED_ORIGINS` | Allowed frontend origins, comma separated. |

Groq receives extracted text for analysis and chat. Local retrieval is word-based, not a semantic embedding model. The existing optional Voyage provider supplies semantic retrieval if configured. Chat retrieval is restricted to the current user's document; it sends selected passages, not the entire PDF, for each question. The inherited cloud analysis flow reviews all extracted clauses together, within provider limits. Large files can hit Groq plan token/rate limits; the UI reports that failure and allows a retry or shorter upload. The displayed model badge indicates configuration, not a live credential test.

For an offline UI demonstration, explicitly set `AI_PROVIDER=demo` and restart. Demo mode produces rule-based flags and excerpts and is labeled **Local demo** throughout the interface. It does not produce AI summaries. Existing Gemini and Ollama adapters remain optional; setup for Ollama is in [LOCAL_AI.md](docs/LOCAL_AI.md).

## Database and PDF processing

Development uses SQLite at `backend/app_data.db` by default. Uploaded bytes are discarded after extraction; extracted text, clauses, results, and chat are stored per account. This update does not change the database schema.

PDF upload validates file type, size, and content, then extracts page-aware text using PyMuPDF. The existing limits are 10 MB, 80 pages, and at most 12 scanned pages. Scans require Tesseract with English/Hindi language data; see [OCR setup](docs/OCR.md). OCR text can be checked and corrected before analysis. Unreadable handwriting, maps, signatures, and uncertain figures require reviewing the original document.

For PostgreSQL with pgvector:

```sh
docker compose up -d db
```

Set this development database URL in `.env`:

```dotenv
DATABASE_URL=postgresql://plainly:plainly-local-only@localhost:5432/plainly
```

The database image includes pgvector. The application initializes the extension and schema. Docker's default password is for local development only. To run the whole app and database in Docker after setting Groq in `.env`:

```sh
docker compose up --build
```

## Architecture

```mermaid
flowchart LR
    UI[React / Vite workspace] --> API[FastAPI]
    API --> PDF[PDF validation and PyMuPDF / OCR]
    PDF --> Store[Account-scoped document and clause storage]
    Store --> Analysis[Grounded analysis with risk reference patterns]
    Analysis --> Groq[Groq · Llama 3.1 8B]
    API --> Search[Document-scoped retrieval]
    Search --> Groq
    Groq --> Check[JSON, schema and source checks]
    Check --> UI
```

## Project layout

```text
backend/              API, auth, database, extraction, retrieval, AI providers
  groq_provider.py    Groq adapter, server-side key and safe errors
  llm.py              Grounded prompts, analysis/chat validation and routing
frontend-react/
  src/components/     Sign-in, library, upload, review, risk, chat, source editor
  src/styles/         Base, workspace, authentication, document review styles
  dist/               Production build served by FastAPI
tests/                Existing API tests plus Groq adapter/pipeline tests
docs/                 OCR, authentication, deployment and validation references
.env.example          Groq configuration template; no credentials included
start.ps1 / start.sh  Install dependencies, build frontend, run server
```

## Core API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Database and configured provider status |
| POST | `/api/auth/signup`, `/api/auth/login`, `/api/auth/logout` | Account access |
| GET | `/api/documents` | Current user's library |
| POST | `/api/documents/upload`, `/api/documents/sample` | Upload or sample review |
| GET, DELETE | `/api/documents/{id}` | Review or delete a document |
| POST | `/api/documents/{id}/retry` | Retry failed analysis |
| POST | `/api/documents/{id}/source-review` | Save corrected extracted text |
| GET, POST | `/api/documents/{id}/chat` | Chat history or a grounded question |

## Validation

```sh
cd frontend-react
npm run build
npm run lint
cd ..
python -m pip install pytest
python -m pytest tests -q
```

Groq tests use mocked HTTP and do not spend credits. They check provider routing, JSON schema instructions, credential handling, timeouts/rate-limit errors, source validation/repair, and document-scoped chat. A real Groq key is still needed to verify inference against your account and plan. PostgreSQL integration requires `TEST_POSTGRES_URL`; otherwise that test is skipped.

## Deployment

The included Dockerfile builds React and serves it through FastAPI. On Render, use `render.yaml`; supply `GROQ_API_KEY` and the correct HTTPS `ALLOWED_ORIGINS`. The blueprint selects Groq/Llama 3.1 8B. On Railway, deploy the Dockerfile, add PostgreSQL with pgvector, and configure `APP_ENV=production`, `DATABASE_URL`, a strong `JWT_SECRET`, `AI_PROVIDER=groq`, `GROQ_API_KEY`, `GROQ_MODEL`, and HTTPS origins. Choose persistent database storage. Verify current platform plans before deploying.

Optional account integrations: [Google sign-in](docs/GOOGLE_SIGN_IN.md) and [Clerk](docs/CLERK.md). Never expose database credentials, API keys, or signing secrets through frontend environment variables. Uploaded content is treated as data, and the AI is instructed not to follow instructions found in document text. Keep account ownership checks, source validation, and the legal disclaimer enabled.

The earlier project notes are retained in `docs/ORIGINAL_README.md` for reference; their selected Ollama configuration is superseded by the Groq setup above.
