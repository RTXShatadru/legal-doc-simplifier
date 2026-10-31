> Inherited base-project documentation. For the unified edition, see [INTEGRATION.md](INTEGRATION.md), [VALIDATION.md](VALIDATION.md), and the root README.

# Architecture and design decisions

## Data flow

~~~mermaid
flowchart LR
    U[React browser] -->|HTTP-only session| A[FastAPI API]
    A -->|PDF bytes| P[PyMuPDF parser]
    P -->|Text, clause IDs, pages| D[(PostgreSQL)]
    D -->|Queued document| W[Single background worker]
    W --> E[Voyage embeddings]
    E --> V[(pgvector clause vectors)]
    W --> R[Curated review-pattern retrieval]
    R --> L[Gemini Flash-Lite]
    L --> G[Schema and evidence validation]
    G --> D
    U -->|Question and document ID| A
    A --> O[Verify ownership]
    O --> V
    V -->|Six document-scoped clauses| L
    G -->|Answer and citations| U
~~~

Local demo replaces PostgreSQL with SQLite, Voyage with normalized hashed word vectors, and Gemini with explicitly labelled pattern matching and excerpts. It runs the same auth, upload, persistence, queue, and presentation flow.

## Boundaries

The backend is the trust boundary. Every user-visible document endpoint checks the session and document ownership. Internal retrieval accepts only the already authorized document ID. Users cannot select another person's document through the API.

Uploaded documents and retrieved clauses are untrusted data. They are serialized as JSON in a user message, separate from the fixed system instructions. The model has no tools and no direct filesystem/database access. Results are rendered as React text; the app does not execute returned HTML.

Risk outputs must satisfy a Pydantic schema, cite existing clause indices, and quote text actually present in the cited clause (whitespace-normalized). Chat must refer only to retrieved clause IDs; unsupported inline markers are rejected. These checks reduce fabricated evidence but cannot validate every interpretation or prevent every prompt-injection attempt.

## Schema

- users: ID, normalized email, password hash, session version.
- documents: owner, safe filename, extracted text, page count, queue status, analysis, public-safe error.
- clauses: document ID, index, heading, text, source page, embedding.
- chat_messages: paired user/assistant messages and persisted evidence sources.
- rate_limits: atomic, expiring request counters.
- settings: embedding profile, guarding against incompatible vectors.

Deletion uses foreign-key cascades for clauses and chat. Chat question/answer pairs are saved together only after generation succeeds. A failed request does not leave an orphan question in the history.

## Why RAG first

A first version needs grounded document answers and an inspectable evaluation loop. RAG provides both without requiring a licensed training corpus, GPU training budget, or an unvalidated fine-tune. Gemini Flash-Lite provides the small-model inference path. The implementation can later add an OpenAI-compatible local inference adapter, but this version does not claim Llama/Mistral support or LoRA training.

The overview sees all bounded clauses for coverage. Chat embeds the current and recent questions, retrieves a small set of document-scoped clauses, and supplies a compact reference set. Summaries are stored and reused, rather than regenerated on every browser refresh.

## Google sign-in

The browser starts Google login through a same-origin POST. The server creates a ten-minute state challenge bound to an HTTP-only browser cookie, plus a nonce and PKCE verifier. Google returns an authorization code to a fixed callback. The backend atomically consumes the challenge, exchanges the code with the verifier, and validates the ID token signature against Google's public keys, issuer, audience, expiry, nonce, authorized party and verified email.

Google identities use the stable subject identifier, not an email lookup. A new subject with an existing email is rejected until the account owner signs in and explicitly connects Google. Linking requires the original SimplyDoc session to remain valid and the Google email to match. No Google access or refresh tokens are persisted. Google login issues the same HTTP-only application session as password login.

Two additive tables, google_accounts and oauth_flows, are created at startup without changing existing users or documents. Hosting proxies should redact callback query strings; the included Uvicorn access-log filter does so for the application log.

## Scaling and operations

Deploy the included image with one worker. The database queue survives process restart, with a 15-minute lease for interrupted work. The worker runs inference and parsing off the event loop. A larger installation should move jobs to a dedicated queue, add heartbeat renewal and provider idempotency, add schema migrations and monitoring, and add email recovery/verification.

Exact cosine search with a document filter is deliberate for at most 256 clauses. A global approximate index followed by document filtering can miss results. If the product adds a large corpus search, introduce an index and evaluate recall under tenant filtering.

## Evaluation plan

Measure extraction coverage, risk precision/recall by clause, source-quote fidelity, unsupported-claim rate, retrieval recall@6, latency, and provider token costs separately. Use independently annotated rental and loan contracts from the intended jurisdiction. Keep train/dev/test documents separate if fine-tuning is added. Include safe clauses, exceptions, negations, long agreements and adversarial document instructions. The supplied synthetic evaluation is only a regression smoke test.
