"""Existing SIGNED synthetic files exercise the read contract, never real approval."""
from datetime import datetime,timedelta,timezone
import hashlib,hmac,json,secrets
from uuid import uuid4
from pathlib import Path

from fastapi.testclient import TestClient
from parkweave.api import configured_app
from parkweave import resource_plan_approval_read as approval
from test_preparation import headers
from test_ordinary_runtime_read import selection,snapshot
from test_service_case_steps import setup,adopt


class SignedFixtureSource:
    def __init__(self,directory):
        self.path=directory/'SYNTHETIC-existing-approval.json';self.signature=directory/'SYNTHETIC-existing-approval.mac'
        self.head=directory/'SYNTHETIC-authority-current-head.json'
        self.key=secrets.token_bytes(32);self.calls=[];self.on_read=None
        self.provider=approval.ReadOnlyApprovalProvider('SYNTHETIC-existing-source',self.read,self.verify,'SYNTHETIC_CONTRACT_FIXTURE')

    def read(self,lookup):
        self.calls.append(lookup)
        if self.on_read:self.on_read(self,lookup,len(self.calls))
        return self.path.read_bytes() if self.path.exists() else None

    def verify(self,lookup,raw):
        head=json.loads(self.head.read_text())
        return (hashlib.sha256(raw).hexdigest()==head['sha256'] and
                hmac.compare_digest(hmac.new(self.key,raw,hashlib.sha256).hexdigest(),self.signature.read_text()))

    def write(self,record):
        # Explicit isolated fixture setup/mutation only. The API has no write operation.
        data=json.dumps(record,sort_keys=True,separators=(',',':')).encode();self.path.write_bytes(data)
        self.signature.write_text(hmac.new(self.key,data,hashlib.sha256).hexdigest())
        self.head.write_text(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),'record_revision':record['record_revision']})+'\n')

    def record(self):return json.loads(self.path.read_bytes())


def path(p,kind='resource-plan-approval'):
    return '/api/preparations/'+p['preparation_id']+'/runtime/'+kind


def factory(f,monkeypatch,provider=None):
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn);monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    monkeypatch.delenv('PARKWEAVE_RUNTIME_READ_CONFIG',raising=False)
    return configured_app(resource_plan_approval_provider=provider)


def current(api,f,p,actor='fixture-a'):
    r=api.get(path(p,'resource-plan-approval-context'),params=selection(p),headers=headers(f[2],actor));assert r.status_code==200,r.text
    x=r.json();return x,{**selection(p),'expected_plan_id':x['binding']['plan_id'],
                       'expected_plan_revision':x['binding']['plan_revision'],'expected_context_sha256':x['context_sha256']}


def seeded(f,tmp_path,monkeypatch):
    p=setup(f,'LOCAL_CASE_RESOURCE_ASSOCIATION');r=adopt(f,p);assert r.status_code==201,r.text
    source=SignedFixtureSource(tmp_path);app=factory(f,monkeypatch,source.provider)
    with TestClient(app) as api:ctx,query=current(api,f,p)
    now=datetime.now(timezone.utc)
    record=dict(schema_version=approval.CONTRACT,purpose='RESOURCE_PLAN_APPROVAL',source_id=source.provider.source_id,
                approval_id=str(uuid4()),record_revision=1,original_record_id='SYNTHETIC-original-record-1',binding=ctx['binding'],
                approver_id='fixture-a',approver_role='enterprise_operator',authority_reference='SYNTHETIC-existing-authority-reference',
                approved_at=(now-timedelta(seconds=5)).isoformat(),valid_from=(now-timedelta(seconds=1)).isoformat(),
                valid_until=(now+timedelta(minutes=5)).isoformat(),state='APPROVED',revoked_at=None)
    source.write(record)
    return p,source,app,query


def read(api,f,p,query,actor='fixture-a',suffix=''):
    return api.get(path(p)+suffix,params=query,headers=headers(f[2],actor))
