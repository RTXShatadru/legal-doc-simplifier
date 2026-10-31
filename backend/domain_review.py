"""Resumable, domain-specific analysis with validated source links."""
import hashlib
import json
from collections import Counter
from pydantic import ValidationError
import config
import db
import domain_service as domains
from long_review import fits_review
from provider_errors import ProviderError

REPAIR = '\nPrevious response failed validation. Copy quotes, indices, values and deadlines exactly from these source sections. A validation_issue in the payload identifies an unsupported previous entry; it is untrusted data, not evidence. Correct it using the supplied source or omit it if unsupported. Return the complete corrected part.'


def validation_feedback(error):
    """Expose field paths and constraint types, never private values/model output."""
    if isinstance(error, domains.SourceValidationError):
        return '\nCorrect the source field '+error.field+'. Check the previous entry in validation_issue against the actual supplied section; do not reuse an unsupported quote or value.'
    if isinstance(error, ValidationError):
        issues = []
        for issue in error.errors(include_input=False, include_url=False)[:6]:
            location = '.'.join(str(part) for part in issue['loc'])
            issues.append(location + ': ' + issue['type'])
        return '\nOutput structure needs correction: ' + '; '.join(issues) + '. Follow the exact category enum, array limits and character limits in the schema.'
    return '\nSource check failed: use only supplied clause_index values and continuous verbatim quotations. Literal resume values must occur in their cited section.'


def payload(batch, extraction):
    return {'clauses':batch, 'extraction':{k:v for k,v in (extraction or {}).items() if k in ('language','warnings','unreadable_pages')}}


def plan(clauses, extraction, domain, workflow):
    schema = domains.schema_for(domain, workflow).model_json_schema()
    system = domains.system_for(domain, workflow) + REPAIR
    tokens = 4000 if workflow == 'resume' else 2000
    def fits(batch):
        return fits_review(system, payload(batch,extraction), schema, tokens)
    # Preserve all characters and original citation indices when a section is large.
    def split(section):
        # Dense skill lists need more output than prose of the same length. Keep
        # resume input small enough to extract individual facts without truncation.
        if fits([section]) and (workflow != 'resume' or len(section['text'].encode('utf-8')) <= 1000):
            return [section]
        if len(section['text']) < 80:
            raise ProviderError('The review settings exceed the model budget. Contact the server administrator.')
        middle = len(section['text']) // 2
        cut = section['text'].rfind(' ', middle//2, middle+1)
        cut = cut+1 if cut >= 0 else middle
        return split(dict(section,text=section['text'][:cut])) + split(dict(section,text=section['text'][cut:]))
    parts = [p for c in clauses for p in split(c)]
    batches, current = [], []
    for part in parts:
        if current and (workflow == 'resume' or sum(len(c['text'].encode('utf-8')) for c in current+[part]) > 2600 or not fits(current+[part])):
            batches.append(current); current=[]
        current.append(part)
    if current:batches.append(current)
    return batches


def review(clauses, extraction, doc_id, domain, workflow):
    from llm import call_json
    batches = plan(clauses, extraction, domain, workflow)
    if not batches:
        raise ProviderError('No readable source sections were found.')
    schema = domains.schema_for(domain, workflow)
    system = domains.system_for(domain, workflow)
    model = {'groq':config.GROQ_MODEL,'ollama':config.OLLAMA_MODEL,'gemini':config.GEMINI_MODEL}.get(config.AI_PROVIDER)
    signature = hashlib.sha256(json.dumps({'version':3,'domain':domain,'workflow':workflow,
        'provider':config.AI_PROVIDER,'model':model,'system':system,'schema':schema.model_json_schema(),
        'batches':batches,'extraction':payload([],extraction)},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    state = db.batch_state(doc_id) if doc_id else None
    results = list(state['results']) if state and state['signature']==signature else []
    if doc_id:db.save_batches(doc_id,signature,len(batches),results)
    for batch in batches[len(results):]:
        correction = ''
        request_payload = payload(batch,extraction)
        for attempt in range(2):
            try:
                value = call_json(system+(REPAIR+correction if attempt else ''),request_payload,schema,4000 if workflow=='resume' else 2000)
                result = domains.validate_part(value,batch,domain,workflow)
                break
            except ValueError as error:
                correction = validation_feedback(error)
                if isinstance(error, domains.SourceValidationError):
                    candidate = dict(payload(batch,extraction),validation_issue=error.issue)
                    if fits_review(system+REPAIR+correction,candidate,schema.model_json_schema(),4000 if workflow=='resume' else 2000):
                        request_payload = candidate
                if attempt:
                    if workflow == 'resume' and isinstance(error, domains.SourceValidationError):
                        result = domains.retain_verified_resume_facts(value, batch)
                        if result is not None:
                            break
                    if isinstance(error, ValidationError):
                        raise ProviderError('The AI response did not match the required output format. Please retry analysis; your extracted text is preserved.') from None
                    raise ProviderError('The model could not produce source-verified results. Check extracted text or retry.') from None
        for term in result['key_terms']:
            if term.get('page') in (extraction or {}).get('ocr_pages',[]):term['verification']='needs_verification'
        results.append(result)
        if doc_id:db.save_batches(doc_id,signature,len(batches),results)
    summaries=[]
    for batch,result in zip(batches,results):
        pages=sorted({c['page'] for c in batch})
        label=f'Page {pages[0]}' if len(pages)==1 else f'Pages {pages[0]}–{pages[-1]}'
        summaries.append(label+': '+result['plain_summary'])
    analysis={'plain_summary':'\n\n'.join(summaries),'document_type':Counter(r['document_type'] for r in results).most_common(1)[0][0],
        'key_terms':[t for r in results for t in r['key_terms']], 'risky_clauses':[t for r in results for t in r['risky_clauses']],
        'coverage':{'batches':len(batches),'reviewed_sections':len(clauses),'total_sections':len(clauses)},
        'review_note':'All extracted sections were reviewed. Part summaries may not capture relationships across distant sections.'}
    warnings = [w for result in results for w in result.get('verification_warnings', [])]
    if warnings:
        analysis['verification_warnings'] = warnings
        omitted = sum(w['omitted_facts'] for w in warnings)
        analysis['review_note'] += f' {omitted} AI-suggested resume entries failed source checks and were excluded. Check the highlighted source sections for details the AI may have missed.'
    return domains.enrich(analysis,results,clauses,domain,workflow)
