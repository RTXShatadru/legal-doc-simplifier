"""Domain routing, evidence checks, extraction and cross-account access."""
import io
import json
import zipfile
import pytest
from sqlalchemy import select, func
from test_app import client, signup, pdf_bytes, db, main, config, llm
import domain_service as domains
import domain_review
import document_input
import resume_matching


def upload_domain(client, domain, workflow='review'):
    r=client.post('/api/documents/upload',data={'domain':domain,'workflow':workflow},files={'file':('document.pdf',pdf_bytes(),'application/pdf')})
    assert r.status_code==202,r.text
    return r.json()['doc_id']


@pytest.mark.parametrize('domain',['property','finance','hr','medical','court'])
def test_one_login_routes_all_domains_and_persists_context(client,domain):
    signup(client)
    assert len(client.get('/api/domains').json())==5
    doc_id=upload_domain(client,domain)
    assert db.claim_job()==doc_id
    main.run_analysis(doc_id)
    doc=client.get('/api/documents/'+doc_id).json()
    assert doc['status']=='ready'
    assert doc['domain']==doc['analysis']['domain']==domain
    assert client.get('/api/documents').json()[0]['domain']==domain
    assert client.post(f'/api/documents/{doc_id}/chat',json={'message':'Explain the deposit'}).status_code==200


def test_unknown_domain_and_invalid_workflow_rejected(client):
    signup(client)
    for domain,workflow in [('fake','review'),('medical','resume'),('hr','unknown')]:
        r=client.post('/api/documents/upload',data={'domain':domain,'workflow':workflow},files={'file':('a.pdf',pdf_bytes())})
        assert r.status_code==422
    assert client.get('/api/documents').json()==[]


def test_resume_match_owner_isolation_invalidation_and_delete(client,monkeypatch):
    signup(client)
    doc_id=upload_domain(client,'hr','resume');db.claim_job();main.run_analysis(doc_id)
    monkeypatch.setattr(resume_matching,'match',lambda *a:{'job_requirements':{'job_title':'Engineer'},'match':{'match_score':50}})
    r=client.post(f'/api/documents/{doc_id}/match',json={'description':'Python and Docker skills required for this position.'})
    assert r.status_code==200
    doc=client.get('/api/documents/'+doc_id).json()
    assert doc['job_match']['match']['match_score']==50
    client.post('/api/auth/logout');signup(client,'other@example.test')
    for url in (f'/api/documents/{doc_id}',f'/api/documents/{doc_id}/chat'):
        assert client.get(url).status_code==404
    assert client.post(f'/api/documents/{doc_id}/match',json={'description':'Python and Docker skills required for this position.'}).status_code==404
    assert client.delete('/api/documents/'+doc_id).status_code==404
    client.post('/api/auth/logout');client.post('/api/auth/login',json={'email':'one@example.test','password':'Password123!'})
    r=client.post(f'/api/documents/{doc_id}/source-review',json={'sections':[{'clause_index':c['clause_index'],'text':c['text']} for c in doc['clauses']],'revision':doc['source_revision']})
    assert r.status_code==202 and db.get_context(doc_id)['job_match'] is None
    assert client.delete('/api/documents/'+doc_id).status_code==200
    assert db.one(select(func.count()).select_from(db.document_context))['count_1']==0


def test_resume_normalization_and_empty_score():
    r=resume_matching.compare(['ReactJS','Python'],['React.js','Docker'],['PYTHON'])
    assert r['match_score']==50 and r['matched_skills']==['React.js'] and r['missing_skills']==['Docker']
    assert r['nice_to_have_matched']==['Python']
    assert resume_matching.compare(['Python'],[],[])['match_score'] is None


def test_docx_text_and_domain_restriction():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Example Candidate. Skills: Python and ReactJS.</w:t></w:r></w:p></w:body></w:document>')
    text,chunks,_,_=document_input.parse(out.getvalue(),'resume.docx','hr','resume')
    assert 'Python' in text and ''.join(c['text'] for c in chunks)==text
    with pytest.raises(ValueError):document_input.parse(out.getvalue(),'resume.docx','finance','review')
    with pytest.raises(ValueError):document_input.parse(b'not a docx','resume.docx','hr','resume')


def test_medical_and_deadline_evidence_validation():
    source=[{'clause_index':4,'page':2,'text':'Glucose 105 mg/dL. Reference 70-99 mg/dL. Reply within 15 days.'}]
    base={'plain_summary':'The source states a glucose reading.','document_type':'Report','key_terms':[],'risky_clauses':[]}
    medical={**base,'flagged_values':[{'test_name':'Glucose','reported_value':'105 mg/dL','normal_range':'70-99 mg/dL','why_flagged':'Compare the printed range.','clause_index':4,'quote':'Glucose 105 mg/dL.'}]}
    assert domains.validate_part(medical,source,'medical','review')['flagged_values'][0]['page']==2
    medical['flagged_values'][0]['normal_range']='80-120'
    with pytest.raises(ValueError):domains.validate_part(medical,source,'medical','review')
    court={**base,'action_items':[{'action':'Reply','deadline':'20 November 2026','clause_index':4,'quote':'Reply within 15 days.'}]}
    with pytest.raises(ValueError):domains.validate_part(court,source,'court','review')


def test_plan_splits_large_sections_without_losing_characters(monkeypatch):
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    source=[{'clause_index':7,'page':3,'text':('अचल संपत्ति का विवरण and property description. '*400)}]
    parts=domain_review.plan(source,{},'property','review')
    assert ''.join(c['text'] for b in parts for c in b)==source[0]['text']
    assert all(c['clause_index']==7 for b in parts for c in b)


def test_live_pipeline_domain_schema_and_saved_resume_results(client,monkeypatch):
    signup(client);doc_id=upload_domain(client,'hr','resume')
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    def generate(system,payload,schema,tokens):
        c=payload['clauses'][0]
        assert schema is domains.ResumePart and 'protected traits' in system
        return {'plain_summary':'A sourced example resume profile.','document_type':'Resume','facts':[{'category':'experience','value':'Sample role','detail':'From supplied text','clause_index':c['clause_index'],'quote':c['text'][:30]}]}
    monkeypatch.setattr(llm,'call_json',generate)
    db.claim_job();main.run_analysis(doc_id)
    doc=client.get('/api/documents/'+doc_id).json()
    assert doc['status']=='ready' and doc['analysis']['resume_profile']['experience']
    monkeypatch.setattr(llm,'call_json',lambda *a:pytest.fail('Saved batches should be reused'))
    rerun=llm.analyze_document(db.get_clauses(doc_id),db.get_extraction(doc_id),doc_id)
    assert rerun['coverage']['reviewed_sections']==len(doc['clauses'])


def test_reclassification_keeps_owner_and_resets_previous_work(client):
    signup(client);doc_id=upload_domain(client,'finance');db.claim_job();main.run_analysis(doc_id)
    r=client.post(f'/api/documents/{doc_id}/workspace',json={'domain':'court'})
    assert r.status_code==202 and r.json()['status']=='queued'
    assert db.get_context(doc_id)['domain']=='court'
    doc=client.get('/api/documents/'+doc_id).json()
    assert doc['analysis'] is None and doc['job_match'] is None
    assert client.post(f'/api/documents/{doc_id}/workspace',json={'domain':'medical'}).status_code==409
    client.post('/api/auth/logout');signup(client,'outsider@example.test')
    assert client.post(f'/api/documents/{doc_id}/workspace',json={'domain':'medical'}).status_code==404


def test_optional_vision_adapter_and_uncertainty(monkeypatch):
    import time,httpx,pymupdf,medical_vision
    monkeypatch.setenv('GROQ_VISION_MODEL','test-image-model')
    monkeypatch.setenv('GROQ_API_KEY','test-no-real-key')
    def handler(request):
        body=json.loads(request.content)
        assert body['model']=='test-image-model'
        assert body['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'text':'Medicine [[illegible]], dose [[unclear?]]. Verify with pharmacist.'})}}]})
    original=httpx.Client
    monkeypatch.setattr(medical_vision.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pymupdf.open() as pdf:
        page=pdf.new_page()
        result,confidence=medical_vision.read_page(page,time.monotonic()+30)
    assert '[[illegible]]' in result and confidence is None


def test_optional_vision_upload_requires_review_and_preserves_pages(monkeypatch):
    import medical_vision,pymupdf
    from PIL import Image
    monkeypatch.setenv('MEDICAL_IMAGE_READER','vision')
    monkeypatch.setattr(medical_vision,'read_page',lambda *a:('Fictional report for testing only. Reported value: 42. Verify this unclear result with the original.',None))
    image=io.BytesIO();Image.new('RGB',(600,800),'white').save(image,format='PNG')
    text,sections,pages,info=document_input.parse(image.getvalue(),'report.png','medical','review')
    assert info['ocr_pages']==[1] and info['reader']=='groq-vision'
    assert '42' in text and pages==1 and sections


def test_resume_skill_cannot_be_invented_from_an_unrelated_quote():
    value={'plain_summary':'A fictional resume profile.','document_type':'Resume','facts':[{'category':'skill','value':'Python','clause_index':0,'quote':'Skills: Java.'}]}
    with pytest.raises(ValueError):domains.validate_part(value,[{'clause_index':0,'page':1,'text':'Skills: Java.'}],'hr','resume')


def test_resume_dense_skill_list_and_certification_are_supported():
    skills=[f'Tool{i:02}' for i in range(30)]
    source=[{'clause_index':4,'page':2,'text':'Skills: '+', '.join(skills)+'. Certificate: Cloud Foundations. Project: Document Reader.'}]
    facts=[dict(category='skill',value=skill,clause_index=4,quote=skill) for skill in skills]
    facts += [dict(category='certification',value='Cloud Foundations',clause_index=4,quote='Certificate: Cloud Foundations.'),
              dict(category='project',value='Document Reader',clause_index=4,quote='Project: Document Reader.')]
    result=domains.validate_part(dict(plain_summary='A fictional profile with documented skills and a certificate.',document_type='Resume',facts=facts),source,'hr','resume')
    analysis=domains.enrich({},[result],source,'hr','resume')
    assert len(analysis['resume_profile']['skills_clean'])==30
    assert analysis['resume_profile']['certification'][0]['page']==2
    assert analysis['resume_profile']['project'][0]['value']=='Document Reader'
    facts[-2]['value']='Invented Advanced Certificate'
    with pytest.raises(ValueError):
        domains.validate_part(dict(plain_summary='A fictional resume profile.',document_type='Resume',facts=facts),source,'hr','resume')


def test_resume_batches_are_small_and_preserve_every_character(monkeypatch):
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    source=[{'clause_index':3,'page':1,'text':('Skills: Python, SQL, Docker. '*80)},
            {'clause_index':8,'page':2,'text':'Certifications: Cloud Foundations.'}]
    batches=domain_review.plan(source,{},'hr','resume')
    assert all(len(batch)==1 and len(batch[0]['text'].encode('utf-8'))<=1000 for batch in batches)
    for section in source:
        assert ''.join(c['text'] for batch in batches for c in batch if c['clause_index']==section['clause_index'])==section['text']


def test_resume_schema_repair_explains_constraints_without_private_input(monkeypatch):
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    source=[{'clause_index':0,'page':1,'text':'Skills: Python.'}]
    calls=[]
    def generate(system,payload,schema,tokens):
        calls.append(system)
        value=dict(plain_summary='A fictional sourced resume profile.',document_type='Resume',facts=[dict(category='skill',value='Python',clause_index=0,quote='Python')])
        if len(calls)==1:
            value['facts'][0]['detail']='private-resume-value '*50
            schema.model_validate(value)
        return value
    monkeypatch.setattr(llm,'call_json',generate)
    result=domain_review.review(source,{},None,'hr','resume')
    assert result['resume_profile']['skills_clean']==['Python']
    assert 'facts.0.detail: string_too_long' in calls[1]
    assert 'private-resume-value' not in calls[1]


def test_resume_schema_error_is_not_reported_as_source_mismatch(monkeypatch):
    from provider_errors import ProviderError
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    def invalid(system,payload,schema,tokens):
        return schema.model_validate(dict(plain_summary='A fictional resume.',document_type='Resume',facts=[dict(category='unsupported',value='Python',clause_index=0,quote='Python')]))
    monkeypatch.setattr(llm,'call_json',invalid)
    with pytest.raises(ProviderError,match='output format'):
        domain_review.review([{'clause_index':0,'page':1,'text':'Skills: Python.'}],{},None,'hr','resume')


def test_hyphenated_pdf_line_wrap_preserves_the_actual_source_quote():
    text='Built with Sentence-\n    Transformers for document search.'
    value=dict(plain_summary='A fictional profile with a documented library.',document_type='Resume',facts=[
        dict(category='skill',value='Sentence-Transformers',quote='Built with Sentence-Transformers',clause_index=6)])
    result=domains.validate_part(value,[dict(clause_index=6,page=2,text=text)],'hr','resume')
    assert result['facts'][0]['quote']=='Built with Sentence-\n    Transformers'
    assert llm.source_quote('Sentence-Transformers','Sentence- unrelated Transformers') is None
    assert llm.source_quote('Sentence-Transformers','Sentence-\nNotTransformers') is None
    assert llm.source_quote('SentenceTransformers',text) is None


def test_resume_source_retry_identifies_the_bad_entry_without_accepting_it(monkeypatch):
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    source=[dict(clause_index=6,page=2,text='Certificate: Cloud Foundations.')]
    calls=[]
    def generate(system,payload,schema,tokens):
        calls.append((system,payload))
        if len(calls)==1:
            fact=dict(category='certification',value='Imaginary Expert Credential',quote='Certificate: Cloud Foundations.',clause_index=6)
        else:
            assert payload['validation_issue']['field']=='facts.0.value'
            assert payload['validation_issue']['previous_entry']['value']=='Imaginary Expert Credential'
            assert 'Imaginary Expert Credential' not in system
            fact=dict(category='certification',value='Cloud Foundations',quote='Certificate: Cloud Foundations.',clause_index=6)
        return dict(plain_summary='A certificate explicitly stated in the resume.',document_type='Resume',facts=[fact])
    monkeypatch.setattr(llm,'call_json',generate)
    result=domain_review.review(source,{},None,'hr','resume')
    assert result['resume_profile']['certification'][0]['value']=='Cloud Foundations'
    assert len(calls)==2


def test_resume_repeated_unsupported_suggestions_keep_only_verified_facts(monkeypatch):
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    source=[dict(clause_index=6,page=2,text='Built a MERN application using Node.js and MongoDB.')]
    calls=[]
    def generate(*args):
        calls.append(args)
        return dict(plain_summary='The candidate knows React and invented-tool.',document_type='Unverified title',facts=[
            dict(category='skill',value='Node.js',clause_index=6,quote='using Node.js'),
            dict(category='skill',value='React',clause_index=6,quote='MERN application'),
            dict(category='skill',value='invented-tool',clause_index=6,quote='not a real quotation'),
            dict(category='skill',value='MongoDB',clause_index=999,quote='MongoDB'),
            dict(category='skill',value='MongoDB',clause_index=6,quote='MongoDB'),
        ])
    monkeypatch.setattr(llm,'call_json',generate)
    result=domain_review.review(source,{},None,'hr','resume')
    assert len(calls)==2
    assert result['resume_profile']['skills_clean']==['MongoDB','Node.js']
    assert result['verification_warnings']==[dict(omitted_facts=3,clause_indices=[6])]
    assert '3 AI-suggested resume entries failed source checks' in result['review_note']
    assert 'React' not in json.dumps(result) and 'invented-tool' not in json.dumps(result)
    assert result['document_type']=='Resume'
    assert all(f['page']==2 for f in result['resume_profile']['skills_detail'])
    assert result['coverage']['reviewed_sections']==1


def test_entirely_unsupported_resume_still_fails_after_repair(monkeypatch):
    from provider_errors import ProviderError
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    monkeypatch.setattr(llm,'call_json',lambda *a:dict(plain_summary='A fictional resume profile.',document_type='Resume',facts=[
        dict(category='skill',value='React',clause_index=0,quote='MERN application')]))
    with pytest.raises(ProviderError,match='source-verified'):
        domain_review.review([dict(clause_index=0,page=1,text='MERN application')],{},None,'hr','resume')


def test_non_resume_source_failures_are_not_filtered(monkeypatch):
    from provider_errors import ProviderError
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    monkeypatch.setattr(llm,'call_json',lambda *a:dict(plain_summary='A fictional medical report.',document_type='Report',key_terms=[],risky_clauses=[],flagged_values=[
        dict(test_name='Glucose',reported_value='105 mg/dL',normal_range='Not stated',why_flagged='Check source',clause_index=0,quote='invented quote')]))
    with pytest.raises(ProviderError,match='source-verified'):
        domain_review.review([dict(clause_index=0,page=1,text='Glucose 105 mg/dL')],{},None,'medical','review')


def test_resume_exclusion_warning_survives_cached_analysis(client,monkeypatch):
    signup(client);doc_id=upload_domain(client,'hr','resume')
    monkeypatch.setattr(config,'AI_PROVIDER','groq')
    def generate(system,payload,schema,tokens):
        c=payload['clauses'][0]
        return dict(plain_summary='An unsupported claim about private-invented-tool.',document_type='Resume',facts=[
            dict(category='skill',value=c['text'][:20],clause_index=c['clause_index'],quote=c['text'][:20]),
            dict(category='skill',value='private-invented-tool',clause_index=c['clause_index'],quote=c['text'][:20])])
    monkeypatch.setattr(llm,'call_json',generate)
    source=db.get_clauses(doc_id)
    result=domain_review.review(source,{},doc_id,'hr','resume')
    assert result['verification_warnings']
    monkeypatch.setattr(llm,'call_json',lambda *a:pytest.fail('Validated cache should be reused'))
    assert domain_review.review(source,{},doc_id,'hr','resume')==result
    assert 'private-invented-tool' not in json.dumps(db.batch_state(doc_id))
