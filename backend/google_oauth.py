"""Google OpenID Connect authorization-code flow. No Google tokens are persisted."""
import base64
import hashlib
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
import config
import db

BROWSER_COOKIE = 'simplydoc_google_flow'
COOKIE_PATH = '/api/auth/google'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
JWKS_URL = 'https://www.googleapis.com/oauth2/v3/certs'
keys = jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600, timeout=10)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def home_url():
    uri = urlsplit(config.GOOGLE_REDIRECT_URI)
    return f'{uri.scheme}://{uri.netloc}/' if config.google_enabled() else '/'


def begin(response, user=None):
    state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    db.save_oauth_flow({'state_hash': digest(state), 'browser_hash': digest(browser),
        'nonce': nonce, 'verifier': verifier, 'expires_at': time.time() + 600,
        'link_user_id': user['id'] if user else None,
        'session_version': user['session_version'] if user else None})
    response.set_cookie(BROWSER_COOKIE, browser, max_age=600, httponly=True,
                        secure=config.PRODUCTION, samesite='lax', path=COOKIE_PATH)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return AUTH_URL + '?' + urlencode({'client_id': config.GOOGLE_CLIENT_ID,
        'redirect_uri': config.GOOGLE_REDIRECT_URI, 'response_type': 'code',
        'scope': 'openid email', 'state': state, 'nonce': nonce,
        'code_challenge': challenge, 'code_challenge_method': 'S256',
        'access_type': 'online', 'prompt': 'select_account'})


def verify_id_token(token, nonce):
    key = keys.get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=['RS256'], audience=config.GOOGLE_CLIENT_ID,
        issuer=['https://accounts.google.com', 'accounts.google.com'],
        options={'require': ['iss', 'aud', 'exp', 'iat', 'sub', 'nonce', 'email', 'email_verified']})
    if claims.get('azp', config.GOOGLE_CLIENT_ID) != config.GOOGLE_CLIENT_ID:
        raise ValueError('Wrong authorized party')
    if not isinstance(claims['nonce'], str) or not secrets.compare_digest(claims['nonce'], nonce):
        raise ValueError('Wrong nonce')
    if claims['email_verified'] is not True:
        raise ValueError('Email not verified')
    subject, email = claims['sub'], claims['email']
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
        raise ValueError('Invalid subject')
    if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise ValueError('Invalid email')
    return {'sub': subject, 'email': email.strip().lower()}


def exchange_code(code, flow):
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.post(TOKEN_URL, data={'code': code, 'client_id': config.GOOGLE_CLIENT_ID,
            'client_secret': config.GOOGLE_CLIENT_SECRET, 'redirect_uri': config.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code', 'code_verifier': flow['verifier']})
        response.raise_for_status()
        token = response.json().get('id_token')
        if not isinstance(token, str) or len(token) > 20000:
            raise ValueError('Missing ID token')
    return verify_id_token(token, flow['nonce'])


def clear_cookie(response):
    response.delete_cookie(BROWSER_COOKIE, path=COOKIE_PATH, httponly=True,
                           secure=config.PRODUCTION, samesite='lax')
