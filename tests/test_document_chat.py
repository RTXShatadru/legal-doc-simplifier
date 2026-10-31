"""Document Q&A stays scoped to the account, source revision and chosen workspace."""
import pytest
from sqlalchemy import update
from test_app import client, signup, pdf_bytes, db, main, config, llm
import domain_service


@pytest.mark.parametrize('domain,workflow,guardrail', [
    ('property', 'review', 'enforceability'),
    ('finance', 'review', 'financial decision'),
    ('hr', 'review', 'whether the user should sign'),
    ('hr', 'resume', 'hiring recommendations'),
    ('medical', 'review', 'Do not diagnose'),
    ('court', 'review', 'Copy stated deadline wording exactly'),
])
def test_chat_in_every_workspace_is_grounded_and_private(client, monkeypatch, domain, workflow, guardrail):
    signup(client)
    response = client.post('/api/documents/upload', data={'domain':domain, 'workflow':workflow},
        files={'file':('example.pdf', pdf_bytes(), 'application/pdf')})
    doc_id = response.json()['doc_id']
    assert client.post(f'/api/documents/{doc_id}/chat', json={'message':'Explain section 1'}).status_code == 409
    assert db.chat_history(doc_id) == []
    assert db.claim_job() == doc_id
    main.run_analysis(doc_id)
    assert domain_service.get(domain, workflow)['features']['chat'] is True
    monkeypatch.setattr(config, 'AI_PROVIDER', 'groq')

    def generate(system, payload, schema, max_tokens):
        assert schema is llm.ChatAnswer
        assert guardrail in system
        assert 'Return at most 2 key terms' not in system
        assert 'History helps resolve follow-up questions; it is not evidence.' in system
        assert 'review_references' not in payload
        section = payload['clauses'][0]
        return {'answer':f"The source states: {section['text']} [{section['clause_index'] + 1}]",
                'clause_indices':[section['clause_index']]}

    monkeypatch.setattr(llm, 'call_json', generate)
    answer = client.post(f'/api/documents/{doc_id}/chat', json={'message':'Explain section 1 in plain language.'})
    assert answer.status_code == 200, answer.text
    source = answer.json()['sources'][0]
    assert source['clause_index'] == 0 and source['page'] == 1
    history = client.get(f'/api/documents/{doc_id}/chat').json()
    assert [m['role'] for m in history] == ['user', 'assistant']
    assert history[-1]['sources'] == answer.json()['sources']
    client.post('/api/auth/logout')
    signup(client, 'other-chat-user@example.test')
    assert client.get(f'/api/documents/{doc_id}/chat').status_code == 404
    assert client.post(f'/api/documents/{doc_id}/chat', json={'message':'Explain section 1'}).status_code == 404


@pytest.mark.parametrize('status', ['queued', 'processing', 'failed', 'needs_review'])
def test_chat_requires_completed_analysis(client, monkeypatch, status):
    signup(client)
    doc_id = client.post('/api/documents/upload', data={'domain':'hr', 'workflow':'resume'},
        files={'file':('resume.pdf', pdf_bytes(), 'application/pdf')}).json()['doc_id']
    with db.engine.begin() as conn:
        conn.execute(update(db.documents).where(db.documents.c.id == doc_id).values(status=status))
    monkeypatch.setattr(llm, 'answer_question', lambda *a:pytest.fail('Unready documents must not call inference'))
    assert client.post(f'/api/documents/{doc_id}/chat', json={'message':'Explain section 1'}).status_code == 409
    assert db.chat_history(doc_id) == []


@pytest.mark.parametrize('question', ['Explain that more simply.', 'Which section supports that?'])
def test_followup_uses_current_document_sources_not_assistant_claims(monkeypatch, question):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'groq')
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:[])
    current = {'clause_index':4, 'page':2, 'text':'Notice must be provided 30 days in advance.'}
    monkeypatch.setattr(db, 'get_clauses', lambda doc_id:[current] if doc_id == 'selected-document' else [])
    monkeypatch.setattr(db, 'get_context', lambda *a:{'domain':'hr', 'workflow':'review'})
    monkeypatch.setattr(db, 'get_extraction', lambda *a:{})
    history = [
        {'role':'user', 'content':'What notice is stated?'},
        {'role':'assistant', 'content':'An outdated answer.', 'sources':[
            {'clause_index':4, 'page':99, 'text':'Stale or altered quotation.'},
            {'clause_index':900, 'page':1, 'text':'An unrelated document.'},
        ]},
    ]

    def generate(system, payload, schema, max_tokens):
        assert payload['clauses'] == [current]
        assert payload['allowed_citations'] == [{'marker':'[5]', 'clause_index':4}]
        return {'answer':'The notice period is 30 days. [5]', 'clause_indices':[4]}

    monkeypatch.setattr(llm, 'call_json', generate)
    answer, sources = llm.answer_question('selected-document', question, history)
    assert '[5]' in answer and sources == [current]


def test_explicit_followup_section_takes_priority_over_previous_sources(monkeypatch):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'demo')
    sections = [{'clause_index':0, 'page':1, 'text':'An earlier topic.'},
                {'clause_index':1, 'page':2, 'text':'A separately requested topic.'}]
    monkeypatch.setattr(db, 'get_clauses', lambda *a:sections)
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:pytest.fail('Explicit section lookup is sufficient'))
    _, sources = llm.answer_question('selected-document', 'Explain this section 2.',
        [{'role':'assistant', 'content':'Previous answer [1]', 'sources':[sections[0]]}])
    assert sources == [sections[1]]


def test_large_unicode_section_uses_relevant_bounded_excerpt_with_original_citation(monkeypatch):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'groq')
    text = ('संपत्ति का अन्य विवरण यहाँ दिया गया है। ' * 1000
            + '\nThe security deposit is refundable within thirty days after inspection.\n'
            + 'संपत्ति का अतिरिक्त विवरण। ' * 1000)
    source = {'clause_index':7, 'page':4, 'text':text}
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:[source])
    monkeypatch.setattr(db, 'get_context', lambda *a:{'domain':'property', 'workflow':'review'})
    monkeypatch.setattr(db, 'get_extraction', lambda *a:{})

    def generate(system, payload, schema, max_tokens):
        excerpts = payload['clauses']
        assert sum(len(c['text'].encode('utf-8')) for c in excerpts) <= 4500
        excerpt = excerpts[0]
        assert excerpt['is_excerpt'] is True
        assert excerpt['excerpt_start'] > 0
        assert excerpt['text'] == text[excerpt['excerpt_start']:excerpt['excerpt_end']]
        assert 'security deposit is refundable within thirty days' in excerpt['text']
        assert '\ufffd' not in excerpt['text']
        assert 'partial' in payload['source_scope']
        assert 'Do not claim to have reviewed the complete section' in system
        assert payload['allowed_citations'] == [{'marker':'[8]', 'clause_index':7}]
        return {'answer':'The deposit is refundable within thirty days after inspection. [8]', 'clause_indices':[7]}

    monkeypatch.setattr(llm, 'call_json', generate)
    answer, sources = llm.answer_question('selected-document', 'When is the security deposit refundable?', [])
    assert '[8]' in answer and sources[0]['clause_index'] == 7 and sources[0]['page'] == 4
    assert sources[0]['is_excerpt'] is True
    assert source['text'] == text and 'is_excerpt' not in source


def test_multiple_large_chat_sources_share_total_utf8_budget(monkeypatch):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'demo')
    sources = [{'clause_index':i, 'page':i+1, 'text':('जमा deposit refundable return. ' * 500)} for i in range(3)]
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:sources)
    _, excerpts = llm.answer_question('selected-document', 'Explain the deposit', [])
    assert len(excerpts) == 3
    assert sum(len(c['text'].encode('utf-8')) for c in excerpts) <= 4500
    assert all(c['is_excerpt'] for c in excerpts)
    assert [c['clause_index'] for c in excerpts] == [0, 1, 2]


def test_repeated_generic_followups_keep_current_long_section_evidence(monkeypatch):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'groq')
    text = 'अन्य संपत्ति विवरण। ' * 1000 + 'The deposit is refundable after thirty days. ' + 'अतिरिक्त विवरण। ' * 1000
    source = {'clause_index':7, 'page':4, 'text':text}
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:[source])
    monkeypatch.setattr(db, 'get_clauses', lambda *a:[source])
    monkeypatch.setattr(db, 'get_context', lambda *a:{'domain':'property', 'workflow':'review'})
    monkeypatch.setattr(db, 'get_extraction', lambda *a:{})
    seen = []

    def generate(system, payload, schema, max_tokens):
        excerpt = payload['clauses'][0]
        assert 'The deposit is refundable after thirty days.' in excerpt['text']
        assert text[excerpt['excerpt_start']:excerpt['excerpt_end']] == excerpt['text']
        assert len(excerpt['text'].encode('utf-8')) <= 4500
        seen.append(excerpt)
        return {'answer':'The deposit is refundable after thirty days. [8]', 'clause_indices':[7]}

    monkeypatch.setattr(llm, 'call_json', generate)
    history = []
    for question in ['When is the deposit refundable?', 'Explain that more simply.', 'Which section supports that?', 'What does that mean?']:
        answer, sources = llm.answer_question('selected-document', question, history)
        history.extend([{'role':'user','content':question}, {'role':'assistant','content':answer,'sources':sources}])
    assert len(seen) == 4 and all(excerpt == seen[0] for excerpt in seen)


def test_new_topic_with_this_does_not_get_displaced_by_old_sources(monkeypatch):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'demo')
    prior = [{'clause_index':i, 'page':1, 'text':'Old topic '+str(i)} for i in range(3)]
    salary = {'clause_index':3,'page':2,'text':'Salary is INR 600000 per annum.'}
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:[salary])
    monkeypatch.setattr(db, 'get_clauses', lambda *a:prior + [salary])
    _, sources = llm.answer_question('selected-document', 'What salary does this document state?',
        [{'role':'user','content':'Explain the old topic'}, {'role':'assistant','content':'Old topic','sources':prior}])
    assert sources[0] == salary


def test_prior_excerpt_offsets_cannot_restore_stale_source_text(monkeypatch):
    monkeypatch.setattr(config, 'AI_PROVIDER', 'demo')
    source = {'clause_index':0,'page':1,'text':'Current notice period is thirty days.'}
    cached = dict(source, text='Stale notice period is ninety days.', is_excerpt=True, excerpt_start=0, excerpt_end=35)
    monkeypatch.setattr(db, 'retrieve', lambda *a, **kw:[])
    monkeypatch.setattr(db, 'get_clauses', lambda *a:[source])
    _, sources = llm.answer_question('selected-document', 'Explain that more simply.',
        [{'role':'assistant','content':'Stale answer','sources':[cached]}])
    assert sources == [source]
