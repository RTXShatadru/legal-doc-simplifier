# Central Indian legal-reference library

After a document finishes analysis, open **Legal references**. Search by topic or a named provision, such as `IPC 420`, `BNS 318(4)`, `TPA 54`, `Registration Act 49`, or `Indian Contract Act 19`. Use **Browse full collection** to see the selected library. The feature works with existing completed documents; re-uploading is unnecessary.

**Ask about this** opens Document chat with a draft question and central-law mode enabled. Review the draft and send it. The chatbot can also use the **Include central Indian law references** checkbox. With that checkbox off, the original document-only chat remains available. Conversations save document citations and legal references separately.

## Coverage

Version `2026-10-31.1` contains 35 edited summaries:

| Act | Included sections |
| --- | --- |
| IPC, 1860 — historical | 405, 415, 420, 423, 441, 463, 464, 467, 468, 471 |
| BNS, 2023 | 316, 318, 318(4), 322, 329, 335, 336, 336(3), 338, 340, 358 |
| Transfer of Property Act, 1882 | 54, 55, 58, 59, 105, 107, 122, 123 |
| Registration Act, 1908 | 17, 49 |
| Indian Contract Act, 1872 | 10, 17, 18, 19 |

This is a central-only starter library, not a complete copy of the IPC or every law relevant to legal documents. State amendments, land-revenue rules, tenancy legislation, stamp rates, local rules, personal-law details, case law and automatic legislative updates are outside its scope. A missing match does not mean no law applies. Summaries are paraphrases, never presented as verbatim statutory text. Document wording, OCR and generated interpretations require verification.

IPC references are historical. BNS commenced on 1 July 2024 subject to the notification's exception; BNS section 358 preserves specified matters under the repealed IPC. The date of the alleged conduct and relevant savings matter, not the date of upload or simply the deed's date. The period selector is a research filter, not a legal determination. Explicitly requested sections remain visible even when outside that filter. Corresponding provisions are not necessarily identical in wording or punishment.

## Sources and maintenance

The source text was checked on **31 October 2026**. This is an access/check date, not a claim that every source is a fully current consolidated statute. The JSON catalog records source URLs, source notes, snapshot SHA-256 hashes, related entries and a library version. Reference copies may be historical or unversioned; verify current official legislation before relying on a summary. The local hashes identify the copies reviewed during development; they do not certify legal currency.

- [IPC reference text — Delhi District Courts](https://session.delhi.gov.in/session/indian-penal-code). Selected physical-document summaries; the hosted historical copy is not a versioned consolidation of all amendments.
- [BNS reference text — NCRB](https://www.ncrb.mha.gov.in/uploads/SankalanPortal/ChaptersBNS.html).
- [Corresponding IPC/BNS sections — NCRB](https://www.ncrb.mha.gov.in/uploads/SankalanPortal/SectionTableBNS.html). Cross-references identify corresponding provisions, not identical offences or penalties. For example, IPC 420 corresponds to BNS 318(4), and IPC 468 to BNS 336(3).
- [BNS section 1 commencement footnote — India Code](https://www.indiacode.nic.in/indiacode/bitstream/123456789/20062/1/a202345.pdf), citing notification S.O. 850(E) of 23 February 2024. The former standalone MHA notification URL returned 404 during integration; the interface links to the official act's commencement note instead.
- [Transfer of Property Act — Delhi District Courts](https://session.delhi.gov.in/session/transfer-property-act).
- [Registration Act section 17 — Delhi Revenue](https://revenue.delhi.gov.in/sites/default/files/revenue/act/part_iii.pdf#page=1), central text on PDF pages 1–3.
- [Registration Act section 49 — Delhi Revenue](https://revenue.delhi.gov.in/sites/default/files/revenue/act/part_x.pdf#page=2), central text and proviso on PDF page 2. State amendments and publisher commentary in these hosted files are excluded.
- [Indian Contract Act — India Code](https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf).

For updates, review the primary text, applicable commencement and amendment history with a qualified reviewer. Edit `backend/legal_knowledge.json`, preserve important exceptions, update source hashes/notes and the version, then run the legal and chat tests. Do not append AI-generated section numbers without verification. No external vector database or additional API key is required.

## Implementation and checks

`backend/legal_knowledge.py` retrieves curated records using named sections and topic keywords. Automatic document suggestions require matching source wording; ordinary sale or lease language does not by itself trigger criminal references. Topic matches may include negations or allegations, so they are explicitly labelled as research leads, not applicability findings.

The authenticated `/api/documents/{id}/legal-references` endpoint requires ownership and completed analysis. Chat with `include_law: true` retrieves up to three law records and bounded document excerpts. Statutory section numbers are parsed separately from document clauses. The model receives only these records and must return allowed law IDs and document indices. The backend rejects unsupported IDs and inline markers, resolves URLs from the catalog, and saves both source types. This validates the citation identity, not the correctness of every generated interpretation.

Questions outside the collection receive a coverage explanation without generating unsupported legal claims. The default law date is unknown; dates are never inferred from upload metadata. Historical conversations retain their catalog version so old references can be identified. Law follow-ups reload records from the current catalog rather than trusting cached model text.

Tests cover exact section lookup, period filters, ordinary property wording, source provenance, missing sections, ownership/readiness, mixed citations, unsupported citations, saved history, library searches and draft handoff to chat. Existing document chat, authentication and domain tests remain in place.
