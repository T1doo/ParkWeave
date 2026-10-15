"""Actual PG/API write with one controlled final availability projection seam.

The seam models UNKNOWN with unchanged immutable basis, not an actual timed
expiration. This is separate from business-source/clock tests and formal modules.
"""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json

from parkweave import material_package_continuation as package
from test_plan_source_conflicts import http_f, link_fixture, receipt_fixture, preparation_fixture
from test_plan_source_conflicts import complete, edit
from test_case_opportunities import imported
from test_preparation import headers


def test_final_unknown_same_basis_refuses_without_plan_or_ledger_write(http_f,monkeypatch):
    f=http_f;p,_,_,_=complete(f,local=True);edit(f,p,'SYNTHETIC manual retained')
    _,cards,_=imported(f,p);card=cards['cards'][0]
    base='/api/preparations/'+p['preparation_id']+'/plan-material-package'
    view=f[3].get(base,params={'card_id':card['id']},headers=headers(f[2]));assert view.status_code==200,view.text
    body=deepcopy(view.json()['action_requests']['KEEP_AND_CONTINUE']);body['reason']='SYNTHETIC final UNKNOWN independent seam'
    key=uuid4().hex
    def saved():
        with f[1].connect() as c:
            row=c.execute('SELECT opportunities,service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        return row
    before=saved();original=package._view;calls=[]
    def final_unknown(*args,**kwargs):
        result,basis=original(*args,**kwargs);calls.append(result['state'])
        if len(calls)==2:
            result=deepcopy(result);result.update(state='UNKNOWN',can_resolve=False,action_requests={},unknown_scope='THIS_CASE',
                affected=[s['id'] for s in args[3]['service_case_plan']['steps']],preserved=[],blocking_reasons=['SYNTHETIC_FINAL_AVAILABILITY_UNKNOWN'])
            result['package_confirmation'].update(can_keep_and_continue=False,can_merge=False)
        return result,basis
    with monkeypatch.context() as patch:
        patch.setattr(package,'_view',final_unknown)
        response=f[3].post(base+'/commands',headers=headers(f[2],key=key),json=body)
    after=saved();cold=f[3].get(base+'/recovery/'+key,headers=headers(f[2]))
    observed=dict(scope='WIP actual PG/API + controlled final availability projection seam; not real expiry',
      final_basis_deliberately_unchanged=True,post_status=response.status_code,cold_status=cold.status_code,
      cold_outcome=cold.json().get('status'),plan_and_ledger_unchanged=after==before,view_calls=len(calls),
      expected_post_status=409,expected_cold_outcome='NOT_OBSERVED',expected_no_plan_or_ledger_write=True)
    (Path(__file__).parent/'result.json').write_text(json.dumps(observed,indent=2)+'\n')
    assert response.status_code==409,observed
    assert after==before and cold.status_code==200 and cold.json()['status']=='NOT_OBSERVED',observed
