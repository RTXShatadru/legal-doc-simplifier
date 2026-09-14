import asyncio
import contextlib
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import jwt
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import config
import auth
import db
import parsing
import embeddings
import llm
from provider_errors import ProviderError
import google_oauth
import clerk_auth

log = logging.getLogger('plainly')


class RedactOAuthQuery(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            if str(args[2]).startswith('/api/auth/google/callback'):
                args[2] = '/api/auth/google/callback'
                record.args = tuple(args)
        return True


logging.getLogger('uvicorn.access').addFilter(RedactOAuthQuery())


def run_analysis(doc_id):
    try:
        chunks = db.get_clauses(doc_id)
        if not chunks:
            return
        vectors = embeddings.embed([c['text'] for c in chunks])
        analysis = llm.analyze_document(chunks, extraction=db.get_extraction(doc_id), doc_id=doc_id)
        analysis['extraction'] = db.get_extraction(doc_id)
        db.save_analysis(doc_id, chunks, vectors, analysis)
    except Exception as exc:
        # Never log document contents, provider bodies, passwords or tokens.
        log.error('Analysis %s failed (%s)', doc_id, type(exc).__name__)
        db.fail_job(doc_id, str(exc) if isinstance(exc, ProviderError) else None)


async def worker():
    while True:
        try:
            doc_id = await asyncio.to_thread(db.claim_job)
            if doc_id:
                await asyncio.to_thread(run_analysis, doc_id)
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error('Worker error (%s)', type(exc).__name__)
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app):
    config.validate()
    db.init_db()
    task = None if os.getenv('DISABLE_WORKER') == '1' else asyncio.create_task(worker())
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title='SimplyDoc · Legal Document Simplifier', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type', 'Authorization'])


class BoundedBody:
    """Limit streamed bodies before multipart parsing, including missing Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST', 'PUT', 'PATCH'):
            return await self.app(scope, receive, send)
        maximum = config.MAX_UPLOAD_BYTES + 65536 if scope['path'] == '/api/documents/upload' else 65536
        parts, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > maximum:
                return await JSONResponse({'detail': 'Request is too large. PDFs must be 10 MB or smaller.'}, 413)(scope, receive, send)
            parts.append(message)
            if not message.get('more_body', False):
                break
        async def replay():
            return parts.pop(0) if parts else await receive()
        await self.app(scope, replay, send)


app.add_middleware(BoundedBody)


@app.middleware('http')
async def security_headers(request: Request, call_next):
    if config.clerk_enabled() and request.url.path in ('/api/auth/signup','/api/auth/login','/api/auth/google/start','/api/auth/google/callback'):
        return JSONResponse({'detail':'Use Clerk sign-in for this workspace.'}, 409)
    if request.method in ('POST', 'DELETE', 'PUT', 'PATCH'):
        origin = request.headers.get('origin')
        if (origin and origin.rstrip('/') not in config.ALLOWED_ORIGINS) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'This origin is not allowed.'}, 403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; frame-src 'self' blob:; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if config.clerk_enabled():
        issuer = config.CLERK_ISSUER
        response.headers['Content-Security-Policy'] = (
            f"default-src 'self'; script-src 'self' {issuer} https://challenges.cloudflare.com https://*.protect.clerk.com; "
            f"connect-src 'self' {issuer} https://*.protect.clerk.com:*; "
            "img-src 'self' data: https://img.clerk.com; style-src 'self' 'unsafe-inline'; font-src 'self'; "
            "frame-src 'self' blob: https://challenges.cloudflare.com https://*.protect.clerk.com; worker-src 'self' blob:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    if config.PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
            raise ValueError('Enter a valid email address.')
        return value


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator('message')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Enter a question.')
        return value.strip()


def current_user(request: Request):
    if config.clerk_enabled():
        return clerk_auth.current_user(request)
    try:
        payload = auth.decode_token(request.cookies.get(config.COOKIE_NAME, ''))
        user = db.user_by_id(payload['sub'])
        if not user or user['session_version'] != payload['ver']:
            raise jwt.InvalidTokenError()
        return user
    except jwt.PyJWTError:
        raise HTTPException(401, 'Your session expired. Please sign in again.') from None


def limit(subject, scope, count, seconds=60):
    if not db.rate_limit(subject, scope, count, seconds):
        raise HTTPException(429, 'Too many requests. Please try again later.', headers={'Retry-After': str(seconds)})


def session(response, user):
    response.set_cookie(config.COOKIE_NAME, auth.create_token(user['id'], user['session_version']),
                        httponly=True, secure=config.PRODUCTION, samesite='lax', max_age=86400, path='/')
    return {'email': user['email']}


@app.get('/api/health')
def health():
    with db.engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    readiness = {}
    if config.AI_PROVIDER == 'ollama':
        import ollama_provider
        readiness = ollama_provider.status()
    elif config.AI_PROVIDER == 'groq':
        readiness = {'ai_model': config.GROQ_MODEL}
    return {'status': 'ok', **readiness, 'ai_provider': config.AI_PROVIDER, 'embedding_provider': config.EMBEDDING_PROVIDER,
            'storage': 'postgresql' if db.POSTGRES else 'sqlite', 'max_upload_mb': 10}


@app.post('/api/auth/signup', status_code=201)
def signup(req: Credentials, request: Request, response: Response):
    limit(request.client.host, 'signup', 10, 3600)
    try:
        user = db.create_user(req.email, auth.hash_password(req.password))
    except IntegrityError:
        raise HTTPException(409, 'An account with this email already exists.') from None
    return session(response, user)


@app.post('/api/auth/login')
def login(req: Credentials, request: Request, response: Response):
    limit(request.client.host, 'login-ip', 30, 900)
    limit(req.email, 'login-email', 10, 900)
    user = db.user_by_email(req.email)
    if not user or not auth.verify_password(req.password, user['password_hash']):
        raise HTTPException(401, 'Incorrect email or password.')
    return session(response, user)


@app.post('/api/auth/logout')
def logout(response: Response, user=Depends(current_user)):
    db.revoke_sessions(user['id'])
    response.delete_cookie(config.COOKIE_NAME, path='/', secure=config.PRODUCTION, httponly=True, samesite='lax')
    return {'logged_out': True}


@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return {'email': user['email'], 'google_connected': db.google_connected(user['id'])}


@app.get('/api/auth/providers')
def auth_providers():
    if config.clerk_enabled():
        return {'google':False, 'auth_provider':'clerk', 'clerk_publishable_key':config.CLERK_PUBLISHABLE_KEY}
    return {'google': config.google_enabled()}


class LinkClerkRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@app.post('/api/auth/clerk/link')
def link_clerk(req: LinkClerkRequest, request: Request):
    limit(request.client.host, 'clerk-link', 5, 900)
    identity = clerk_auth.claims(request)
    limit(identity['sub'], 'clerk-link-user', 5, 900)
    user = clerk_auth.current_user(request, req.password)
    return {'email':user['email']}


class GoogleStartRequest(BaseModel):
    link: bool = False


@app.post('/api/auth/google/start')
def google_start(req: GoogleStartRequest, request: Request, response: Response):
    if not config.google_enabled():
        raise HTTPException(503, 'Google sign-in is not configured yet. Please use email and password.')
    limit(request.client.host, 'google-start', 30, 900)
    user = current_user(request) if req.link else None
    return {'url': google_oauth.begin(response, user)}


@app.get('/api/auth/google/callback')
def google_callback(request: Request):
    def finish(error=None, user=None, linked=False):
        suffix = '?auth_error=' + error if error else '?google=connected' if linked else ''
        response = RedirectResponse(google_oauth.home_url() + suffix, status_code=303)
        google_oauth.clear_cookie(response)
        if user:
            session(response, user)
        return response

    if not config.google_enabled():
        return finish('not_configured')
    state = request.query_params.get('state', '')
    browser = request.cookies.get(google_oauth.BROWSER_COOKIE, '')
    if not 20 <= len(state) <= 128 or not 20 <= len(browser) <= 128:
        return finish('expired')
    flow = db.consume_oauth_flow(google_oauth.digest(state), google_oauth.digest(browser))
    if not flow:
        return finish('expired')
    if request.query_params.get('error'):
        return finish('cancelled')
    code = request.query_params.get('code', '')
    if not code or len(code) > 4096:
        return finish('failed')
    if flow['link_user_id']:
        try:
            user = current_user(request)
            if user['id'] != flow['link_user_id'] or user['session_version'] != flow['session_version']:
                return finish('expired')
        except HTTPException:
            return finish('expired')
    try:
        identity = google_oauth.exchange_code(code, flow)
        user = db.resolve_google_user(identity['sub'], identity['email'], flow['link_user_id'])
    except db.GoogleAccountConflict as exc:
        return finish(str(exc))
    except IntegrityError:
        # An overlapping signup/link request must not merge accounts.
        return finish('conflict')
    except Exception as exc:
        log.warning('Google sign-in failed (%s)', type(exc).__name__)
        return finish('failed')
    return finish(user=user, linked=bool(flow['link_user_id']))


def ingest(content, filename, user):
    limit(user['id'], 'upload', 10, 3600)
    limit('service', 'analysis-budget', int(os.getenv('MAX_ANALYSES_PER_DAY', '100')), 86400)
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'PDFs must be 10 MB or smaller.')
    try:
        full_text, chunks, pages, extraction = parsing.parse_pdf_detailed(content)
        safe_name = Path(filename.replace('\\', '/')).name[:180] or 'document.pdf'
        doc_id = db.create_document(user['id'], safe_name, full_text, chunks, pages, extraction)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {'doc_id': doc_id, 'filename': safe_name, 'clause_count': len(chunks), 'status': 'needs_review' if extraction.get('ocr_pages') else 'queued'}


@app.post('/api/documents/upload', status_code=202)
def upload_document(file: UploadFile = File(...), user=Depends(current_user)):
    try:
        content = file.file.read(config.MAX_UPLOAD_BYTES + 1)
        return ingest(content, file.filename or 'document.pdf', user)
    finally:
        file.file.close()


@app.post('/api/documents/sample', status_code=202)
def sample_document(user=Depends(current_user)):
    return ingest((config.ROOT / 'sample_lease.pdf').read_bytes(), 'Sample rental agreement.pdf', user)


@app.get('/api/documents')
def list_documents(user=Depends(current_user)):
    return db.list_documents(user['id'])


def owned(doc_id, user):
    doc = db.get_document(str(doc_id), user['id'])
    if not doc:
        raise HTTPException(404, 'Document not found.')
    return doc


@app.get('/api/documents/{doc_id}')
def get_document(doc_id: UUID, user=Depends(current_user)):
    doc = owned(doc_id, user)
    chunks = db.get_clauses(doc['id'])
    return {'doc_id': doc['id'], 'filename': doc['filename'], 'status': doc['status'],
            'uploaded_at': doc['uploaded_at'], 'page_count': doc['page_count'],
            'analysis': doc['summary_json'], 'error': doc['error'], 'clauses': chunks, 'source_revision': db.source_revision(chunks),
            'extraction': db.get_extraction(doc['id']), 'progress': db.batch_progress(doc['id'])}


class SourceSection(BaseModel):
    clause_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=8000)

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Source sections cannot be blank. Mark unreadable passages explicitly.')
        return value


class SourceReview(BaseModel):
    sections: list[SourceSection] = Field(min_length=1, max_length=1000)
    revision: str = Field(min_length=64, max_length=64)


@app.post('/api/documents/{doc_id}/source-review', status_code=202)
def source_review(doc_id: UUID, req: SourceReview, user=Depends(current_user)):
    owned(doc_id,user)
    limit(user['id'],'source-review',10,3600)
    limit('service','analysis-budget',int(os.getenv('MAX_ANALYSES_PER_DAY','100')),86400)
    try:
        db.review_source(str(doc_id),user['id'],[c.model_dump() for c in req.sections],req.revision)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from None
    return {'status':'queued'}


@app.post('/api/documents/{doc_id}/retry', status_code=202)
def retry_document(doc_id: UUID, user=Depends(current_user)):
    owned(doc_id, user)
    limit(user['id'], 'retry', 5, 3600)
    limit('service', 'analysis-budget', int(os.getenv('MAX_ANALYSES_PER_DAY', '100')), 86400)
    if not db.retry(str(doc_id), user['id']):
        raise HTTPException(409, 'Only failed analyses can be retried.')
    return {'status': 'queued'}


@app.post('/api/documents/{doc_id}/chat')
def chat(doc_id: UUID, req: ChatRequest, user=Depends(current_user)):
    doc = owned(doc_id, user)
    if doc['status'] != 'ready':
        raise HTTPException(409, 'Wait for the analysis to finish before asking a question.')
    limit(user['id'], 'chat', 60, 3600)
    limit('service', 'chat-budget', int(os.getenv('MAX_CHATS_PER_DAY', '1000')), 86400)
    revision=db.source_revision(db.get_clauses(doc['id']))
    try:
        answer, sources = llm.answer_question(doc['id'], req.message, db.chat_history(doc['id']))
        db.save_chat_pair(doc['id'], req.message, answer, sources, expected_revision=revision)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception as exc:
        log.error('Chat %s failed (%s)', doc['id'], type(exc).__name__)
        raise HTTPException(503, 'Could not answer right now. Your question was not saved; please retry.') from None
    return {'answer': answer, 'sources': sources}


@app.get('/api/documents/{doc_id}/chat')
def history(doc_id: UUID, user=Depends(current_user)):
    doc = owned(doc_id, user)
    return db.chat_history(doc['id'], 200)


@app.delete('/api/documents/{doc_id}')
def delete_document(doc_id: UUID, user=Depends(current_user)):
    if not db.delete_document(str(doc_id), user['id']):
        raise HTTPException(404, 'Document not found.')
    return {'deleted': True}


@app.exception_handler(Exception)
async def unhandled(request, exc):
    log.error('Request failed (%s)', type(exc).__name__)
    return JSONResponse({'detail': 'Something went wrong. Please try again.'}, 500)


DIST = config.ROOT / 'frontend-react' / 'dist'
if DIST.is_dir():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/')
    def frontend():
        return FileResponse(DIST / 'index.html')

    @app.get('/favicon.svg')
    def favicon():
        return FileResponse(DIST / 'favicon.svg')
