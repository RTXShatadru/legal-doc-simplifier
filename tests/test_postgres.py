"""Opt-in real pgvector integration. Uses only uniquely named test records."""
import os
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Set TEST_POSTGRES_URL to a disposable pgvector database')
def test_real_postgres_bootstrap_retrieval_and_delete():
    env=dict(os.environ, DATABASE_URL=os.environ['TEST_POSTGRES_URL'], EMBEDDING_PROVIDER='local',
             AI_PROVIDER='demo', APP_ENV='development', DISABLE_WORKER='1')
    script = """
import uuid
from sqlalchemy import delete
import db, embeddings
db.init_db()
user=db.create_user(str(uuid.uuid4())+'@pg-test.invalid','test-only')
other=db.create_user(str(uuid.uuid4())+'@pg-test.invalid','test-only')
try:
    chunks=[{'clause_index':0,'heading':'Deposit','text':'Deposit is 900 dollars.','page':1},
            {'clause_index':1,'heading':'Rent','text':'Monthly rent is 1500 dollars.','page':2}]
    doc=db.create_document(user['id'],'integration.pdf','Deposit and rent.',chunks,2)
    db.save_analysis(doc,chunks,embeddings.embed([c['text'] for c in chunks]),{'mode':'demo'})
    results=db.retrieve(doc,'deposit',1)
    assert results[0]['clause_index']==0, results
    assert db.get_document(doc,other['id']) is None
    assert db.list_documents(other['id'])==[]
    assert db.delete_document(doc,user['id'])
    assert db.get_clauses(doc)==[]
    print('Real PostgreSQL extension bootstrap, vector retrieval, isolation, and cascade deletion passed')
finally:
    with db.engine.begin() as conn:
        conn.execute(delete(db.users).where(db.users.c.id.in_([user['id'],other['id']])))
    db.engine.dispose()
"""
    result=subprocess.run([sys.executable,'-c',script],env=env,cwd=Path(__file__).resolve().parents[1]/'backend',capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
