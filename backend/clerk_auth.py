"""Verify Clerk session JWTs before resolving local document ownership."""
import re
import jwt
import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
import config
import db

_jwks = None
_issuer = None


def signing_key(token):
    global _jwks, _issuer
    if _jwks is None or _issuer != config.CLERK_ISSUER:
        _issuer = config.CLERK_ISSUER
        _jwks = jwt.PyJWKClient(_issuer + '/.well-known/jwks.json', lifespan=300, timeout=10)
    return _jwks.get_signing_key_from_jwt(token).key


def claims(request):
    if not config.clerk_enabled():
        raise HTTPException(404, 'Clerk authentication is not enabled.')
    header = request.headers.get('authorization', '')
    if not header.startswith('Bearer ') or len(header) > 16000:
        raise HTTPException(401, 'Sign in with Clerk to continue.')
    token = header[7:]
    try:
        value = jwt.decode(token, signing_key(token), algorithms=['RS256'], issuer=config.CLERK_ISSUER,
            leeway=5, options={'require':['exp','iat','nbf','sub','sid','azp']})
        if (value['azp'] not in config.ALLOWED_ORIGINS or value.get('sts') == 'pending'
                or not re.fullmatch(r'user_[A-Za-z0-9]+', value['sub'])
                or not re.fullmatch(r'sess_[A-Za-z0-9]+', value['sid'])):
            raise jwt.InvalidTokenError()
        return value
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, 'Your Clerk session is invalid or expired. Sign in again.') from None


def verified_email(subject):
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get('https://api.clerk.com/v1/users/' + subject,
                headers={'Authorization':'Bearer ' + config.CLERK_SECRET_KEY})
        response.raise_for_status()
        value = response.json()
        if value.get('id') != subject:
            raise ValueError()
        email = next((e['email_address'] for e in value.get('email_addresses', [])
            if e.get('id') == value.get('primary_email_address_id') and e.get('verification', {}).get('status') == 'verified'), None)
        if not email or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or len(email)>254:
            raise HTTPException(403, 'Verify your primary email address in Clerk before continuing.')
        return email.strip().lower()
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Could not verify your Clerk profile. Please retry.') from None


def current_user(request, password=None):
    value = claims(request)
    existing = db.resolve_clerk_user(value['sub'])
    if existing:
        return existing
    try:
        return db.resolve_clerk_user(value['sub'], verified_email(value['sub']), password)
    except db.ClerkLinkRequired:
        raise HTTPException(409, 'An existing SimplyDoc account needs linking. Enter its original password to keep your documents.') from None
    except IntegrityError:
        # A racing first login may have provisioned this subject already.
        existing = db.resolve_clerk_user(value['sub'])
        if existing:
            return existing
        raise HTTPException(409, 'This account is already linked to another Clerk user.') from None
