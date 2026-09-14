"""Local model via a local or explicitly configured Ollama server; no cloud fallback."""
import json
from threading import BoundedSemaphore
import httpx
import config
from provider_errors import ProviderError

GATE = BoundedSemaphore(1)


def status():
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            response = client.get(config.OLLAMA_BASE_URL + '/api/tags')
        response.raise_for_status()
        names = {m.get('name') for m in response.json().get('models', [])}
        if config.OLLAMA_MODEL in names:
            return {'ai_model': config.OLLAMA_MODEL, 'ai_ready': True, 'ai_message': 'Local model is installed. Inference speed depends on server memory and GPU.'}
        return {'ai_ready': False, 'ai_message': f'Install the model on the Ollama server: ollama pull {config.OLLAMA_MODEL}'}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return {'ai_ready': False, 'ai_message': f'Start Ollama, then run: ollama pull {config.OLLAMA_MODEL}. See docs/LOCAL_AI.md.'}


def fits(system, payload, schema, max_tokens):
    return len((system + json.dumps(payload, ensure_ascii=False) + json.dumps(schema)).encode('utf-8')) + max_tokens + 512 <= config.OLLAMA_CONTEXT


def context_size(system, payload, schema, max_tokens):
    required = len((system + json.dumps(payload, ensure_ascii=False) + json.dumps(schema)).encode('utf-8')) + max_tokens + 512
    return min(config.OLLAMA_CONTEXT, max(4096, ((required + 2047) // 2048) * 2048))


def grammar_schema(value):
    # Ollama's grammar compiler rejects large bounded string repetitions.
    # Pydantic still enforces the original length limits on the returned JSON.
    if isinstance(value,dict):
        return {k:grammar_schema(v) for k,v in value.items() if k!='maxLength'}
    if isinstance(value,list):
        return [grammar_schema(v) for v in value]
    return value


def generate(system, payload, schema, max_tokens):
    prompt = json.dumps(payload, ensure_ascii=False)
    # UTF-8 bytes conservatively bound tokens; fail explicitly rather than let
    # the runtime silently truncate legal source clauses from a long document.
    if not fits(system, payload, schema, max_tokens):
        raise ProviderError('This document exceeds the local model context budget. Split the PDF into smaller documents and retry; no clauses were silently omitted.')
    if not GATE.acquire(blocking=False):
        raise ProviderError('The local model is processing another request. Please retry after it finishes.')
    try:
        with httpx.Client(timeout=httpx.Timeout(300, connect=5), trust_env=False) as client:
            response = client.post(config.OLLAMA_BASE_URL + '/api/chat', json={
                'model': config.OLLAMA_MODEL,
                **({'think': 'low'} if config.OLLAMA_MODEL.startswith('gpt-oss') else {}),
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
                'format': grammar_schema(schema), 'stream': False, 'keep_alive': '2m',
                'options': {'num_ctx': context_size(system,payload,schema,max_tokens), 'num_predict': max_tokens, 'temperature': 0.2},
            })
        if response.status_code == 404:
            raise ProviderError(f'Local model is not installed. Run ollama pull {config.OLLAMA_MODEL} on the Ollama server.')
        if response.status_code >= 400:
            raise ProviderError('Ollama could not run the local model. Check available RAM/VRAM and the Ollama server logs.')
        data = response.json()
        if data.get('done') is not True or data.get('done_reason') != 'stop':
            raise ProviderError('The local model did not complete its answer. Try a shorter document or question.')
        # Only final content enters the report; thinking is neither stored nor shown.
        answer = data.get('message', {}).get('content', '').strip()
        if not answer:
            raise ProviderError('The local model returned no final answer. Please retry with a shorter request.')
        return answer
    except httpx.TimeoutException:
        raise ProviderError('The local model timed out after five minutes. Free memory, use a stronger inference server, or shorten the document.') from None
    except httpx.HTTPError:
        raise ProviderError('Cannot reach Ollama. Start it and check OLLAMA_BASE_URL on the SimplyDoc server.') from None
    except (ValueError, TypeError, AttributeError):
        raise ProviderError('Ollama returned an unreadable response. Please retry.') from None
    finally:
        GATE.release()
