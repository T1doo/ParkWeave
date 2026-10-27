"""Synthetic contract/refusal tests only; no formal source is accepted or read."""
import json
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from parkweave.api import create_app, configured_app
from parkweave import formal_preparation_entry as formal
from parkweave.store import Denied
from test_preparation import preparation_fixture, headers
from test_native_preparation_entry import snapshot

STATUS='/api/formal-preparations/entry-status'
ENTRY='/api/formal-preparations/entry'


def selection():
    # Opaque contract examples, never real records or purported real evidence.
    return dict(source_domain='contract-test-source.example',preparation_id='same-id',case_id='same-id',
                run_id='same-id',plan_id='same-id',preparation_revision=1,plan_revision=1,
                service_id='contract-test-service',service_version=1,source_revision_sha256='a'*64)


def config(**changes):
    return json.dumps(dict(schema_version='parkweave-formal-preparation-read-config/1',source_kind='AUTHORIZED_BUSINESS',
                          source_id='CONTRACT_TEST_SOURCE',provenance_contract_id='UNKNOWN_REAL_CONTRACT',
                          park_id='park-a',org_id='org-a',binding=selection(),**changes))


def interfaces(kind='AUTHORIZED_BUSINESS'):
    calls=[]
    def read(refs):calls.append('reader');raise AssertionError('no external source access permitted')
    def verify(refs,raw):calls.append('verifier');return {'REAL':True,'verified':True}
    return formal.FormalSourceReader('CONTRACT_TEST_SOURCE',selection()['source_domain'],kind,read),formal.IndependentProvenanceVerifier(selection()['source_domain'],'UNKNOWN_REAL_CONTRACT',verify),calls


def app(f,monkeypatch,cfg=None,reader=None,verifier=None):
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn)
    monkeypatch.delenv('PARKWEAVE_RUNTIME_READ_CONFIG',raising=False)
    if cfg is None:monkeypatch.delenv('PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG',raising=False)
    else:monkeypatch.setenv('PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG',cfg)
    return configured_app(formal_source_reader=reader,formal_provenance_verifier=verifier)


def closed(x,reason):
    assert x['state']=='UNAVAILABLE' and x['reason']==reason and x['read_only'] is True
    for field in ('source_proofs_verified','source_access_attempted','business_record_read','entry_available',
                  'current_source_subject_authority_verified','approval_granted','resource_plan_approval_available',
                  'execution_authorized','decision_writes_enabled','synthetic_contract_tests_are_real_source_acceptance'):
        assert x[field] is False
    assert x['unimplemented_source_contracts']==list(formal.PROOFS)
    assert 'SOURCE_SPECIFIC_PROVENANCE_ADAPTER' in x['unimplemented_integration']
    assert 'EXISTING_AUTHORIZED_SOURCE_STRUCTURE_AND_RECORDS' in x['external_inputs_required']


@pytest.mark.parametrize('actor',['fixture-a','prep-specialist-fixture-a'])
def test_default_factory_restart_only_checks_existing_local_grant_never_reads_business(preparation_fixture,monkeypatch,actor):
    f=preparation_fixture;before=snapshot(f[1])
    for _ in range(2):
        with TestClient(app(f,monkeypatch)) as api:
            for path,params in ((STATUS,None),(ENTRY,selection())):
                r=api.get(path,params=params,headers=headers(f[2],actor));assert r.status_code==200
                closed(r.json(),'FORMAL_SOURCE_CONFIG_NOT_PROVIDED')
            assert api.post(ENTRY,headers=headers(f[2],actor),json={'REAL':True}).status_code==405
    assert snapshot(f[1])==before


@pytest.mark.parametrize('missing,reason',[('reader','FORMAL_SOURCE_READER_NOT_PROVIDED'),
    ('verifier','INDEPENDENT_FORMAL_PROVENANCE_NOT_PROVIDED'),('none','FORMAL_PROVENANCE_CONTRACT_NOT_IMPLEMENTED'),
    ('synthetic','FORMAL_SOURCE_TYPE_REFUSED'),('public','FORMAL_SOURCE_TYPE_REFUSED'),
    ('reader-domain','FORMAL_SOURCE_READER_BINDING_REFUSED'),('reader-id','FORMAL_SOURCE_READER_BINDING_REFUSED'),
    ('verifier-domain','INDEPENDENT_FORMAL_PROVENANCE_BINDING_REFUSED'),('verifier-contract','INDEPENDENT_FORMAL_PROVENANCE_BINDING_REFUSED')])
def test_missing_or_self_declared_interfaces_never_open_unknown_real_contract(preparation_fixture,monkeypatch,missing,reason):
    f=preparation_fixture;reader,verifier,calls=interfaces()
    if missing=='reader':reader=None
    elif missing=='verifier':verifier=None
    elif missing=='synthetic':reader=replace(reader,source_kind='SYNTHETIC_CONTRACT_FIXTURE')
    elif missing=='public':reader=replace(reader,source_kind='PUBLIC')
    elif missing=='reader-domain':reader=replace(reader,source_domain='other-source.example')
    elif missing=='reader-id':reader=replace(reader,source_id='other-source')
    elif missing=='verifier-domain':verifier=replace(verifier,source_domain='other-source.example')
    elif missing=='verifier-contract':verifier=replace(verifier,contract_id='other-proof')
    before=snapshot(f[1])
    with TestClient(app(f,monkeypatch,config(),reader,verifier)) as api:
        for path,params in ((STATUS,None),(ENTRY,selection())):
            r=api.get(path,params=params,headers=headers(f[2]));assert r.status_code==200;closed(r.json(),reason)
    assert calls==[] and snapshot(f[1])==before


@pytest.mark.parametrize('field',list(selection()))
def test_exact_domain_object_service_revision_or_fingerprint_mismatch_never_calls_source(preparation_fixture,monkeypatch,field):
    f=preparation_fixture;reader,verifier,calls=interfaces();query=selection()
    query[field]=(2 if field.endswith(('revision','version')) else 'b'*64 if field.endswith('sha256') else 'other-source-or-id')
    with TestClient(app(f,monkeypatch,config(),reader,verifier)) as api:
        assert api.get(ENTRY,params=query,headers=headers(f[2])).status_code==409
    assert calls==[]


@pytest.mark.parametrize('damage',['READ','PREPARE','identity','foreign-tenant'])
def test_current_authorization_denied_before_any_source_even_after_restart(preparation_fixture,monkeypatch,damage):
    f=preparation_fixture;reader,verifier,calls=interfaces()
    if damage!='foreign-tenant':
        with f[1].connect() as c:
            if damage=='identity':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
            elif damage=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            else:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
    actor='fixture-b' if damage=='foreign-tenant' else 'fixture-a';before=snapshot(f[1])
    for _ in range(2):
        with TestClient(app(f,monkeypatch,config(),reader,verifier)) as api:
            assert api.get(STATUS,headers=headers(f[2],actor)).status_code==403
            assert api.get(ENTRY,params=selection(),headers=headers(f[2],actor)).status_code==403
    assert calls==[] and snapshot(f[1])==before


@pytest.mark.parametrize('extra',['verified','REAL','allow_synthetic','writer_dsn','signature','history','plan_approval_id'])
def test_http_cannot_declare_source_type_proof_or_activation(preparation_fixture,monkeypatch,extra):
    f=preparation_fixture
    with TestClient(app(f,monkeypatch)) as api:
        assert api.get(ENTRY,params={**selection(),extra:'true'},headers=headers(f[2])).status_code==422
        assert api.get(STATUS,params={extra:'true'},headers=headers(f[2])).status_code==422
        assert api.get(ENTRY,params=[*selection().items(),('source_domain','other')],headers=headers(f[2])).status_code==422


def test_domains_and_object_types_never_alias_same_ids():
    original=formal.Selection(**selection()).references()
    changed=formal.Selection(**{**selection(),'source_domain':'other-source.example'}).references()
    assert len(set(original))==4 and set(original).isdisjoint(changed)
    assert {r.object_type for r in original}=={'PREPARATION','CASE','RUN','ADOPTED_PLAN'}
    with pytest.raises(ValidationError):formal.SourceReference(source_domain='x',object_type='SIGNATURE',record_id='same-id')


def test_lookup_binds_current_subject_metadata_and_purpose_without_accepting_authority_claims():
    values=dict(selection=formal.Selection(**selection()),viewer_id='fixture-a',park_id='park-a',org_id='org-a',
                role='enterprise_operator',purpose='READ_EXISTING_PREPARATION')
    lookup=formal.FormalReadLookup(**values)
    assert lookup.selection.references()[0].source_domain==selection()['source_domain']
    for extra in ('verified','token','writer_dsn','source_subject_authorized'):
        with pytest.raises(ValidationError):formal.FormalReadLookup(**values,**{extra:True})
    with pytest.raises(ValidationError):formal.FormalReadLookup(**{**values,'purpose':'EXECUTE'})


def test_public_config_rejects_boolean_revision_instead_of_coercing_it_to_one():
    value=json.loads(config());value['binding']['plan_revision']=True
    with pytest.raises(Denied,match='values not echoed'):formal.dependencies(json.dumps(value),None,None)


@pytest.mark.parametrize('damage',['fixture-kind','duplicate','verified','credentials'])
def test_config_is_only_narrowing_no_boolean_proof_credentials_or_synthetic_override(damage):
    raw=config()
    if damage=='duplicate':raw=raw[:-1]+',"source_kind":"AUTHORIZED_BUSINESS"}'
    else:
        v=json.loads(raw)
        if damage=='fixture-kind':v['source_kind']='SYNTHETIC_CONTRACT_FIXTURE'
        else:v[damage]='SYNTHETIC_REJECT_THIS_VALUE'
        raw=json.dumps(v)
    with pytest.raises(Denied,match='values not echoed'):formal.dependencies(raw,None,None)


def test_isolated_native_resource_approval_readers_and_boolean_verifiers_are_not_formal_proofs():
    from parkweave.native_run_access import NativeRunAccess
    from parkweave.service_plan_approval import IsolatedPlanApproval
    from parkweave.resource_plan_approval_read import ReadOnlyApprovalProvider
    for value in (object.__new__(NativeRunAccess),object.__new__(IsolatedPlanApproval),ReadOnlyApprovalProvider('x',lambda x:None,lambda x,y:True),{'REAL':True,'verified':True}):
        with pytest.raises(Denied,match='formal source reader'):formal.dependencies(None,value,None)
    with pytest.raises(Denied,match='provenance verifier'):formal.dependencies(None,None,True)
    reader,_,_=interfaces()
    verifier=formal.IndependentProvenanceVerifier(reader.source_domain,'UNKNOWN_REAL_CONTRACT',reader.read_existing)
    with pytest.raises(Denied,match='independent provenance'):formal.dependencies(None,reader,verifier)
