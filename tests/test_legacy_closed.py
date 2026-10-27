"""Legacy invalid FIRST closures cannot reopen template writes without local handles."""
from pathlib import Path
from copy import deepcopy
import json,subprocess,selectors
import pytest
from parkweave import service_case_steps
from parkweave.store import Conflict,digest
from parkweave.template_consumer import canonical
from test_template_consumer import template_consumption,headers,products
from test_template_consumer_planning import preview,adoption,post,edit
from test_template_partial import partial,recover,journal
from test_template_terminal import finish_body

def legacy(f,monkeypatch):
    row=partial(f);v=preview(f,row).json();data={**adoption(v),'partial_adoption':True};original=service_case_steps.adopt
    def refusal(*a,**kw):raise Conflict('SYNTHETIC old first refusal was wrongly finalized')
    monkeypatch.setattr(service_case_steps,'adopt',refusal);assert post(f,row,'adopt',data,'legacy-first').status_code==409
    monkeypatch.setattr(service_case_steps,'adopt',original)
    p=recover(f,row,'legacy-first').json();request=finish_body(p)
    meta=dict(original_request_key=p['original_request_key'],body_sha256=p['body_sha256'],state='CLOSED_NOT_COMMITTED',proof_kind='FIRST_DEFINITE_REFUSAL',refusal_code='FIRST_PRODUCT_CONFLICT',request=request,fingerprint=digest(canonical(request)))
    with f['repository'].connect(write=True) as c:c.execute("UPDATE consumer_stages SET state='CLOSED_NOT_COMMITTED',result=?,error=NULL WHERE name LIKE 'CONFIRM_PLAN_%'",(canonical({'consumer_finalization':meta}),))
    return row,v,data,p

def test_cold_instance_and_new_key_adoption_remain_unresolved_without_any_browser_handle(template_consumption,monkeypatch):
    f=template_consumption;row,v,data,p=legacy(f,monkeypatch);saved=journal(f);before=products(f['owner'],include_audit=True)
    cold=f['client'].get('/api/template-consumer/instances/'+row['instance_id'],headers=headers(f));assert cold.status_code==200
    assert cold.json()['state']=='UNKNOWN' and cold.json()['adoption_quarantined'] is True
    assert post(f,row,'adopt',data,'new-key-after-old-cleanup').status_code==409
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before

def test_actual_cold_template_page_with_no_handle_cannot_preview_or_adopt_legacy_first(template_consumption,monkeypatch):
    f=template_consumption;row,v,data,p=legacy(f,monkeypatch);saved=journal(f);before=products(f['owner'],include_audit=True);messages=[];summary=None
    proc=subprocess.Popen(['node','tests/legacy_closed_actual.js',row['instance_id']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert sel.select(timeout=15),'legacy cold page bridge timeout'
            line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None
            r=f['client'].request(method,q['path'],headers=headers(f,key=o.get('headers',{}).get('Idempotency-Key')),json=body);messages.append({'method':method,'path':q['path'],'status':r.status_code});assert r.status_code<400,r.text
            proc.stdin.write((json.dumps({'status':r.status_code,'body':r.json()})+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read().decode();assert summary and summary['checks']>=7
        assert all(q['method']=='GET' for q in messages)
        assert journal(f)==saved and products(f['owner'],include_audit=True)==before
    finally:
        Path('.runtime/legacy-closed-20261014/cold-page-chain.json').write_text(json.dumps({'summary':summary,'requests':messages,'zero_business_and_journal_writes':journal(f)==saved and products(f['owner'],include_audit=True)==before},indent=2)+'\n')
        sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
