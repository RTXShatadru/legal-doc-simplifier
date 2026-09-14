"""One persistence layer for PostgreSQL/pgvector and the SQLite local demo."""
import time
import uuid
from sqlalchemy import (create_engine, event, MetaData, Table, Column, String, Integer, Float,
                        Text, JSON, ForeignKey, Index, select, update, delete, func, text)
from sqlalchemy.exc import IntegrityError
from pgvector.sqlalchemy import Vector
import config
import embeddings

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True,
                       connect_args={'check_same_thread': False, 'timeout': 30} if config.DATABASE_URL.startswith('sqlite') else {})
POSTGRES = engine.dialect.name == 'postgresql'
if not POSTGRES:
    @event.listens_for(engine, 'connect')
    def sqlite_setup(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
metadata = MetaData()
users = Table('users', metadata,
    Column('id', String(36), primary_key=True), Column('email', String(254), unique=True, nullable=False),
    Column('password_hash', Text, nullable=False), Column('session_version', Integer, nullable=False, default=0))
documents = Table('documents', metadata,
    Column('id', String(36), primary_key=True), Column('user_id', String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('filename', Text, nullable=False), Column('uploaded_at', Float, nullable=False),
    Column('full_text', Text, nullable=False), Column('page_count', Integer, nullable=False),
    Column('status', String(20), nullable=False), Column('summary_json', JSON),
    Column('error', Text), Column('started_at', Float))
clauses = Table('clauses', metadata,
    Column('id', Integer, primary_key=True), Column('doc_id', String(36), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
    Column('clause_index', Integer, nullable=False), Column('heading', Text),
    Column('text', Text, nullable=False), Column('page', Integer, nullable=False),
    Column('embedding', JSON().with_variant(Vector(config.EMBEDDING_DIM), 'postgresql')))
document_extraction = Table('document_extraction', metadata,
    Column('doc_id', String(36), ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
    Column('info', JSON, nullable=False))
analysis_batches = Table('analysis_batches', metadata,
    Column('doc_id', String(36), ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
    Column('signature', String(64), nullable=False), Column('total', Integer, nullable=False),
    Column('results', JSON, nullable=False))


def batch_state(doc_id):
    return one(select(analysis_batches).where(analysis_batches.c.doc_id == doc_id))


def save_batches(doc_id, signature, total, results):
    with engine.begin() as conn:
        if not conn.execute(select(documents.c.id).where(documents.c.id == doc_id)).first():
            raise ValueError('Document removed during review')
        conn.execute(delete(analysis_batches).where(analysis_batches.c.doc_id == doc_id))
        conn.execute(analysis_batches.insert().values(doc_id=doc_id, signature=signature, total=total, results=results))
        conn.execute(update(documents).where(documents.c.id == doc_id, documents.c.status == 'processing').values(started_at=time.time()))


def batch_progress(doc_id):
    state = batch_state(doc_id)
    return {'completed': len(state['results']), 'total': state['total']} if state else None

messages = Table('chat_messages', metadata,
    Column('id', Integer, primary_key=True), Column('doc_id', String(36), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
    Column('role', String(12), nullable=False), Column('content', Text, nullable=False), Column('sources', JSON),
    Column('created_at', Float, nullable=False))
limits = Table('rate_limits', metadata, Column('key', String(200), primary_key=True),
               Column('hits', Integer, nullable=False), Column('expires_at', Float, nullable=False))
settings = Table('settings', metadata, Column('key', String(100), primary_key=True), Column('value', Text, nullable=False))
google_accounts = Table('google_accounts', metadata,
    Column('subject', String(255), primary_key=True),
    Column('user_id', String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True))
clerk_accounts = Table('clerk_accounts', metadata,
    Column('subject', String(255), primary_key=True),
    Column('user_id', String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True))


class ClerkLinkRequired(ValueError):
    pass


def resolve_clerk_user(subject, email=None, link_password=None):
    import auth
    with engine.begin() as conn:
        account = conn.execute(select(clerk_accounts).where(clerk_accounts.c.subject == subject)).mappings().first()
        if account:
            user_id = account['user_id']
        else:
            if not email:
                return None
            user = conn.execute(select(users).where(users.c.email == email).with_for_update()).mappings().first()
            if user:
                if not link_password or not auth.verify_password(link_password, user['password_hash']):
                    raise ClerkLinkRequired()
                user_id = user['id']
            else:
                user_id = str(uuid.uuid4())
                conn.execute(users.insert().values(id=user_id,email=email,password_hash='!clerk-only',session_version=0))
            conn.execute(clerk_accounts.insert().values(subject=subject,user_id=user_id))
    return user_by_id(user_id)
oauth_flows = Table('oauth_flows', metadata,
    Column('state_hash', String(64), primary_key=True),
    Column('browser_hash', String(64), nullable=False),
    Column('nonce', String(128), nullable=False), Column('verifier', String(128), nullable=False),
    Column('expires_at', Float, nullable=False),
    Column('link_user_id', String(36), ForeignKey('users.id', ondelete='CASCADE')),
    Column('session_version', Integer))
Index('document_owner_idx', documents.c.user_id)
Index('clause_document_index', clauses.c.doc_id, clauses.c.clause_index, unique=True)
Index('chat_document_idx', messages.c.doc_id, messages.c.id)


def init_db():
    # Bootstrap extension BEFORE registering/creating vector columns on a fresh DB.
    if POSTGRES:
        with engine.begin() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    metadata.create_all(engine)
    signature = f'{config.EMBEDDING_PROVIDER}:{config.EMBEDDING_DIM}'
    if config.EMBEDDING_PROVIDER == 'voyage':
        import os
        signature += ':' + os.getenv('VOYAGE_MODEL', 'voyage-3.5-lite')
    with engine.begin() as conn:
        existing = conn.execute(select(settings.c.value).where(settings.c.key == 'embedding_profile')).scalar()
        if existing and existing != signature:
            raise RuntimeError('Embedding profile changed. Use a new database or explicitly migrate/re-embed existing clauses.')
        if not existing:
            conn.execute(settings.insert().values(key='embedding_profile', value=signature))
    # Exact, document-filtered cosine search is intentional for <=120k characters/doc.
    # Avoid a global approximate index returning too few rows after owner filtering.


def one(query):
    with engine.connect() as conn:
        row = conn.execute(query).mappings().first()
        return dict(row) if row else None


def all_rows(query):
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query).mappings()]


def user_by_email(email):
    return one(select(users).where(users.c.email == email))


def user_by_id(user_id):
    return one(select(users).where(users.c.id == user_id))


def create_user(email, password_hash):
    user_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(users.insert().values(id=user_id, email=email, password_hash=password_hash, session_version=0))
    return user_by_id(user_id)


def revoke_sessions(user_id):
    with engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == user_id).values(session_version=users.c.session_version + 1))


class GoogleAccountConflict(ValueError):
    pass


def google_connected(user_id):
    return one(select(google_accounts.c.subject).where(google_accounts.c.user_id == user_id)) is not None


def save_oauth_flow(flow):
    with engine.begin() as conn:
        conn.execute(delete(oauth_flows).where(oauth_flows.c.expires_at < time.time()))
        conn.execute(oauth_flows.insert().values(**flow))


def consume_oauth_flow(state_hash, browser_hash):
    # DELETE RETURNING makes a validated challenge single-use, also across workers.
    with engine.begin() as conn:
        row = conn.execute(delete(oauth_flows).where(oauth_flows.c.state_hash == state_hash,
            oauth_flows.c.browser_hash == browser_hash, oauth_flows.c.expires_at > time.time())
            .returning(*oauth_flows.c)).mappings().first()
        return dict(row) if row else None


def resolve_google_user(subject, email, link_user_id=None):
    with engine.begin() as conn:
        account = conn.execute(select(google_accounts).where(google_accounts.c.subject == subject)).mappings().first()
        if account:
            if link_user_id and account['user_id'] != link_user_id:
                raise GoogleAccountConflict('already_linked')
            user_id = account['user_id']
        elif link_user_id:
            user = conn.execute(select(users).where(users.c.id == link_user_id).with_for_update()).mappings().first()
            if not user or user['email'] != email:
                raise GoogleAccountConflict('email_mismatch')
            if conn.execute(select(google_accounts.c.subject).where(google_accounts.c.user_id == link_user_id)).scalar():
                raise GoogleAccountConflict('already_linked')
            user_id = link_user_id
            conn.execute(google_accounts.insert().values(subject=subject, user_id=user_id))
        else:
            if conn.execute(select(users.c.id).where(users.c.email == email)).scalar():
                raise GoogleAccountConflict('email_exists')
            user_id = str(uuid.uuid4())
            # A non-bcrypt sentinel disables password login for a Google-only account.
            conn.execute(users.insert().values(id=user_id, email=email, password_hash='!google-only', session_version=0))
            conn.execute(google_accounts.insert().values(subject=subject, user_id=user_id))
    return user_by_id(user_id)


def rate_limit(subject, scope, limit, seconds):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sq_insert
    now = time.time()
    key = f'{scope}:{subject}:{int(now // seconds)}'
    table_insert = pg_insert if POSTGRES else sq_insert
    stmt = table_insert(limits).values(key=key, hits=1, expires_at=now + seconds)
    stmt = stmt.on_conflict_do_update(index_elements=[limits.c.key], set_={'hits': limits.c.hits + 1},
                                     where=limits.c.hits < limit).returning(limits.c.hits)
    with engine.begin() as conn:
        conn.execute(delete(limits).where(limits.c.expires_at < now))
        return conn.execute(stmt).scalar() is not None


def create_document(user_id, filename, full_text, chunks, page_count, extraction=None):
    doc_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(select(users.c.id).where(users.c.id == user_id).with_for_update()).first()
        count = conn.execute(select(func.count()).select_from(documents).where(documents.c.user_id == user_id)).scalar()
        if count >= config.MAX_DOCUMENTS:
            raise ValueError('Your library is full (50 documents). Delete a document before uploading.')
        conn.execute(documents.insert().values(id=doc_id, user_id=user_id, filename=filename, full_text=full_text,
                     page_count=page_count, uploaded_at=time.time(), status='needs_review' if extraction and extraction.get('ocr_pages') else 'queued'))
        conn.execute(clauses.insert(), [dict(c, doc_id=doc_id) for c in chunks])
        if extraction:
            conn.execute(document_extraction.insert().values(doc_id=doc_id, info=extraction))
    return doc_id


def list_documents(user_id):
    return all_rows(select(documents.c.id, documents.c.filename, documents.c.uploaded_at, documents.c.status, documents.c.page_count)
                    .where(documents.c.user_id == user_id).order_by(documents.c.uploaded_at.desc()))


def source_revision(chunks):
    import hashlib
    import json
    return hashlib.sha256(json.dumps([(c['clause_index'], c['text']) for c in chunks], ensure_ascii=False).encode()).hexdigest()


def review_source(doc_id, user_id, revised, revision):
    with engine.begin() as conn:
        doc = conn.execute(select(documents).where(documents.c.id==doc_id, documents.c.user_id==user_id).with_for_update()).mappings().first()
        if not doc or doc['status'] not in ('needs_review','failed','ready'):
            raise ValueError('Wait for analysis to finish before editing source text.')
        current = list(conn.execute(select(clauses).where(clauses.c.doc_id==doc_id).order_by(clauses.c.clause_index)).mappings())
        if source_revision(current)!=revision:
            raise ValueError('Source text changed. Refresh before saving your corrections.')
        if len(revised)!=len(current) or {c['clause_index'] for c in revised}!={c['clause_index'] for c in current}:
            raise ValueError('Include every source section exactly once.')
        updates={c['clause_index']:c['text'] for c in revised}
        if sum(len(t) for t in updates.values())>config.MAX_TEXT_CHARS:
            raise ValueError('Corrected text exceeds the document size limit.')
        claimed=conn.execute(update(documents).where(documents.c.id==doc_id,documents.c.status==doc['status']).values(status='queued',summary_json=None,error=None,started_at=None,
            full_text='\n\n'.join(updates[c['clause_index']] for c in current)))
        if not claimed.rowcount:
            raise ValueError('Document state changed. Refresh and try again.')
        info=conn.execute(select(document_extraction.c.info).where(document_extraction.c.doc_id==doc_id)).scalar() or {}
        info=dict(info)
        info.setdefault('original_sections',[{'clause_index':c['clause_index'],'page':c['page'],'text':c['text']} for c in current])
        info['user_reviewed_at']=time.time()
        # User review is not proof that OCR or legal interpretation is correct.
        conn.execute(delete(document_extraction).where(document_extraction.c.doc_id==doc_id))
        conn.execute(document_extraction.insert().values(doc_id=doc_id,info=info))
        for index, value in updates.items():
            conn.execute(update(clauses).where(clauses.c.doc_id==doc_id,clauses.c.clause_index==index).values(text=value,embedding=None))
        conn.execute(delete(analysis_batches).where(analysis_batches.c.doc_id==doc_id))
        conn.execute(delete(messages).where(messages.c.doc_id==doc_id))


def get_document(doc_id, user_id):
    return one(select(documents).where(documents.c.id == doc_id, documents.c.user_id == user_id))


def get_extraction(doc_id):
    row = one(select(document_extraction.c.info).where(document_extraction.c.doc_id == doc_id))
    return row['info'] if row else None


def get_clauses(doc_id):
    return all_rows(select(clauses.c.clause_index, clauses.c.heading, clauses.c.text, clauses.c.page).where(clauses.c.doc_id == doc_id).order_by(clauses.c.clause_index))


def claim_job():
    now = time.time()
    with engine.begin() as conn:
        # Abandoned jobs become retryable after a bounded lease, including restarts.
        conn.execute(update(documents).where(documents.c.status == 'processing', documents.c.started_at < now - 900)
                     .values(status='failed', error='Analysis was interrupted. Please retry.'))
        job = conn.execute(select(documents.c.id).where(documents.c.status == 'queued').order_by(documents.c.uploaded_at).limit(1)).scalar()
        if not job:
            return None
        claimed = conn.execute(update(documents).where(documents.c.id == job, documents.c.status == 'queued')
                               .values(status='processing', started_at=now))
        return job if claimed.rowcount else None


def save_analysis(doc_id, chunks, vectors, analysis):
    with engine.begin() as conn:
        if not conn.execute(select(documents.c.id).where(documents.c.id == doc_id)).scalar():
            return
        for clause, vector in zip(chunks, vectors, strict=True):
            conn.execute(update(clauses).where(clauses.c.doc_id == doc_id, clauses.c.clause_index == clause['clause_index']).values(embedding=vector))
        conn.execute(update(documents).where(documents.c.id == doc_id).values(status='ready', summary_json=analysis, error=None))


def fail_job(doc_id, safe_error=None):
    with engine.begin() as conn:
        conn.execute(update(documents).where(documents.c.id == doc_id).values(status='failed', error=safe_error or 'Analysis could not finish. Check the service configuration or try again.'))


def retry(doc_id, user_id):
    with engine.begin() as conn:
        result = conn.execute(update(documents).where(documents.c.id == doc_id, documents.c.user_id == user_id,
                              documents.c.status == 'failed').values(status='queued', error=None, started_at=None))
        return bool(result.rowcount)


def retrieve(doc_id, query, top_k=6):
    if config.EMBEDDING_PROVIDER == 'local':
        from retrieval import rank
        rows = all_rows(select(clauses.c.clause_index, clauses.c.heading, clauses.c.text, clauses.c.page)
                        .where(clauses.c.doc_id == doc_id, clauses.c.embedding.is_not(None)))
        return rank(rows, query, top_k)
    query_vector = embeddings.embed([query], 'query')[0]
    if POSTGRES:
        # ORM comparator needs Vector type, even when a JSON dialect variant is used.
        from sqlalchemy import cast
        distance = cast(clauses.c.embedding, Vector(config.EMBEDDING_DIM)).cosine_distance(query_vector)
        rows = all_rows(select(clauses.c.clause_index, clauses.c.heading, clauses.c.text, clauses.c.page)
                        .where(clauses.c.doc_id == doc_id, clauses.c.embedding.is_not(None)).order_by(distance).limit(top_k))
        return rows
    rows = all_rows(select(clauses).where(clauses.c.doc_id == doc_id, clauses.c.embedding.is_not(None)))
    rows.sort(key=lambda c: embeddings.similarity(query_vector, c['embedding']), reverse=True)
    return [{k: c[k] for k in ('clause_index', 'heading', 'text', 'page')} for c in rows[:top_k]]


def chat_history(doc_id, limit=40):
    rows = all_rows(select(messages).where(messages.c.doc_id == doc_id).order_by(messages.c.id.desc()).limit(limit))
    return [{k: row[k] for k in ('role', 'content', 'sources')} for row in reversed(rows)]


def save_chat_pair(doc_id, question, answer, sources, expected_revision=None):
    with engine.begin() as conn:
        if expected_revision is not None:
            state=conn.execute(select(documents.c.status).where(documents.c.id==doc_id).with_for_update()).scalar()
            current=list(conn.execute(select(clauses).where(clauses.c.doc_id==doc_id).order_by(clauses.c.clause_index)).mappings())
            if state!='ready' or source_revision(current)!=expected_revision:
                raise ValueError('Source changed during chat')
        conn.execute(messages.insert(), [
            {'doc_id': doc_id, 'role': 'user', 'content': question, 'sources': [], 'created_at': time.time()},
            {'doc_id': doc_id, 'role': 'assistant', 'content': answer, 'sources': sources, 'created_at': time.time()}])


def delete_document(doc_id, user_id):
    with engine.begin() as conn:
        return bool(conn.execute(delete(documents).where(documents.c.id == doc_id, documents.c.user_id == user_id)).rowcount)
