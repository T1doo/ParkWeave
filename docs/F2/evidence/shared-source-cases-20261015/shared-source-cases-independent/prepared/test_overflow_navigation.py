"""Runtime harness regression: original worklist second page, never fixed UUIDs."""
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from conftest import pg, fixture

from test_shared_source_cases_independent import (
    shared_http, link_fixture, receipt_fixture, preparation_fixture,
    no_preparation, run_html, snapshot, stored, headers, material_add, prep_command,
    adopt, verified, GOALS)
from test_request_intents import save
from parkweave.preparation import SERVICE


def test_original_worklist_second_page_anchor_then_unknown_overflow(shared_http,monkeypatch):
    f,_=shared_http; out=Path('.runtime/shared-source-cases-independent/prepared')
    (out/'overflow-redaction-values.private.json').write_text(json.dumps(sorted(f[2].values()))+'\n')
    # All IDs come from the actual original worker; select an existing Run.
    candidates=[no_preparation(f) for _ in range(33)]
    anchor=max(candidates,key=lambda row:str(row['case_id']))
    response=f[3].post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=dict(run_id=str(anchor['run_id']),service_id=SERVICE,service_version=1,reviewer_id='prep-specialist-fixture-a'))
    assert response.status_code==201,response.text
    p=response.json(); p=material_add(f,p).json(); p=material_add(f,p,'material_outline').json()
    p=save(f,p,goals=[GOALS[0]],text='SYNTHETIC existing highest Case explicit P1 request').json()
    p=prep_command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC independent highest Case review').json()
    p=prep_command(f,p,'CONFIRM',reason='SYNTHETIC explicit highest Case confirmation').json()
    assert adopt(f,p).status_code==201; verified(f,p,'P1')
    driver=out/'shared_source_cases_real_html.js'; original_popen=subprocess.Popen
    def prepared_driver(args,*positional,**kwargs):
        if args==['node','tests/shared_source_cases_real_html.js']: args=['node',str(driver)]
        return original_popen(args,*positional,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',prepared_driver)
    before=snapshot(f); result=run_html(f,p,'overflow',{}); assert snapshot(f)==before
    pages=[row for row in result['calls'] if row['path'].startswith('/api/cases/worklist?')]
    assert len(pages)==2 and '&after=' in pages[1]['path']
    assert all(row['method']=='GET' for row in result['calls'])
    record=dict(scope='RUNTIME_PREPARED_HARNESS_NOT_FROZEN_GATE',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        runtime_driver_sha256=hashlib.sha256(driver.read_bytes()).hexdigest(),probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        candidates=33,anchor_rank=33,original_worklist_pages=2,case_ids_not_changed=True,business_writes_during_html=0,
        actual_http=True,actual_asgi=True,owned_pg=True,result=result)
    (out/'overflow-second-page-result.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
