from conftest import fixture,pg
from test_template_consumer import template_consumption,headers,body
from test_template_consumer_planning import ready
from template_candidate_support import grant_snapshot
from datetime import datetime,timedelta,timezone

def test_original_template_case_fact_bundle_declare_select_confirm_without_new_run_grant(template_consumption):
 f=template_consumption;data=body(f);data['materials'][1]['text']='地区甲 / 17 / 本次服务诉求';row=ready(f,data);p=row['preparation']['preparation'];pid=row['preparation_id'];path='/api/preparations/'+pid
 old_auth=grant_snapshot(f['owner'])
 with f['owner'].connect() as c:old_runs=c.execute('SELECT id FROM runs ORDER BY id').fetchall()
 r=f['client'].post(path+'/fact-clarifications/declare',headers=headers(f,key='ind-purpose'),json=dict(expected_preparation_revision=p['revision'],expected_clarification_revision=0,profile='LOCAL_SERVICE_PREPARATION_FACTS_V1',purpose='SERVICE_PREPARATION',reason='SYNTHETIC original same Case purpose'));assert r.status_code==200,r.text
 period=dict(valid_from=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),valid_until=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),timezone='UTC');chosen={}
 for field,value in [('region','地区甲'),('employees',17),('service_need','本次服务诉求')]:
  v=f['client'].get(path+'/fact-bundle',headers=headers(f)).json();m=next(x for x in v['documents'] if x['slot']=='material_outline');quote=str(value);start=m['text'].index(quote)
  source=dict(field=field,value=value,unit='people' if field=='employees' else 'text',validity=period,material_id=m['id'],material_version=m['version'],material_sha256=m['source_sha256'],start=start,end=start+len(quote))
  r=f['client'].post(path+'/fact-bundle/commands',headers=headers(f,key='ind-source-'+field),json=dict(action='REGISTER_DOCUMENT',expected_preparation_revision=v['preparation_revision'],expected_bundle_revision=v['revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC current explicit original document',source=source));assert r.status_code==200,r.text;chosen[field]=r.json()['receipt']['payload']['entry']['id']
 v=f['client'].get(path+'/fact-clarifications',headers=headers(f)).json();by={x['id']:x for x in v['sources']}
 r=f['client'].post(path+'/fact-clarifications/confirm',headers=headers(f,key='ind-select'),json=dict(expected_preparation_revision=v['preparation_revision'],expected_clarification_revision=v['revision'],expected_source_sha256=v['source_sha256'],choices=[dict(field=field,assertion_id=chosen[field],expected_assertion_revision=by[chosen[field]]['revision'],expected_assertion_fingerprint=by[chosen[field]]['fingerprint']) for field in chosen],reason='SYNTHETIC explicit owner chooses original same Case sources'));assert r.status_code==200,r.text
 v=f['client'].get(path+'/fact-clarifications',headers=headers(f)).json();assert v['state']=='CURRENT';assert v['case_id']==row['case_id'];assert grant_snapshot(f['owner'])==old_auth
 with f['owner'].connect() as c:assert c.execute('SELECT id FROM runs ORDER BY id').fetchall()==old_runs
