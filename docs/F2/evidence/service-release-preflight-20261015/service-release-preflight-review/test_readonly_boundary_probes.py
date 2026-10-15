"""Independent runtime-only negative seams; run only at parent's exact freeze."""
from copy import deepcopy
from pathlib import Path
import json,subprocess
from uuid import UUID
import pytest
from parkweave import bounded_planning as bp, typed_source_impact as typed
from test_service_release_preflight_independent import chain,selected,preview,plan,originals,ok,headers,plan_command,KINDS
pytest_plugins=['test_service_release_preflight_independent']
OUT=Path('/workspace/ParkWeave/.runtime/service-release-preflight-review')
def receipt(name,value):
 value.update(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),scope='RUNTIME_NEGATIVE_SEAM_ACTUAL_ORIGINAL_HTTP_ASGI_OWNED_PG_NO_BUSINESS_WRITE')
 (OUT/('boundary-'+name+'.json')).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def test_saved_v4_history_does_not_call_current_compiler(preflight_http,monkeypatch):
 r=preflight_http;p=chain(r);before=originals(r);saved=deepcopy(plan(r,p));journal=r['repository'].path.read_bytes()
 def poison(*args,**kwargs):raise AssertionError('CURRENT_COMPILER_MUST_NOT_VALIDATE_SAVED_V4_HISTORY')
 with r['f'][0].connect() as c:
  actor,parent=r['checker']._context(c,r['f'][2]['fixture-c'],UUID(p['preparation_id']))
  with monkeypatch.context() as m:
   m.setattr(bp,'compile',poison)
   historic,record,pairs=r['checker']._originals(parent)
   assert historic==saved and len(pairs)==3 and record['frozen_registry']==saved['binding']['registry']
 assert originals(r)==before and r['repository'].path.read_bytes()==journal
 receipt('saved-history-current-compiler-poison',{'saved_history_valid':True,'current_compiler_called':False,'historical_originals':3,'six_mandatory_goals':len(saved['required_goals']),'business_and_all_original_history_unchanged':True,'private_preflight_journal_unchanged':True,'seam':'Historical validator direct read after actual six-goal original HTTP chain; not a current-target admission test'})
@pytest.mark.parametrize('shape',['boolean_schema','partial_unknown_with_lock'])
def test_future_or_contradictory_graph_is_nonrecordable_and_keeps_locks(preflight_http,monkeypatch,shape):
 r=preflight_http;p=chain(r);f=r['f']
 if shape=='partial_unknown_with_lock':
  current=ok(f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],'fixture-c')))
  step=next(s for s in current['steps'] if s['adapter_id']=='P1')
  ok(plan_command(f,p,'P1','LOCK',row=current,user='fixture-c',expected_source_sha256=step['source_sha256']))
 old=selected(r,p);same=dict(instance=r['a']['configs']['park-b',KINDS[1]],ref=old);saved=deepcopy(plan(r,p));before=originals(r);journal=r['repository'].path.read_bytes();real=typed.build
 def future(*args,**kwargs):
  value=deepcopy(real(*args,**kwargs))
  if shape=='boolean_schema':value['schema']=True
  else:
   subset=[s['id'] for s in saved['steps'] if s['adapter_id'] in ('P4','P5')]
   value.update(unknown_scope='THIS_CASE',affected=subset,preserved=[s['id'] for s in saved['steps'] if s['id'] not in subset])
  return value
 with monkeypatch.context() as m:
  m.setattr(typed,'build',future)
  response=preview(r,p,old,same);assert response.status_code==200,response.text;value=response.json()
 assert value['classification']=='UNKNOWN' and not value['can_record'] and set(value['affected'])=={s['id'] for s in saved['steps']} and value['preserved']==[]
 expected_locks=[s['id'] for s in saved['steps'] if s.get('manual_lock') is not None]
 assert value['locked_affected']==expected_locks and originals(r)==before and r['repository'].path.read_bytes()==journal
 receipt(shape,{'classification':value['classification'],'can_record':value['can_record'],'affected_count':len(value['affected']),'preserved_count':len(value['preserved']),'locked_affected_count':len(value['locked_affected']),'literal_original_uuid_partition_exact':True,'business_and_all_original_history_unchanged':True,'private_preflight_journal_unchanged':True,'target_same_release_control_not_cross_version':True})
