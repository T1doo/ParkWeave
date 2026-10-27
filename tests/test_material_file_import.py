"""Real material-candidate parsing and original material writes; synthetic only."""
import base64
import hashlib
import csv
import io
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from parkweave import material_file_import as files,preparation as prep
from parkweave.api import configured_app
from test_preparation import preparation_fixture,create,command,headers,read
from test_native_preparation_entry import snapshot


def encoded(raw):return base64.b64encode(raw).decode('ascii')
def body(p,name='SYNTHETIC.txt',raw=b'SYNTHETIC new material'):
    return dict(expected_preparation_revision=p['revision'],expected_case_id=p['case_id'],expected_run_id=p['run_id'],
                data_classification='SYNTHETIC_SAMPLE',file_name=name,content_base64=encoded(raw))
def path(p):return '/api/preparations/'+p['preparation_id']+'/material-file-candidate'
def ordinary(f,monkeypatch):
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn);monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    for key in ('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG'):monkeypatch.delenv(key,raising=False)
    return configured_app()


@pytest.mark.parametrize('name,raw,expected,kind',[
    ('样例.TXT','\ufeff  SYNTHETIC中文\r\n第二行  '.encode(),'SYNTHETIC中文\n第二行','TEXT'),
    ('样例.md',b'# SYNTHETIC\n<img src=x onerror=alert(1)>','# SYNTHETIC\n<img src=x onerror=alert(1)>','MARKDOWN'),
    ('样例.csv',b'name,notes\r\n"SYNTHETIC,a","line1\nline2"\r\n','"name","notes"\n"SYNTHETIC,a","line1\nline2"','CSV'),
    ('样例.json',b'{"employees":37,"statement":"SYNTHETIC"}','{"employees":37,"statement":"SYNTHETIC"}','JSON'),
    ('formula.csv',b'item,value\nSYNTHETIC,=1+1\n','"item","value"\n"SYNTHETIC","=1+1"','CSV'),
    ('array.json','["合成",1,true,null]'.encode(),'["合成",1,true,null]','JSON'),
])
def test_formats_preserve_plain_text_without_extracting_facts_or_executing_content(name,raw,expected,kind):
    x=files.parse(name,encoded(raw));assert x['candidate_text']==expected and x['format']==kind
    assert x['raw_file_sha256']==hashlib.sha256(raw).hexdigest() and x['candidate_sha256']==hashlib.sha256(expected.encode()).hexdigest()
    assert x['authenticity']=='UNVERIFIED' and x['source_kind']=='DOCUMENT_EXCERPT' and 'SYNTHETIC' in x['source_label']
    assert files.units(x['source_label'])<=200


@pytest.mark.parametrize('name,raw,reason',[
    ('../secret.txt',b'x','SAFE_FILE_NAME_REQUIRED'),('C:\\secret.txt',b'x','SAFE_FILE_NAME_REQUIRED'),
    ('hidden.txt:stream',b'x','SAFE_FILE_NAME_REQUIRED'),('NUL.txt',b'x','SAFE_FILE_NAME_REQUIRED'),
    ('x\n.txt',b'x','SAFE_FILE_NAME_REQUIRED'),('\ud800.txt',b'x','SAFE_FILE_NAME_REQUIRED'),
    ('x.html',b'<script>bad()</script>','SUPPORTED_TEXT_FORMAT_REQUIRED'),
    ('x.txt',b'','FILE_BYTE_LIMIT'),('x.txt',b'x'*8193,'FILE_BYTE_LIMIT'),
    ('x.txt',b'\xff\xfe','UTF8_TEXT_REQUIRED'),('x.txt',b'a\x00b','PLAIN_TEXT_REQUIRED'),
    ('x.txt',b'   \r\n','CANDIDATE_TEXT_LIMIT'),('x.txt',b'x'*4001,'CANDIDATE_TEXT_LIMIT'),
    ('x.json',b'{"x":1,"x":2}','JSON_DUPLICATE_FIELD'),
    ('x.json',b'{"x":{"y":1,"y":2}}','JSON_DUPLICATE_FIELD'),
    ('x.json',b'{"x":NaN}','JSON_FINITE_VALUES_REQUIRED'),
    ('x.json',b'{"x":"\\ud800"}','UTF8_TEXT_REQUIRED'),
    ('x.json',b'"scalar"','JSON_OBJECT_OR_ARRAY_REQUIRED'),
    ('x.json',b'{wrong}','VALID_JSON_REQUIRED'),
    ('x.json',b'['*10+b'0'+b']'*10,'JSON_COMPLEXITY_LIMIT'),
    ('x.json',json.dumps(list(range(256))).encode(),'JSON_COMPLEXITY_LIMIT'),
    ('x.csv',b'name,name\na,b','CSV_DISTINCT_HEADERS_REQUIRED'),
    ('x.csv',b'name, name\na,b','CSV_DISTINCT_HEADERS_REQUIRED'),
    ('x.csv',b'name, \na,b','CSV_DISTINCT_HEADERS_REQUIRED'),
    ('x.csv',b'name,value\na,b,c','CSV_ROW_WIDTH_MISMATCH'),
    ('x.csv',b'name,value\n"unterminated,b','VALID_CSV_REQUIRED'),
    ('x.csv',('name\n'+'x\n'*101).encode(),'CSV_TABLE_LIMIT'),
    ('x.csv',(','.join('c'+str(i) for i in range(33))).encode(),'CSV_TABLE_LIMIT'),
])
def test_bad_or_ambiguous_files_refuse_without_truncating_or_inventing_data(name,raw,reason):
    with pytest.raises(files.FileCandidateError,match='^'+reason+'$'):files.parse(name,encoded(raw))


def test_exact_text_limit_and_non_bmp_units_and_bad_base64():
    assert len(files.parse('x.txt',encoded(b'x'*4000))['candidate_text'])==4000
    assert files.units(files.parse('x.txt',encoded(('😀'*2000).encode()))['candidate_text'])==4000
    with pytest.raises(files.FileCandidateError,match='CANDIDATE_TEXT_LIMIT'):files.parse('x.txt',encoded(('😀'*2001).encode()))
    with pytest.raises(files.FileCandidateError,match='VALID_BASE64_REQUIRED'):files.parse('x.txt','!!notbase64!!')


@pytest.mark.parametrize('raw',[b'{"n":1e-999}',b'{"n":1e999}',b'{"n":1.23456789012345678901234567890123456789}',b'{"n":-0.0,"i":12345678901234567890123456789}',b'{"n":1e999999999999999999999999999999}',b'{"n":1e-999999999999999999999999999999}'])
def test_json_validated_without_rewriting_any_numeric_lexeme(raw):
    assert files.parse('x.json',encoded(raw))['candidate_text']==raw.decode()


@pytest.mark.parametrize('raw',[b'h,v\nSYNTHETIC,tail  \n',b' h ,v\n lead , tail \n',b'h,v\nSYNTHETIC,"line1\nline2 "\n'])
def test_csv_roundtrip_preserves_every_field_value_even_after_original_strip(raw):
    candidate=files.parse('x.csv',encoded(raw))['candidate_text'].strip()
    assert list(csv.reader(io.StringIO(candidate)))==list(csv.reader(io.StringIO(raw.decode())))


def test_actual_http_raw_file_boundary_fits_unchanged_global_body_cap(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=create(f);before=snapshot(f[1]);raw=b' '*(8192-9)+b'SYNTHETIC'
    with TestClient(ordinary(f,monkeypatch)) as api:
        data=body(p,raw=raw);assert len(json.dumps(data).encode())<16384
        r=api.post(path(p),json=data,headers=headers(f[2]));assert r.status_code==200 and r.json()['file_bytes']==8192 and r.json()['candidate_text']=='SYNTHETIC'
        r=api.post(path(p),json=body(p,raw=raw+b' '),headers=headers(f[2]));assert r.status_code==422 and r.json()['detail']=='FILE_BYTE_LIMIT'
        assert api.post(path(p),content=b' '*16385,headers=headers(f[2])).status_code==413
    assert snapshot(f[1])==before


@pytest.mark.parametrize('damage',['filename-surrogate','filename-overlong-surrogate','invalid-utf8','classification-surrogate','extra-private-input'])
def test_actual_http_invalid_input_has_stable_error_without_private_echo(preparation_fixture,monkeypatch,damage):
    f=preparation_fixture;p,_,_=create(f);before=snapshot(f[1]);data=body(p)
    if damage=='filename-surrogate':data['file_name']='\ud800.txt'
    elif damage=='filename-overlong-surrogate':data['file_name']='x'*100+'\ud800'
    elif damage=='classification-surrogate':data['data_classification']='\ud800'
    elif damage=='extra-private-input':data['private']='SYNTHETIC-private-marker'
    raw=json.dumps(data).encode() if damage!='invalid-utf8' else b'{"file_name":"\xff"}'
    with TestClient(ordinary(f,monkeypatch)) as api:
        r=api.post(path(p),content=raw,headers={**headers(f[2]),'Content-Type':'application/json'})
        expected=(400,{'detail':'There was an error parsing the body'}) if damage=='invalid-utf8' else (422,{'detail':'invalid bounded material file request'})
        assert (r.status_code,r.json())==expected
        assert 'SYNTHETIC-private-marker' not in r.text and '\\ud800' not in r.text
    assert snapshot(f[1])==before


def test_actual_http_extreme_json_exponents_preserve_original_lexeme(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=create(f);before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:
        for raw in (b'{"n":1e999999999999999999999999999999}',b'{"n":1e-999999999999999999999999999999}'):
            r=api.post(path(p),json=body(p,'SYNTHETIC.json',raw),headers=headers(f[2]))
            assert r.status_code==200 and r.json()['candidate_text']==raw.decode()
    assert snapshot(f[1])==before


@pytest.mark.parametrize('name,raw',[('SYNTHETIC.txt',b'first'),('SYNTHETIC.md',b'# second'),('SYNTHETIC.csv',b'a,b\n1,2'),('SYNTHETIC.json',b'{"employees":37}')])
def test_ordinary_api_candidate_only_reads_current_owner_scope_and_persists_nothing(preparation_fixture,monkeypatch,name,raw):
    f=preparation_fixture;p,_,_=create(f);before=snapshot(f[1])
    with f[1].connect() as c:before_facts=c.execute('SELECT count(*) n FROM fact_assertions').fetchone()['n']
    with TestClient(ordinary(f,monkeypatch)) as api:
        r=api.post(path(p),json=body(p,name,raw),headers=headers(f[2]));assert r.status_code==200,r.text
        x=r.json();assert (x['preparation_id'],x['case_id'],x['run_id'],x['preparation_revision'])==(p['preparation_id'],p['case_id'],p['run_id'],p['revision'])
        assert not x['persisted'] and x['original_submission_required'] and x['scope']=='SYNTHETIC_LOCAL_PREPARATION_ONLY'
        assert 'content_base64' not in x
    assert snapshot(f[1])==before
    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM fact_assertions').fetchone()['n']==before_facts


@pytest.mark.parametrize('field',['expected_case_id','expected_run_id','expected_preparation_revision'])
def test_changed_case_run_revision_rejected_before_parsing_file(preparation_fixture,monkeypatch,field):
    f=preparation_fixture;p,_,_=create(f);data=body(p);data[field]=(p['revision']+1 if field.endswith('revision') else str(uuid4()));data['content_base64']='bad!!'
    before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:assert api.post(path(p),json=data,headers=headers(f[2])).status_code==409
    assert snapshot(f[1])==before


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_other_tenant_park_or_assigned_reviewer_cannot_use_owner_file_entry(preparation_fixture,monkeypatch,actor):
    f=preparation_fixture;p,_,_=create(f);before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:assert api.post(path(p),json=body(p),headers=headers(f[2],actor)).status_code==403
    assert snapshot(f[1])==before


@pytest.mark.parametrize('damage',['READ','PREPARE','identity','reviewer','catalog'])
def test_revoked_or_missing_current_entry_conditions_stay_refused_after_factory_restart(preparation_fixture,monkeypatch,damage):
    f=preparation_fixture;p,_,_=create(f)
    with f[1].connect() as c:
        if damage=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif damage=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        elif damage=='identity':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif damage=='reviewer':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a'")
        else:c.execute("UPDATE preparation_catalog SET source='{}'::jsonb WHERE park_id='park-a'")
    before=snapshot(f[1])
    for _ in range(2):
        with TestClient(ordinary(f,monkeypatch)) as api:assert api.post(path(p),json=body(p),headers=headers(f[2])).status_code==(409 if damage=='catalog' else 403)
    assert snapshot(f[1])==before


def test_candidate_fills_original_command_then_review_confirmation_and_key_recovery(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=create(f);key=str(uuid4())
    with TestClient(ordinary(f,monkeypatch)) as api:
        result=api.post(path(p),json=body(p,'SYNTHETIC.json',b'{"need":"SYNTHETIC imported request"}'),headers=headers(f[2])).json()
    data=dict(slot='need_summary',text=result['candidate_text'],source_kind=result['source_kind'],source_label=result['source_label'])
    first=command(f,p,'ADD_EVIDENCE',key=key,**data);assert first.status_code==200,first.text
    assert command(f,p,'ADD_EVIDENCE',key=key,**data).json()==first.json()
    p=first.json();record=read(f,p).json();material=record['current_materials'][0]
    assert material['text']==result['candidate_text'] and material['source_sha256']==result['candidate_sha256'] and material['authenticity']=='UNVERIFIED'
    recovery=f[3].get('/api/preparations/'+p['preparation_id']+'/command-recovery',headers=headers(f[2],key=key))
    assert recovery.status_code==200 and recovery.json()['status']=='COMMITTED'
    p=command(f,p,'ADD_EVIDENCE',slot='material_outline',text='SYNTHETIC original material outline',source_kind='DOCUMENT_EXCERPT',source_label='SYNTHETIC original').json()
    p=command(f,p,'REVIEW',user='prep-specialist-fixture-a',reason='SYNTHETIC independent review of actual imported body').json()
    p=command(f,p,'CONFIRM',reason='SYNTHETIC owner confirms exact material version').json()
    assert read(f,p).json()['preparation']['state']=='LOCAL_CONFIRMED'
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s',(p['case_id'],)).fetchone()['state']=='NEEDS_INPUT'
        assert c.execute('SELECT count(*) n FROM preparation_events WHERE actor_id=%s AND request_key=%s',('fixture-a',key)).fetchone()['n']==1


def test_preview_cannot_supply_real_classification_or_bypass_original_execute_grant(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=create(f)
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:
        data=body(p);data['data_classification']='REAL';assert api.post(path(p),json=data,headers=headers(f[2])).status_code==422
        data=body(p);data['verified']=True;assert api.post(path(p),json=data,headers=headers(f[2])).status_code==422
        x=api.post(path(p),json=body(p),headers=headers(f[2]));assert x.status_code==200
        x=x.json();r=command(f,p,'ADD_EVIDENCE',slot='need_summary',text=x['candidate_text'],source_kind=x['source_kind'],source_label=x['source_label']);assert r.status_code==403
    assert snapshot(f[1])==before
