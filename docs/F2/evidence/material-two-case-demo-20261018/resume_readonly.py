from pathlib import Path
import json,traceback
base=Path('.runtime/material-two-case-demo-20261018/run_material_http.py').read_text().split('def main():',1)[0]
base=base.replace("SOURCE='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765'", "SOURCE='24f6db12490b7ba7f01099d311af97e926eeddd0'")
exec(compile(base,'original-http-helper-definitions','exec'))
def canonical(v):return json.dumps(v,sort_keys=True,default=str)
def resume():
 expected=json.loads((D/'before-restart-business-snapshot.json').read_text())
 with running('final-restart') as (client,ready):
  before=snapshot();assert canonical(before)==canonical(expected)
  page=client.get('/');assert page.status_code==200 and page.content==(R/'src/parkweave/web.html').read_bytes()
  traffic.append(dict(method='GET',path='/',status=200,original_source_bytes=True))
  for label in ['A','B']:
   original=json.loads((D/('readiness-'+label+'.json')).read_text());id=original['preparation_id']
   view=request(client,'enterprise','GET','/api/preparations/'+id)
   reviewer=request(client,'specialist','GET','/api/preparations/'+id)
   assert view['preparation']['state']==reviewer['preparation']['state']=='LOCAL_CONFIRMED'
   assert view['preparation']['revision']==original['preparation_revision']
   assert view['preparation']['case_id']==original['case_id']
   current=request(client,'enterprise','GET','/api/preparations/'+id+'/readiness');assert current==original
   items={x['slot']:x for x in original['sources']['materials']}
   case=dict(label=label,run_id=view['preparation']['run_id'],case_id=original['case_id'],preparation_id=id,
             revision=original['preparation_revision'],need=items['need_summary']['text'],outline=items['material_outline']['text'])
   assert view['current_materials']==original['sources']['materials']
   cases.append(case)
   raw=export(client,case,label+'-restart');assert raw==(P/'downloads'/('material-'+label+'.txt')).read_bytes()
  after=snapshot();assert canonical(after)==canonical(before)
  emit('final-restart-business-snapshot.json',after)
 assert all(x['method']=='GET' for x in traffic)
 first=json.loads((D/'first-start-settlement.json').read_text())
 failed=json.loads((D/'restart-settlement.json').read_text())
 initial=json.loads((D/'initial-business-snapshot.json').read_text())
 partial=json.loads((D/'http-partial-failure.json').read_text())
 assert first['launcher_exit']==0 and failed['launcher_exit']==1 and partial['cases_created']==2
 assert sum(x['status']==403 for x in partial['traffic'])==4
 result=dict(setup_source_commit=marker['setup_source_commit'],material_write_tested_source_commit='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765',restart_tested_source_commit=SOURCE,
    first_window_overall_exit=1,first_window_scope='Two case/material/review/confirmation flows plus two NodeVM exports completed; subsequent restart precheck refused',
    scenario_count=2,both_actual_http_case_material_review_confirmation=True,negative_role_requests_403=4,
    final_readonly_restart_pass=True,final_restart_contains_business_posts=False,unchanged_ids_materials_review_and_exports=True,
    real_browser='REFUSED_ONCE_NO_RETRY',browser_download='NOT_RUN_SANDBOX_REFUSED',original_js_node_vm_text_exports=4,
    local_synthetic_demo_profile=False,initial_business_counts=initial['counts'],final_business_counts=after['counts'],
    authority_counts=after['authority']['counts'],authority_unchanged=initial['authority']==after['authority'],
    setup_count=1,session_generation_count=1,private_state_retained=True,session_expiry='NONE_MANUAL_REVOCATION_REQUIRED',
    real_model_calls=0,windows_formal_at='NOT_RUN',real_business='NOT_RUN',cases=cases,
    settlements=[first,failed,*settlements],final_restart_traffic=traffic,
    exports=[json.loads((D/('export-'+label+'.json')).read_text()) for label in ['A','B','A-restart','B-restart']])
 emit('final-material-validation.json',result)
 print(json.dumps({k:v for k,v in result.items() if k not in ['cases','settlements','final_restart_traffic','exports']},indent=2))
try:resume()
except BaseException as error:
 (P/'logs/readonly-resume-failure.log').open('a').write(traceback.format_exc())
 emit('resume-partial-failure.json',dict(error_type=type(error).__name__,traffic=traffic,settlements=settlements))
 print('READONLY_RESUME_FAILED: '+type(error).__name__+'; private trace retained')
 raise SystemExit(1)
