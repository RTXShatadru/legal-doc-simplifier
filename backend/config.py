import os
import re
import secrets
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
load_dotenv(ROOT / 'backend' / '.env')
PRODUCTION = os.getenv('APP_ENV', 'development') == 'production'
DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{ROOT / 'backend' / 'app_data.db'}")
if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL.split('://', 1)[1]
AI_PROVIDER = os.getenv('AI_PROVIDER', 'groq')
EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'local')
EMBEDDING_DIM = 1024 if EMBEDDING_PROVIDER == 'voyage' else 384
JWT_SECRET = os.getenv('JWT_SECRET') or secrets.token_urlsafe(48)
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant').strip()
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:4b-instruct-2507-q4_K_M').strip()
OLLAMA_CONTEXT = 32768
ALLOWED_ORIGINS = [x.strip().rstrip('/') for x in os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173').split(',') if x.strip()]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_DOCUMENTS = 50
MAX_PAGES = 80
MAX_TEXT_CHARS = 120000
COOKIE_NAME = 'plainly_session'
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', '').strip()
AUTH_PROVIDER = os.getenv('AUTH_PROVIDER', 'local')
CLERK_PUBLISHABLE_KEY = os.getenv('CLERK_PUBLISHABLE_KEY', '').strip()
CLERK_SECRET_KEY = os.getenv('CLERK_SECRET_KEY', '').strip()
CLERK_ISSUER = os.getenv('CLERK_ISSUER', '').strip().rstrip('/')


def clerk_enabled():
    return AUTH_PROVIDER == 'clerk'


def google_enabled():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)


def validate_google():
    from urllib.parse import urlsplit
    if not any((GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)):
        return
    if not google_enabled():
        raise RuntimeError('Configure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI together')
    uri = urlsplit(GOOGLE_REDIRECT_URI)
    origin = f'{uri.scheme}://{uri.netloc}'
    if (origin not in ALLOWED_ORIGINS or uri.path != '/api/auth/google/callback'
            or uri.query or uri.fragment or uri.username or uri.password
            or (uri.scheme != 'https' and not (not PRODUCTION and uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1')))):
        raise RuntimeError('GOOGLE_REDIRECT_URI must be an allowed HTTPS origin plus /api/auth/google/callback (HTTP localhost is allowed in development)')


def validate():
    if AUTH_PROVIDER not in ('local', 'clerk'):
        raise RuntimeError('AUTH_PROVIDER must be local or clerk')
    if clerk_enabled():
        from urllib.parse import urlsplit
        import base64
        uri = urlsplit(CLERK_ISSUER)
        try:
            encoded = CLERK_PUBLISHABLE_KEY.split('_', 2)[2]
            host = base64.b64decode(encoded + '=' * (-len(encoded) % 4)).decode().rstrip('$')
        except Exception:
            host = ''
        if (not CLERK_SECRET_KEY.startswith(('sk_test_', 'sk_live_'))
                or not CLERK_PUBLISHABLE_KEY.startswith(('pk_test_', 'pk_live_'))
                or not re.fullmatch(r'[A-Za-z0-9.-]+', host)
                or uri.scheme != 'https' or uri.netloc != host or uri.path or uri.query or uri.fragment):
            raise RuntimeError('Configure matching CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY and HTTPS CLERK_ISSUER before enabling Clerk')
    validate_google()
    if AI_PROVIDER not in ('demo', 'gemini', 'ollama', 'groq') or EMBEDDING_PROVIDER not in ('local', 'voyage'):
        raise RuntimeError('Unsupported AI_PROVIDER or EMBEDDING_PROVIDER')
    if PRODUCTION:
        if len(os.getenv('JWT_SECRET', '')) < 32:
            raise RuntimeError('Production requires a JWT_SECRET of at least 32 characters')
        if not DATABASE_URL.startswith('postgresql'):
            raise RuntimeError('Production requires Postgres for durable storage')
        if not ALLOWED_ORIGINS or any(not x.startswith('https://') for x in ALLOWED_ORIGINS):
            raise RuntimeError('Set ALLOWED_ORIGINS to your HTTPS deployment origin')
    if AI_PROVIDER == 'gemini' and not os.getenv('GEMINI_API_KEY'):
        raise RuntimeError('Set GEMINI_API_KEY for AI_PROVIDER=gemini')
    if AI_PROVIDER == 'groq':
        if not os.getenv('GROQ_API_KEY', '').strip():
            raise RuntimeError('Set GROQ_API_KEY in .env for AI_PROVIDER=groq. Use AI_PROVIDER=demo only for local testing without AI.')
        if not re.fullmatch(r'[a-zA-Z0-9._/-]+', GROQ_MODEL):
            raise RuntimeError('Set GROQ_MODEL to a supported Groq model, such as llama-3.1-8b-instant')
    if EMBEDDING_PROVIDER == 'voyage' and not os.getenv('VOYAGE_API_KEY'):
        raise RuntimeError('Set VOYAGE_API_KEY for EMBEDDING_PROVIDER=voyage')
