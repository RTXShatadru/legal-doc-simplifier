# Integration notes

This is a separate integrated edition of SimplyDoc. The previous project and uploaded archives were not modified. All workspaces now share the existing React/Vite interface, FastAPI server, authenticated session, database, document ownership checks, OCR, source correction, and Groq configuration.

## Source mapping

| Source | Integrated functionality |
|---|---|
| Existing `legal-doc-simplifier` | Shared authentication, property reviews, source-linked chat, OCR, background jobs, resumable analysis, library, report export |
| `clearclause.zip` | Finance, employment, medical and court domain definitions, guardrails, glossary vocabulary, questions/checklists, court actions, category suggestions |
| `resume_scanner.zip` | Structured resume profiles, supplied skill vocabulary, normalized required/preferred skill comparison, JSON export |
| `simplydoc.zip` | Medical reports, reported values and printed ranges, unclear readings, medical chat, image uploads and optional vision transcription |

ClearClause already contained four overlapping domains, so they were merged into one registry rather than duplicated. The final workspaces are Property, Finance, Career & Employment, Medical, and Court. Career contains two workflows: employment-document review and resume scanning/job matching.

## Important implementation choices

- A single cookie session (or the existing optional Clerk integration) covers every workspace. Old databases, uploaded documents and account credentials were not imported. Create an account in the integrated app.
- Uploaded `.env`, credential YAML, databases, sample personal resumes, stored uploads, Chroma data, and virtual environments were excluded from the release. Keep any real credentials supplied in the source archives private and rotate them before sharing those archives elsewhere.
- Resume skill normalization uses the supplied canonical vocabulary plus explicit aliases such as ReactJS → React.js. It does not require downloading sentence-transformer models or shipping the old Chroma database. Unknown skills remain as written. The UI exposes this mapping; it does not present fabricated embedding distances.
- Matching reports required-skill overlap, not candidate ranking or a hiring recommendation. No required skills produces an unavailable score, not a misleading 0%.
- Domain results require valid JSON, source indices and matching quotations. Medical reported values/ranges and court deadlines are checked against the cited text. These checks establish source correspondence, not professional correctness.
- The previous whole-document “missing” claims became a clearly labeled full-document checklist. A topic absent from one batch is not necessarily absent from the full document.
- Suggested categories can be accepted with “Review in that workspace”. This clears old analysis, chat, batches and job matches; OCR review remains required when appropriate.
- Resume contact details and skills must appear verbatim in their cited source. Experience and education summaries still require human verification.
- Document chat is enabled for all domains and both Career workflows. It uses a question-answering prompt rather than the analysis extraction schema. Follow-up questions reload prior cited sections from the same document; long sections provide bounded, relevant excerpts marked as partial. Citation indices link back to the full source section. Successful conversations persist per document and account; drafts and pending replies survive switching review tabs.
- Medical images use local OCR by default. Optional Groq vision uses an explicitly configured image-capable model. It has a mocked adapter test, but was not live-tested because the account's text model is not assumed to support images. No model names are guessed or silently substituted.
- Original pages are not stored. The database stores extracted text and analysis. Image/PDF bytes are discarded after extraction. The source-comparison picker stays in the browser.
- DOCX extraction preserves paragraph/table-cell text, but not Word pagination. Its “page 1” references mean the extracted document body.

## Boundaries

This release integrates document analysis. It does not add a verified Indian statutory database or IPC/BNS applicability engine; that earlier proposal still needs jurisdiction and source curation. It does not diagnose illness, establish title, predict court outcomes, or decide whom to hire.

Groq availability and token limits depend on the account. The configured default is `openai/gpt-oss-20b`; the model is checked through real synthetic requests during integration. Every source section is included in a budgeted batch, with completed batches reused on retry. Cross-section relationships can still be missed by part summaries.

## Validation

See `VALIDATION.md` for the tested paths and remaining limitations. No private document from the input archives was sent for testing. The test documents were invented examples.
