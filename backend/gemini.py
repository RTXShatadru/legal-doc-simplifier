"""Gemini REST adapter. Credentials and provider bodies never enter app errors."""
import json
import os
import re
import httpx
import config
from provider_errors import ProviderError


def generate(system, payload, schema, max_tokens):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        raise ProviderError('Add GEMINI_API_KEY to the server configuration and restart SimplyDoc.')
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', config.GEMINI_MODEL):
        raise ProviderError('Check the GEMINI_MODEL setting on the server.')
    body = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps(payload, ensure_ascii=False)}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'responseJsonSchema': schema,
                             'maxOutputTokens': max_tokens, 'temperature': 0.2},
    }
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent',
                headers={'x-goog-api-key': key}, json=body)
        if response.status_code == 429:
            raise ProviderError('Gemini usage quota reached. Wait for your free-tier quota to reset, then retry. Check limits in Google AI Studio.')
        if response.status_code in (401, 403):
            raise ProviderError('Gemini access was denied. Check the server API key and project access in Google AI Studio.')
        if response.status_code >= 400:
            raise ProviderError('Gemini could not process this request. Check model availability and server configuration, then retry.')
        data = response.json()
        candidates = data.get('candidates') or []
        if not candidates or candidates[0].get('finishReason') != 'STOP':
            raise ProviderError('Gemini did not return a complete answer. Try a shorter document or question.')
        parts = candidates[0].get('content', {}).get('parts', [])
        answer = ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
        if not answer:
            raise ProviderError('Gemini returned no answer. Please retry.')
        return answer
    except httpx.TimeoutException:
        raise ProviderError('Gemini timed out. Please retry in a moment.') from None
    except httpx.HTTPError:
        raise ProviderError('Cannot reach Gemini. Check the server connection and retry.') from None
    except (ValueError, TypeError, KeyError):
        raise ProviderError('Gemini returned an unreadable response. Please retry.') from None
