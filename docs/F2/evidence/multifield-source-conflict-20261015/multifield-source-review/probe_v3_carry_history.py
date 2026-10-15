"""Supplemental actual v3-note/compatible-carry composition, original five goals.

This is not the new six-goal acceptance path and performs only isolated fixture
publication/forward carries already supported by the original test helpers.
"""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json
import os

from test_note_template_carry import ready, request, apply
from test_template_upgrade import upgrade_case, publication, GOALS
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from test_plan_source_conflicts import edit
from test_case_opportunities import imported


def test_v3_note_original_receipt_survives_compatible_carry_edit_reconfirm_and_next_hop(upgrade_case):
    u=upgrade_case;f=u['f'];row,p,target=ready(u)
    _,x,_=imported(f,p);card=x['cards'][0]
    base='/api/preparations/'+p['preparation_id']+'/plan-material-package'
    def acknowledge():
        view=f[3].get(base,params={'card_id':card['id']},headers=headers(f[2]));assert view.status_code==200,view.text
        view=view.json();body=deepcopy(view['action_requests']['KEEP_AND_CONTINUE'])
        body['reason']='SYNTHETIC explicit package acknowledgement between compatible carries'
        key=uuid4().hex
        posted=f[3].post(base+'/commands',headers=headers(f[2],key=key),json=body)
        assert posted.status_code==200,posted.text
        assert posted.json()['current']['note']['text']==view['note']['text']
        return key,posted.json()['receipt']
    original_key,original_receipt=acknowledge()
    _,body=request(u,row,target);first=apply(u,row,body);assert first.status_code==200,first.text
    first_cold=f[3].get(base+'/recovery/'+original_key,headers=headers(f[2]))
    assert first_cold.status_code==200 and first_cold.json()['receipt']==original_receipt
    changed=edit(f,p,'SYNTHETIC later exact manual note after first compatible carry')
    assert changed['current']['note']['event_id']!=original_receipt['id']
    _,second_receipt=acknowledge()
    target2=publication(u,GOALS,'1','SYNTHETIC next compatible carry after v3 explicit reconfirmation')
    _,body2=request(u,row,target2);second=apply(u,row,body2);assert second.status_code==200,second.text
    final=f[3].get(base+'/recovery/'+original_key,headers=headers(f[2]));assert final.status_code==200,final.text
    assert final.json()['status']=='COMMITTED' and final.json()['receipt']==original_receipt
    assert any(e==second_receipt for e in final.json()['current']['history'])
    output=Path(os.environ.get('MULTIFIELD_REVIEW_PROBE_OUT',Path(__file__).parent));output.mkdir(parents=True,exist_ok=True)
    (output/'v3-carry-history-result.json').write_text(json.dumps(dict(status='PASS',
       scope='original five-goal owned fixture/API supplemental composition, not six-goal main acceptance',
       original_v3_event_exact_after_two_compatible_carries=True,legal_manual_edit_followed_by_fresh_v3_confirmation=True,
       actual_API_PG=True,formal_publication_or_general_migration=False),indent=2)+'\n')
