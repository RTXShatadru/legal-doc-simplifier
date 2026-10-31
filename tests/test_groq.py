"""Groq contract tests use mock HTTP; they never spend API credits."""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import config
import groq_provider
import llm
from provider_errors import ProviderError


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setattr(groq_provider.time, 'sleep', lambda delay: None)
    monkeypatch.setenv('GROQ_API_KEY', 'test-key-not-a-real-credential')
    monkeypatch.setattr(config, 'AI_PROVIDER', 'groq')
    monkeypatch.setattr(config, 'GROQ_MODEL', 'llama-3.1-8b-instant')


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(groq_provider.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def test_groq_sends_json_schema_and_backend_key(groq, monkeypatch):
    def respond(request):
        assert str(request.url) == 'https://api.groq.com/openai/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-key-not-a-real-credential'
        payload = json.loads(request.content)
        assert payload['model'] == 'llama-3.1-8b-instant'
        assert payload['response_format'] == {'type': 'json_object'}
        assert 'JSON schema' in payload['messages'][0]['content']
        assert json.loads(payload['messages'][1]['content']) == {'question': 'Payment date?'}
        assert payload['max_completion_tokens'] == 650
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"answer":"On the fifth.","clause_indices":[0]}'}}]})
    transport(monkeypatch, respond)
    result = llm.call_json('Use only sources.', {'question': 'Payment date?'}, llm.ChatAnswer, 650)
    assert result['clause_indices'] == [0]


@pytest.mark.parametrize('status, wording', [(401, 'access was denied'), (403, 'access was denied'), (429, 'usage limit'), (404, 'GROQ_MODEL'), (400, 'shorter document'), (500, 'temporarily unavailable')])
def test_provider_errors_do_not_expose_response_or_key(groq, monkeypatch, status, wording):
    transport(monkeypatch, lambda request: httpx.Response(status, text='PRIVATE RESPONSE test-key-not-a-real-credential'))
    with pytest.raises(ProviderError, match=wording) as error:
        groq_provider.generate('system', {}, {}, 100)
    assert 'PRIVATE RESPONSE' not in str(error.value)
    assert 'test-key' not in str(error.value)


@pytest.mark.parametrize('body', [{}, {'choices': []}, {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}, {'choices': [{'finish_reason': 'stop', 'message': {'content': None}}]}])
def test_incomplete_or_malformed_provider_envelopes(groq, monkeypatch, body):
    transport(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(ProviderError):
        groq_provider.generate('system', {}, {}, 100)


def test_missing_key_fails_before_network(groq, monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY')
    with pytest.raises(ProviderError, match='GROQ_API_KEY'):
        groq_provider.generate('system', {}, {}, 100)


def test_timeout_is_actionable(groq, monkeypatch):
    def respond(request):
        raise httpx.ReadTimeout('private upstream details', request=request)
    transport(monkeypatch, respond)
    with pytest.raises(ProviderError, match='Groq timed out'):
        groq_provider.generate('system', {}, {}, 100)


@pytest.mark.parametrize('first', ['not JSON', '{"plain_summary":"short"}', None])
def test_analysis_repairs_json_or_fabricated_sources_once(groq, monkeypatch, first):
    valid = {'plain_summary': 'Rent is due before the fifth day of each month.', 'document_type': 'Rental agreement', 'key_terms': [], 'risky_clauses': [{'clause_index': 0, 'risk_level': 'low', 'title': 'Payment deadline', 'reason': 'Keep track of the due date.', 'quote': 'Rent is due before the fifth.', 'question': 'Which payment methods are accepted?'}]}
    bad_quote = {**valid, 'risky_clauses': [{**valid['risky_clauses'][0], 'quote': 'A fabricated fee applies.'}]}
    responses = iter([first if first is not None else json.dumps(bad_quote), json.dumps(valid)])
    calls = []
    def generate(system, *args):
        calls.append(system)
        return next(responses)
    monkeypatch.setattr(groq_provider, 'generate', generate)
    result = llm.analyze_document([{'clause_index': 0, 'text': 'Rent is due before the fifth.', 'page': 2}])
    assert len(calls) == 2 and 'failed validation' in calls[1]
    assert result['model'] == 'llama-3.1-8b-instant'
    assert result['mode'] == 'groq'
    assert result['risky_clauses'][0]['page'] == 2


def test_groq_chat_uses_retrieval_for_selected_document(groq, monkeypatch):
    retrieved = []
    def retrieve(doc_id, query, top_k):
        retrieved.append(doc_id)
        return [{'clause_index': 0, 'text': 'Rent is due on the fifth.', 'page': 3}]
    monkeypatch.setattr(llm.db, 'retrieve', retrieve)
    monkeypatch.setattr(llm.db, 'get_extraction', lambda doc_id: {})
    monkeypatch.setattr(groq_provider, 'generate', lambda *args: '{"answer":"Rent is due on the fifth. [1]","clause_indices":[0]}')
    answer, sources = llm.answer_question('selected-document', 'When is rent due?', [])
    assert retrieved == ['selected-document']
    assert '[1]' in answer and sources[0]['page'] == 3
