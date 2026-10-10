"""Legal old resource occupancy is neither copied nor altered by preview."""
from pathlib import Path
import json
from conftest import pg,fixture
from test_resource_execution_preview import preparation_fixture,setup,execute,snapshot
from test_isolated_execution_preview import execute as p1_execute
from test_resource_combinations import pair,write
from test_resource_holds import body as formal_body,preview as formal_preview
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-p2-resource-execution-preview-review')
def test_real_original_nonempty_resource_hold_combination_receipts_preserved(preparation_fixture,tmp_path):
 f0=preparation_fixture
 with actual_http(create_app(f0[0])) as (client,requests):
  f=f0[:3]+(client,);p,p1,e=setup(f,tmp_path);assert p1_execute(f,p).status_code==201;old=p1.path.read_bytes();holds,data=pair(f,quantity=1);combo=write(f,data);assert combo.status_code==201
  occupied=formal_preview(f,formal_body(f,quantity=1)).json()['occupied_peak'];assert occupied==1
  before=snapshot(f)
  assert len(before['synthetic_resource_holds'])==2 and len(before['synthetic_resource_receipts'])==2 and len(before['synthetic_resource_combinations'])==1 and len(before['synthetic_resource_combination_receipts'])==1
  r=execute(f,p);assert r.status_code==201;d=r.json()['result'];a=d['artifact'];assert d['state']=='SUCCEEDED'
  assert a['capacity_scope']=='EMPTY_ISOLATED_SPACE_ONLY' and all(x['occupied_peak']==0 for x in a['prechecks']) and len(a['holds'])==2
  assert {x['id'] for x in a['holds']}.isdisjoint({x['id'] for x in holds}) and a['combination']['id']!=combo.json()['combination']['id']
  assert snapshot(f)==before and p1.path.read_bytes()==old
  (PRIVATE_EVIDENCE/'nonempty-formal-preserved-safe.json').write_text(json.dumps(dict(actual_original_http_holds=2,actual_original_combination=1,actual_original_hold_receipts=2,actual_original_combination_receipts=1,formal_occupied_peak=occupied,isolated_occupied_peak=0,capacity_scope='EMPTY_ISOLATED_SPACE_ONLY',private_artifact_new_uuids=True,all_public_rows_and_values_unchanged=True,old_p1_sqlite_bytes_unchanged=True,no_formal_release_or_real_availability_claim=True),indent=2)+'\n')
