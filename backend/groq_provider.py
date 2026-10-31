"""Groq Chat Completions adapter; API keys and provider bodies stay on the server."""
import json
import os
import time

import httpx

import config
from provider_errors import ProviderError


def generate(system, payload, schema, max_tokens):
    key = os.getenv('GROQ_API_KEY', '').strip()
    if not key:
        raise ProviderError('Add GROQ_API_KEY to the server configuration and restart SimplyDoc.')
    # Llama 3.1 supports JSON object mode. Pydantic enforces the supplied schema
    # after generation; JSON mode alone does not guarantee schema compliance.
    body = {
        'model': config.GROQ_MODEL,
        'messages': [
            {'role': 'system', 'content': system + '\nReturn one JSON object conforming to this JSON schema:\n' + json.dumps(schema)},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
        ],
        'response_format': {'type': 'json_object'},
        'temperature': 0.2,
        'max_completion_tokens': max_tokens,
        'stream': False,
    }
    if config.GROQ_MODEL.startswith('openai/gpt-oss'):
        body['reasoning_effort'] = 'low'
        body['max_completion_tokens'] = max(max_tokens, 2000)
    try:
        with httpx.Client(timeout=httpx.Timeout(90, connect=30)) as client:
            for attempt in range(3):
                try:
                    response = client.post(
                        'https://api.groq.com/openai/v1/chat/completions',
                        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                        json=body,
                    )
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code != 429 or attempt == 2:
                    break
                try:
                    delay = float(response.headers.get('retry-after', '60'))
                except ValueError:
                    delay = 60
                if delay > 60:
                    break
                time.sleep(max(1, delay) + 1)
        if response.status_code == 429:
            raise ProviderError('Groq usage limit reached. Wait for your quota to reset, then retry. Larger documents may need a higher token limit in Groq.')
        if response.status_code in (401, 403):
            raise ProviderError('Groq access was denied. Check GROQ_API_KEY and model access on the server.')
        if response.status_code in (400, 404, 413, 422):
            raise ProviderError('Groq could not process this request. Check GROQ_MODEL or try a shorter document.')
        if response.status_code >= 400:
            raise ProviderError('Groq is temporarily unavailable. Please retry in a moment.')
        choice = response.json()['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ProviderError('Groq did not complete its answer. Try a shorter document or question.')
        answer = choice['message']['content']
        if not isinstance(answer, str) or not answer.strip():
            raise ProviderError('Groq returned no answer. Please retry.')
        return answer.strip()
    except httpx.TimeoutException:
        raise ProviderError('Groq timed out. Please retry in a moment.') from None
    except httpx.HTTPError:
        raise ProviderError('Cannot reach Groq. Check the server connection and retry.') from None
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise ProviderError('Groq returned an unreadable response. Please retry.') from None
