# SimplyDoc Unified

One login and dashboard for property, finance, career, medical and court documents.

## Start here

Read [RUN_IN_VSCODE.md](RUN_IN_VSCODE.md). Use Python 3.11+ and Node.js 22.12+.
The default address is **http://127.0.0.1:8002**.

| Workspace | Capabilities | Files |
|---|---|---|
| Property & agreements | Deeds, rentals, terms, flags and source-linked chat | PDF |
| Finance | Loans, fees, repayment terms, glossary and questions | PDF |
| Career & employment | Employment contracts; resume skills, experience, education, projects, certifications and job matching | PDF, DOCX |
| Medical | Reports, printed values/ranges, unclear readings, paperwork and chat | PDF, JPG, PNG, WEBP |
| Court & legal notices | Source-linked actions and exact deadline wording | PDF |

All workspaces share private document history, document chat, status polling, source correction, resumable batches and report export. Resume matching exports structured JSON too. Select the domain before upload; Career has a Resume/Employment switch. All file uploads are limited to 10 MB. PDFs support up to 80 pages, with at most 12 scanned pages.

## Ask about your document

When a document is **Ready to review**, open it and choose **Chat with document** or the **Document chat** tab. Ask a question in English or Hindi, choose a suggested question, or ask for a simpler explanation of the last answer.

Replies include clickable section references and source excerpts. Use **Back to document chat** after checking the original wording. Questions and successful answers are saved separately for each document. Drafts and pending replies stay in place when switching tabs within that document. Correcting extracted text or changing workspaces clears outdated chat along with the analysis.

Chat is available for property, finance, employment, resumes, medical reports and court documents. Answers use selected passages, and long sections are searched for relevant excerpts within a bounded request. They can miss context; verify important details against the original document. Demo mode returns matching excerpts rather than generated answers.

Resume extraction uses small parts to accommodate dense skill lists. Projects, certifications, achievements and languages have separate profile categories. Supported fields retain source citations; PDF line wraps after an existing hyphen are accepted as formatting, with the actual extracted quotation preserved. Invalid output gets a targeted correction attempt, and output-format errors are distinguished from unsupported-source errors.

If a resume suggestion still fails its source check after correction, the review retains only the entries that pass validation. A visible notice lists the affected source sections and the number of excluded suggestions. The affected part's AI summary is replaced with a factual extraction-status message so it cannot repeat rejected claims. Entirely unsupported responses and invalid output formats still fail; other document workflows retain their existing strict validation.

## Central Indian legal references

Open **Legal references** after analysis to search 35 selected provisions from IPC, BNS, the Transfer of Property Act, Registration Act and Indian Contract Act. Entries include edited summaries, official source links, historical IPC labels and corresponding BNS references. **Ask about this** prepares a question in Document chat; send it to clarify the provision alongside relevant document passages.

Use **Include central Indian law references** in chat to enable this mode. The date selector refers to alleged conduct, not the document date. Coverage is central-only and limited: state laws, stamp rates and case law are not included, and topic matches are not legal conclusions. No additional API key is needed. See [docs/LEGAL_KNOWLEDGE.md](docs/LEGAL_KNOWLEDGE.md) for included sections, sources and maintenance.

## AI and authentication

Use a **Groq** API key. The integrated default is `openai/gpt-oss-20b`, not Anthropic or the unavailable Llama model from earlier versions. Set the model according to your account's availability. The local `.env` is excluded from the ZIP. `.env.example` contains placeholders only.

Email/password login is shared across domains. The existing optional Clerk and Google sign-in integrations remain available. No old accounts or private uploads are imported. See [docs/CLERK.md](docs/CLERK.md).

For UI exploration without an API key, set `AI_PROVIDER=demo`. Demo mode displays source excerpts and local rules; it does not generate resume profiles, medical interpretations or job requirements.

## OCR and medical images

Tesseract with Hindi and English language files reads printed scans locally. Correct uncertain extracted text before analysis. Set `TESSERACT_CMD` if Tesseract is not on PATH or in the standard installation folders. The ZIP does not include platform-specific OCR executables.

Optional handwriting transcription uses `MEDICAL_IMAGE_READER=vision` with an explicitly configured `GROQ_VISION_MODEL` that supports image inputs. This sends medical page images to Groq. It is off by default, requires user source review, and must not be used to guess medicine names or doses.

## Architecture

React/Vite → FastAPI → authenticated document store → extraction/source review → domain-specific Groq batches → validated results.

SQLite is the local default. PostgreSQL is supported by the existing persistence layer. `document_context` adds workspace and resume-match metadata without altering older document columns. The original legal-only database can be migrated separately by an administrator; this release starts with an empty library.

## Development and verification

```bash
python -m pip install -r backend/requirements.lock.txt
python -m pip install pytest
python -m pytest tests -q
cd frontend-react
npm ci
npm test
npm run lint
npm run build
```

For separate frontend development run `npm run dev` and a backend at the port configured in `frontend-react/vite.config.js` (8000 by default). The single-server startup script serves the compiled frontend on 8002.

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for source attribution, architecture choices and limitations, and [docs/VALIDATION.md](docs/VALIDATION.md) for checks performed. Docker/Render files are inherited configuration, not proof of a tested deployment. No hosting or paid resources were created.

## Scope

This tool explains documents. It does not provide medical diagnoses, legal determinations, financial recommendations or hiring decisions. Verify important source text and interpretations. Its curated central-law library provides research references, not determinations of IPC/BNS applicability.
