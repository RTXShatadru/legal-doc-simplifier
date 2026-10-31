"""Central-law retrieval, private access and separate document/statute citations."""
from urllib.parse import urlparse
import pytest
from test_app import client, signup, upload, ready, db, main, config, llm
import legal_knowledge as legal


def test_catalog_has_official_provenance_and_no_state_laws():
    assert len(legal.ENTRIES) == 35
    for key, entry in legal.ENTRIES.items():
        assert key == entry['act']+entry['section']
        assert entry['jurisdiction'] == 'India — central law'
        assert urlparse(entry['source_url']).hostname.endswith(('.gov.in','.nic.in'))
        assert len(legal.CATALOG['sources'][entry['source_id']]['sha256']) == 64
        assert all(related in legal.ENTRIES for related in entry['related'])
    assert legal.ENTRIES['IPC420']['related'] == ['BNS318(4)']
    assert legal.ENTRIES['IPC468']['related'] == ['BNS336(3)']
    assert 'collateral transaction' in legal.ENTRIES['REG49']['summary']


@pytest.mark.parametrize('question,expected', [
    ('Explain IPC section 420', ['IPC420']), ('section 420 of the IPC', ['IPC420']),
    ('Indian Penal Code, 1860 section 420', ['IPC420']), ('BNS 318(4)', ['BNS318(4)']),
    ('IPC 420 and 468', ['IPC420','IPC468']), ('TPA 54 and Registration Act 49', ['TPA54','REG49']),
    ('Explain document section 3', []), ('IPC 999', ['IPC999']),
])
def test_exact_statute_recognition(question, expected):
    assert legal.explicit_references(question) == expected


def test_unknown_section_does_not_fall_back_to_unrelated_topic():
    assert legal.lookup('Explain IPC 999 about cheating') == []
    assert legal.lookup('RERA section 13') == []
    assert legal.response('IPC 420 and 999', [], 'unknown', 'all', False)['missing_requested'] == ['IPC999']


def test_ordinary_sale_has_civil_references_without_criminal_accusation():
    clauses = [dict(clause_index=5,page=2,text='The seller transfers property under this sale deed. Registration is required.')]
    result = legal.lookup(clauses=clauses)
    assert {'TPA54','TPA55','REG17'} <= {entry['id'] for entry in result}
    assert not any(entry['act'] in ('IPC','BNS') for entry in result)
    assert all(entry['evidence'][0]['clause_index'] == 5 for entry in result)
    assert not any(entry['act'] in ('IPC','BNS') for entry in legal.lookup('property rights'))


def test_period_filters_do_not_hide_explicit_historical_lookup():
    assert all(entry['act'] != 'IPC' for entry in legal.lookup('cheating',period='after'))
    assert all(entry['act'] != 'BNS' for entry in legal.lookup('cheating',period='before'))
    result = legal.lookup('IPC 420',period='after')
    assert len(result) == 1 and result[0]['status'] == 'historical'
    assert {'IPC','BNS'} <= {entry['act'] for entry in legal.lookup('cheating')}


def test_legal_reference_route_private_and_ready_only(client):
    signup(client)
    doc_id = upload(client)
    path = f'/api/documents/{doc_id}/legal-references'
    assert client.get(path).status_code == 409
    assert db.claim_job() == doc_id
    main.run_analysis(doc_id)
    response = client.get(path,params={'q':'IPC 420','period':'after'})
    assert response.status_code == 200
    assert response.json()['entries'][0]['id'] == 'IPC420'
    assert client.get(path,params={'period':'yesterday'}).status_code == 422
    assert client.get(path,params={'q':'x'*201}).status_code == 422
    client.post('/api/auth/logout'); signup(client,'other-law@example.test')
    assert client.get(path).status_code == 404


def test_legal_chat_statutory_section_is_not_a_document_index(client,monkeypatch):
    doc_id,_ = ready(client)
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    seen = []
    def generate(system,payload,schema,max_tokens):
        assert schema is legal.LegalAnswer
        assert payload['laws'][0]['id'] == 'IPC420'
        assert payload['alleged_conduct_period'] == 'unknown'
        assert 'allegations' in system
        seen.append(payload)
        return dict(answer='Cheating requires the stated deception and dishonest inducement. [LAW:IPC420]',clause_indices=[],law_ids=['IPC420'])
    monkeypatch.setattr(llm,'call_json',generate)
    result = client.post(f'/api/documents/{doc_id}/chat',json={'message':'Explain IPC section 420','include_law':True})
    assert result.status_code == 200, result.text
    source = result.json()['sources'][0]
    assert source['kind'] == 'law' and source['id'] == 'IPC420'
    assert source['url'] == legal.ENTRIES['IPC420']['source_url']
    assert 'conduct date is unknown' in result.json()['answer']
    assert seen
    assert db.chat_history(doc_id)[-1]['sources'] == result.json()['sources']


@pytest.mark.parametrize('answer,indices,ids', [
    ('Unsupported [LAW:IPC999]',[],['IPC999']), ('Unknown marker [LAW:IPC468]',[],['IPC420']),
    ('Missing document [22]',[21],['IPC420']), ('BNS section 318 applies.',[],['IPC420']),
    ('The allegation is in clause\u202f0. [LAW:IPC420]',[],['IPC420']),
])
def test_invented_or_unretrieved_citations_rejected(answer,indices,ids):
    with pytest.raises(ValueError):
        legal.validate_answer(dict(answer=answer,clause_indices=indices,law_ids=ids),[],[legal.ENTRIES['IPC420']],'unknown')


def test_mixed_citations_keep_document_and_law_sources_separate():
    clause = dict(clause_index=2,page=1,text='The deed requires registration.')
    answer,sources = legal.validate_answer(dict(answer='The deed mentions registration [3]. Read the exceptions [LAW:REG49].',
        clause_indices=[2],law_ids=['REG49']),[clause],[legal.ENTRIES['REG49']],'unknown')
    assert sources[0] == clause and sources[1]['kind'] == 'law'
    assert '[3]' in answer


def test_missing_knowledge_abstains_without_provider(client,monkeypatch):
    doc_id,_=ready(client)
    monkeypatch.setattr(llm,'call_json',lambda *a:pytest.fail('No supplied law means no legal generation'))
    response=client.post(f'/api/documents/{doc_id}/chat',json={'message':'Explain IPC 999','include_law':True})
    assert response.status_code == 200
    assert response.json()['sources'] == []
    assert 'not included' in response.json()['answer']


def test_legal_followup_reloads_catalog_not_cached_law_text(monkeypatch):
    monkeypatch.setattr(config,'AI_PROVIDER','demo')
    monkeypatch.setattr(db,'get_clauses',lambda *a:[])
    monkeypatch.setattr(db,'retrieve',lambda *a,**kw:[])
    answer,sources=legal.answer_question('doc','Explain that more simply.',[
        dict(role='assistant',content='Stale answer',sources=[dict(kind='law',id='IPC420',summary='Fake law',url='https://attacker.test')])])
    assert sources[0]['url'] == legal.ENTRIES['IPC420']['source_url']
    assert 'Fake law' not in answer
