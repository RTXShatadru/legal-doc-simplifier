"""Bounded, resumable reviews; every source section belongs to exactly one batch."""
import hashlib
import json
from collections import Counter
import config
import db
import ollama_provider
from provider_errors import ProviderError

INSTRUCTIONS = '''
Review this part of the document in 1–2 concise sentences. Identify its document type.
For an academic paper or other non-contract document, explain the topic and findings,
use key_terms for important concepts, and return no legal risk flags. For an agreement,
identify obligations and potential concerns using exact source quotes of at most 25 words.
Review every supplied section. An absent term in this part may appear in another part;
never declare it absent from the complete document. Use only supplied clause indices.
Keep at most 2 key terms and 2 risk flags in this part, focusing on the most important.
Extract important names, dates, amounts, property identifiers and obligations as key_terms.
For every key term, include an exact source quote and set uncertain=true if the OCR,
value or interpretation is unclear. Write "Needs verification" for an unreadable value.
Do not guess missing digits, names or dates. A quote match does not prove interpretation.
Base the summary on supported details; keep uncertainty explicit.
Keep each field concise: at most 12 words per explanation, reason, or question.
Write explanations in English, but keep risk quotes in the ORIGINAL source language.
For Hindi OCR, copy the text exactly, including apparent OCR mistakes. Never translate
or correct a quote. If a passage is too unclear to support a concern, explain the
uncertainty in the summary instead of inventing a risk or reconstructing its quote.
'''
TOKENS = 1000
REPAIR = '''
The previous attempt failed JSON or source-citation validation. Generate a fresh review
using the same source sections. Check every clause_index against the supplied indices.
Every risk quote MUST be an exact continuous substring of that indexed section,
in its original language. Never replace Hindi source text with an English translation.
Return complete schema-valid JSON. Do not include unsupported claims or citations.
'''


def payload_for(batch, extraction):
    from llm import reference_set
    # Detailed per-page OCR scores remain in the report; compact warnings suffice for inference.
    quality = {k: extraction[k] for k in ('language','warnings','unreadable_pages') if extraction and k in extraction}
    return {'clauses':batch, 'extraction':quality, 'review_references':reference_set(batch)}


def plan(clauses, extraction=None):
    from llm import SYSTEM, SourcedAnalysis as Analysis
    batches, current = [], []
    for clause in clauses:
        proposed = current + [clause]
        # Bound latency as well as memory, including multibyte Hindi text.
        size = sum(len(c['text'].encode('utf-8')) for c in proposed)
        # A single larger section stays intact if it fits the hard context limit.
        fits = (size <= 1800 or not current) and ollama_provider.fits(SYSTEM+INSTRUCTIONS+REPAIR,payload_for(proposed,extraction),Analysis.model_json_schema(),TOKENS)
        if not fits:
            if not current:
                raise ProviderError('One section exceeds the review budget. Please use a smaller PDF section.')
            batches.append(current)
            current = [clause]
            if not ollama_provider.fits(SYSTEM+INSTRUCTIONS+REPAIR,payload_for(current,extraction),Analysis.model_json_schema(),TOKENS):
                raise ProviderError('One section exceeds the review budget. Please use a smaller PDF section.')
        else:
            current = proposed
    if current:
        batches.append(current)
    return batches


def review_batch(batch, extraction):
    from llm import SYSTEM, SourcedAnalysis as Analysis, call_json, validate_analysis
    for attempt in range(2):
        try:
            return validate_analysis(call_json(SYSTEM+INSTRUCTIONS+(REPAIR if attempt else ''),
                                               payload_for(batch,extraction),Analysis,TOKENS),batch)
        except ValueError:
            # Regenerate once, retaining strict validation. Never publish or cache
            # an ungrounded answer, or log potentially sensitive model output.
            if attempt:
                raise ProviderError('The model could not produce a review with verifiable source citations after two attempts. OCR may be unclear; try a clearer scan or retry analysis.') from None


def review(clauses, extraction=None, doc_id=None):
    from llm import SYSTEM
    batches = plan(clauses, extraction)
    signature = hashlib.sha256(json.dumps({'version':2,'model':config.OLLAMA_MODEL,'system':SYSTEM+INSTRUCTIONS,'batches':batches,'extraction':extraction},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    state = db.batch_state(doc_id) if doc_id else None
    results = list(state['results']) if state and state['signature']==signature else []
    if doc_id:
        db.save_batches(doc_id,signature,len(batches),results)
    for batch in batches[len(results):]:
        result = review_batch(batch,extraction)
        if extraction and extraction.get('ocr_pages'):
            for term in result['key_terms']:
                if term['page'] in extraction['ocr_pages']:
                    term['verification'] = 'needs_verification'
        results.append(result)
        if doc_id:
            db.save_batches(doc_id,signature,len(batches),results)
    types = Counter(r['document_type'] for r in results)
    summaries = []
    for batch, result in zip(batches,results):
        pages = sorted({c['page'] for c in batch})
        summaries.append(f"Pages {pages[0]}–{pages[-1]}: " + result['plain_summary'])
    # Preserve every validated result. Do not apply the single-call schema's list
    # caps to the aggregate or ask a second model call to discard source details.
    return {'plain_summary':'\n\n'.join(summaries) if len(results)>1 else results[0]['plain_summary'],
            'document_type':types.most_common(1)[0][0],
            'key_terms':[t for r in results for t in r['key_terms']],
            'risky_clauses':[t for r in results for t in r['risky_clauses']],
            'coverage':{'batches':len(batches),'reviewed_sections':len(clauses),'total_sections':len(clauses)},
            'review_note':'All extracted sections were reviewed in order. The overview combines part summaries; cross-part implications may need additional review.'}
