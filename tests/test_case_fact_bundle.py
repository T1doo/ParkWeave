"""Real PostgreSQL/API: provenance and manual locks drive original Case fact gate."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from uuid import uuid4,UUID
import json,hashlib
import pytest,psycopg
from psycopg.types.json import Jsonb
from parkweave import case_fact_bundle as bundle,case_fact_clarifications as facts
from parkweave.store import Store,Conflict
from test_executor_receipts import receipt_fixture
from test_case_resources import link_fixture
from test_preparation import preparation_fixture,filled,add,headers,command as prep_command,read as prep_read
from test_case_fact_clarifications_integration import post_fact,declare,fact_read,business,authority,assertions

def get(f,p,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/fact-bundle',headers=headers(f[2],user))
def recover(f,p,key,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/fact-bundle/recovery/'+key,headers=headers(f[2],user))
def command(f,p,data,key=None,user='fixture-a'):return f[3].post('/api/preparations/'+p['preparation_id']+'/fact-bundle/commands',headers=headers(f[2],user,key or uuid4().hex),json=data)
def body(v,action='REGISTER_DOCUMENT',**extra):return dict(action=action,expected_preparation_revision=v['preparation_revision'],expected_bundle_revision=v['revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC PRIVATE_BUNDLE_REASON explicit action',**extra)
def period():
 now=datetime.now(timezone.utc);return dict(valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=2)).isoformat(),timezone='UTC')
def setup(f):
 p=filled(f);p=add(f,p,'material_outline','SYNTHETIC 地区甲 / 17 / 办理需求').json()
 d=declare(f,p);assert d.status_code==200,d.text;p=d.json()
 for field,value in [('region','地区乙'),('employees',8),('service_need','其它自述')]:post_fact(f,field,value,'SYNTHETIC original '+field)
 return p

def document(f,p,field='region'):
 data=prep_read(f,p).json();m=next(x for x in data['current_materials'] if x['slot']=='material_outline');quote={'region':'地区甲','employees':'17','service_need':'办理需求'}[field];start=m['text'].index(quote)
 return dict(field=field,value=int(quote) if field=='employees' else quote,unit='people' if field=='employees' else 'text',validity=period(),material_id=m['id'],material_version=m['version'],material_sha256=m['source_sha256'],start=start,end=start+len(quote))
def register(f,p,field='region'):
 r=command(f,p,body(get(f,p).json(),source=document(f,p,field)));assert r.status_code==200,r.text;return r.json()['current'],r.json()['receipt']['payload']['entry']
def choose(f,p,selected=None):
 v=fact_read(f,p).json();selected=selected or {x['field_name']:x['id'] for x in v['sources'] if x['source_kind']=='USER_ASSERTED_SYNTHETIC'};by={x['id']:x for x in v['sources']}
 b=dict(expected_preparation_revision=v['preparation_revision'],expected_clarification_revision=v['revision'],expected_source_sha256=v['source_sha256'],choices=[dict(field=field,assertion_id=selected[field],expected_assertion_revision=by[selected[field]]['revision'],expected_assertion_fingerprint=by[selected[field]]['fingerprint']) for field in facts.FIELDS],reason='SYNTHETIC choose explicit real source identities')
 return f[3].post('/api/preparations/'+p['preparation_id']+'/fact-clarifications/confirm',headers=headers(f[2],key=uuid4().hex),json=b)
def snapshot(f):
 with f[1].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in ('preparations','preparation_events','preparation_evidence','fact_assertions','cases','principals','capability_grants','field_grants','action_grants','preparation_grants','run_assignments')}

def test_documents_are_actual_selectable_case_sources_and_original_review_gate(preparation_fixture):
 f=preparation_fixture;p=setup(f);old_assertions=assertions(f);old_auth=authority(f);old_business=business(f);selected={}
 for field in facts.FIELDS:v,e=register(f,p,field);selected[field]=e['id']
 r=choose(f,p,selected);assert r.status_code==200,r.text;p=r.json();assert fact_read(f,p).json()['state']=='CURRENT'
 p=prep_command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC original assigned review').json();p=prep_command(f,p,'CONFIRM',reason='SYNTHETIC original owner confirm').json();assert p['state']=='LOCAL_CONFIRMED'
 assert assertions(f)==old_assertions and authority(f)==old_auth
 v=get(f,p).json();assert len(v['entries'])==3 and all(x['eligible_for_case_selection'] for x in v['entries']);assert v['share_scope']=='OWNER_CASE_USE_ONLY' and not v['business_publication'] and not v['case_goal_completed']
 with f[1].connect() as c:assert c.execute('SELECT state FROM cases WHERE id=%s',(UUID(p['case_id']),)).fetchone()['state']!='FULFILLED'
 assert business(f)==old_business
 cold=Store(f[0].dsn);assert bundle.read(cold,f[2]['fixture-a'],UUID(p['preparation_id']))['history']==v['history']

def test_assumptions_stay_unknown_and_never_enter_original_choice(preparation_fixture):
 f=preparation_fixture;p=setup(f);source=dict(field='employees',value=999,unit='people',validity=period(),note='SYNTHETIC PRIVATE_ASSUMPTION unsupported proposal');r=command(f,p,body(get(f,p).json(),'REGISTER_ASSUMPTION',source=source));assert r.status_code==200;v=r.json()['current'];e=v['entries'][0];assert e['kind']=='ASSUMPTION_SYNTHETIC' and e['state']=='UNKNOWN' and not e['eligible_for_case_selection'];assert e['id'] not in {x['id'] for x in fact_read(f,p).json()['sources']}
 q=choose(f,p);assert q.status_code==200;before=snapshot(f);v=fact_read(f,p).json();sources=v['sources'];b=dict(expected_preparation_revision=v['preparation_revision'],expected_clarification_revision=v['revision'],expected_source_sha256=v['source_sha256'],choices=[dict(field=x['field_name'],assertion_id=e['id'] if x['field_name']=='employees' else x['id'],expected_assertion_revision=1,expected_assertion_fingerprint=e['fingerprint'] if x['field_name']=='employees' else x['fingerprint']) for x in sources],reason='SYNTHETIC try assumption selection');r=f[3].post('/api/preparations/'+p['preparation_id']+'/fact-clarifications/confirm',headers=headers(f[2],key=uuid4().hex),json=b);assert r.status_code==409 and snapshot(f)==before
 r=command(f,p,body(get(f,p).json(),'WITHDRAW',source_id=e['id']));assert r.status_code==200 and r.json()['current']['entries'][0]['active'] is False and len(r.json()['current']['history'])==2

def test_manual_lock_refuses_different_source_and_withdraw_until_explicit_unlock(preparation_fixture):
 f=preparation_fixture;p=setup(f);v,e=register(f,p);x=fact_read(f,p).json();selected={s['field_name']:s['id'] for s in x['sources'] if s['source_kind']=='USER_ASSERTED_SYNTHETIC'};selected['region']=e['id'];r=choose(f,p,selected);assert r.status_code==200
 source=next(s for s in fact_read(f,p).json()['sources'] if s['id']==e['id']);r=command(f,p,body(get(f,p).json(),'LOCK',field='region',assertion_id=e['id'],assertion_revision=1,assertion_fingerprint=source['fingerprint']));assert r.status_code==200,r.text;lock=deepcopy(r.json()['current']['locks']['region']);before=snapshot(f)
 r=choose(f,p);assert r.status_code==409 and 'LOCK_CONFLICT' in r.text and snapshot(f)==before
 r=command(f,p,body(get(f,p).json(),'WITHDRAW',source_id=e['id']));assert r.status_code==409 and snapshot(f)==before
 r=choose(f,p,selected);assert r.status_code==200,r.text;assert get(f,p).json()['locks']['region']==lock
 r=command(f,p,body(get(f,p).json(),'UNLOCK',field='region'));assert r.status_code==200;assert choose(f,p).status_code==200
 r=command(f,p,body(get(f,p).json(),'WITHDRAW',source_id=e['id']));assert r.status_code==200 and r.json()['current']['entries'][0]['state']=='WITHDRAWN'

@pytest.mark.parametrize('change',['version','actual-text','expired','withdraw'])
def test_historical_document_not_selected_when_source_changes(preparation_fixture,change):
 f=preparation_fixture;p=setup(f);v,e=register(f,p);selected={s['field_name']:s['id'] for s in fact_read(f,p).json()['sources'] if s['source_kind']=='USER_ASSERTED_SYNTHETIC'};selected['region']=e['id'];assert choose(f,p,selected).status_code==200
 if change=='version':add(f,prep_read(f,p).json()['preparation']|dict(preparation_id=p['preparation_id']),'material_outline','SYNTHETIC 新地区 / 17 / 新需求')
 elif change=='actual-text':
  with f[1].connect() as c:c.execute('UPDATE preparation_evidence SET text=text||%s WHERE id=%s',('SYNTHETIC corrupted bytes',UUID(e['material']['id'])))
 elif change=='expired':
  with f[1].connect() as c:
   value=c.execute('SELECT fact_bundle FROM preparations WHERE id=%s',(UUID(p['preparation_id']),)).fetchone()['fact_bundle'];x=value['events'][0]['payload']['entry'];x['source']['validity']['valid_until']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();x['fingerprint']=bundle.sha({k:v for k,v in x.items() if k!='fingerprint'});value['events'][0]['sha256']=bundle.sha({k:v for k,v in value['events'][0].items() if k!='sha256'});c.execute('UPDATE preparations SET fact_bundle=%s WHERE id=%s',(Jsonb(value),UUID(p['preparation_id'])))
 else:assert command(f,p,body(get(f,p).json(),'WITHDRAW',source_id=e['id'])).status_code==200
 before=snapshot(f);v=get(f,p).json();assert not v['entries'][0]['eligible_for_case_selection'];assert fact_read(f,p).json()['state']=='STALE';assert choose(f,p,selected).status_code==409 and snapshot(f)==before
 assert choose(f,p).status_code==200

@pytest.mark.parametrize('bad',['value','hash','id','span','kind','bool','purpose','scope','huge','note'])
def test_reject_forged_document_and_extra_shapes_without_effect(preparation_fixture,bad):
 f=preparation_fixture;p=setup(f);s=document(f,p);b=body(get(f,p).json(),source=s)
 if bad=='value':s['value']='PRIVATE forged different region'
 elif bad=='hash':s['material_sha256']='0'*64
 elif bad=='id':s['material_id']=str(uuid4())
 elif bad=='span':s['end']=4000
 elif bad=='kind':b['action']='PROMOTE_ASSUMPTION'
 elif bad=='bool':b['expected_bundle_revision']=False
 elif bad=='purpose':b['purpose']='MARKETING'
 elif bad=='scope':b['owner_id']='fixture-b'
 elif bad=='huge':s['value']='X'*2001
 else:s['note']='SYNTHETIC private extra document annotation'
 before=snapshot(f);r=command(f,p,b);assert r.status_code in (409,422) and snapshot(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_owner_only_scope_denies_read_write_recovery_and_generic_redacts(preparation_fixture,user):
 f=preparation_fixture;p=setup(f);v,e=register(f,p);before=snapshot(f);key=v['history'][0]['request_key']
 assert get(f,p,user).status_code==403 and recover(f,p,key,user).status_code==403 and command(f,p,body(v,'WITHDRAW',source_id=e['id']),user=user).status_code==403 and snapshot(f)==before
 text=prep_read(f,p,'prep-specialist-fixture-a').text;assert 'PRIVATE_BUNDLE_REASON' not in text and 'fact_bundle' not in prep_read(f,p).json()['preparation']

@pytest.mark.parametrize('which',['READ','WRITE','EXECUTE','PREPARE','ACTIVE'])
def test_revoke_original_authority_blocks_mutation_and_read_privacy(preparation_fixture,which):
 f=preparation_fixture;p=setup(f);v,e=register(f,p)
 with f[1].connect() as c:
  if which in ('READ','WRITE'):c.execute('UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id=%s AND field_name=%s AND capability=%s',('fixture-a','region',which))
  elif which=='EXECUTE':c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
  elif which=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  else:c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
 before=snapshot(f);assert command(f,p,body(v,'WITHDRAW',source_id=e['id'])).status_code==403 and snapshot(f)==before
 if which=='WRITE':assert get(f,p).status_code==200 and not get(f,p).json()['can_write']
 else:assert get(f,p).status_code==403

def test_same_key_recovery_cross_case_and_concurrent_CAS(preparation_fixture):
 f=preparation_fixture;p=setup(f);b=body(get(f,p).json(),source=document(f,p));key=uuid4().hex;before_auth=authority(f)
 with ThreadPoolExecutor(2) as pool:responses=list(pool.map(lambda _:command(f,p,b,key),range(2)))
 assert [r.status_code for r in responses]==[200,200];v=get(f,p).json();assert v['revision']==1 and len(v['entries'])==1;before=snapshot(f);r=recover(f,p,key);assert r.status_code==200 and r.json()['receipt']==v['history'][0] and snapshot(f)==before;assert recover(f,p,uuid4().hex).json()['status']=='NOT_OBSERVED'
 assert command(f,p,b|dict(reason='SYNTHETIC changed body'),key).status_code==409
 p2=setup(f);assert recover(f,p2,key).status_code==409
 b=body(get(f,p).json(),'REGISTER_ASSUMPTION',source=dict(field='region',value='SYNTHETIC proposal',unit='text',validity=period(),note='SYNTHETIC assumption'))
 with ThreadPoolExecutor(2) as pool:r=list(pool.map(lambda _:command(f,p,b),range(2)))
 assert sorted(x.status_code for x in r)==[200,409];assert authority(f)==before_auth

@pytest.mark.parametrize('bad',['binding','version-bool','event','deleted'])
def test_invalid_bundle_proof_fails_closed_and_no_get_writes(preparation_fixture,bad):
 f=preparation_fixture;p=setup(f);v,e=register(f,p)
 with f[1].connect() as c:
  value=c.execute('SELECT fact_bundle FROM preparations WHERE id=%s',(UUID(p['preparation_id']),)).fetchone()['fact_bundle']
  if bad=='binding':value['binding']['owner_id']='fixture-b'
  elif bad=='version-bool':value['version']=True
  elif bad=='event':value['events'][0]['reason']='SYNTHETIC corruption'
  else:value=None
  c.execute('UPDATE preparations SET fact_bundle=%s WHERE id=%s',(Jsonb(value) if value is not None else None,UUID(p['preparation_id'])))
 before=snapshot(f);assert get(f,p).status_code==409;assert fact_read(f,p).status_code==409;assert snapshot(f)==before

def test_post_update_failure_rolls_back_whole_source_parent_plan_event(preparation_fixture,monkeypatch):
 f=preparation_fixture;p=setup(f);b=body(get(f,p).json(),source=document(f,p));before=snapshot(f)
 def fail(*a,**kw):raise RuntimeError('SYNTHETIC after actual SQL source update')
 monkeypatch.setattr(bundle,'view',fail)
 with pytest.raises(RuntimeError):command(f,p,b)
 assert snapshot(f)==before

def test_codepoint_exact_whitespace_excerpt_and_integer_cannot_be_forged(preparation_fixture):
 f=preparation_fixture;p=setup(f);p=add(f,prep_read(f,p).json()['preparation']|dict(preparation_id=p['preparation_id']),'material_outline','SYNTHETIC 😀 地区甲  / 17').json();m=next(x for x in prep_read(f,p).json()['current_materials'] if x['slot']=='material_outline');quote=' 地区甲 ';start=m['text'].index(quote);s=dict(field='region',value=quote,unit='text',validity=period(),material_id=m['id'],material_version=m['version'],material_sha256=m['source_sha256'],start=start,end=start+len(quote));r=command(f,p,body(get(f,p).json(),source=s));assert r.status_code==200,r.text;assert r.json()['current']['entries'][0]['source']['value']==quote
 start=m['text'].index('17');s=dict(field='employees',value=99,unit='people',validity=period(),material_id=m['id'],material_version=m['version'],material_sha256=m['source_sha256'],start=start,end=start+2);before=snapshot(f);assert command(f,p,body(get(f,p).json(),source=s)).status_code==409 and snapshot(f)==before


def test_bundle_reason_assumption_and_values_not_shared_by_generic_role_views(preparation_fixture):
 f=preparation_fixture;p=setup(f);v,e=register(f,p);r=command(f,p,body(get(f,p).json(),'REGISTER_ASSUMPTION',source=dict(field='region',value='SYNTHETIC PRIVATE_BUNDLE_VALUE',unit='text',validity=period(),note='SYNTHETIC PRIVATE_BUNDLE_NOTE')));assert r.status_code==200
 before=snapshot(f)
 for user in ('fixture-a','prep-specialist-fixture-a'):
  for path in ('/api/preparations/'+p['preparation_id'],'/api/preparations/'+p['preparation_id']+'/readiness','/api/preparation-tasks'):
   x=f[3].get(path,headers=headers(f[2],user));assert x.status_code==200;assert all(mark not in x.text for mark in ('PRIVATE_BUNDLE_REASON','PRIVATE_BUNDLE_VALUE','PRIVATE_BUNDLE_NOTE'))
 assert snapshot(f)==before


def test_timed_source_expiration_during_actual_post_update_wait_rolls_back_lock(preparation_fixture,monkeypatch):
 import time
 from parkweave import controlled_plans as cp
 f=preparation_fixture;p=setup(f);s=document(f,p);s['validity']['valid_until']=(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat();r=command(f,p,body(get(f,p).json(),source=s));assert r.status_code==200;e=r.json()['receipt']['payload']['entry'];selected={x['field_name']:x['id'] for x in fact_read(f,p).json()['sources'] if x['source_kind']=='USER_ASSERTED_SYNTHETIC'};selected['region']=e['id'];assert choose(f,p,selected).status_code==200
 original=cp.invalidate
 def wait(c,id,index):original(c,id,index);time.sleep(1.1)
 monkeypatch.setattr(cp,'invalidate',wait);v=get(f,p).json();before=snapshot(f);key=uuid4().hex;r=command(f,p,body(v,'LOCK',field='region',assertion_id=e['id'],assertion_revision=1,assertion_fingerprint=e['fingerprint']),key);assert r.status_code==409 and snapshot(f)==before;assert recover(f,p,key).json()['status']=='NOT_OBSERVED'


def test_bounds_are_actual_persistent_source_and_event_caps(preparation_fixture):
 f=preparation_fixture;p=setup(f)
 for i in range(12):
  source=dict(field='region',value='SYNTHETIC unknown '+str(i),unit='text',validity=period(),note='SYNTHETIC own bounded assumption');assert command(f,p,body(get(f,p).json(),'REGISTER_ASSUMPTION',source=source)).status_code==200
 v=get(f,p).json();before=snapshot(f);assert command(f,p,body(v,'REGISTER_ASSUMPTION',source=source)).status_code==409 and snapshot(f)==before
 for e in v['entries']:assert command(f,p,body(get(f,p).json(),'WITHDRAW',source_id=e['id'])).status_code==200
 for _ in range(4):
  assert choose(f,p).status_code==200;v=get(f,p).json();s=next(x for x in v['selected_sources'] if x['field']=='region');assert command(f,p,body(v,'LOCK',field='region',assertion_id=s['assertion_id'],assertion_revision=s['expected_assertion_revision'],assertion_fingerprint=s['expected_assertion_fingerprint'])).status_code==200;assert command(f,p,body(get(f,p).json(),'UNLOCK',field='region')).status_code==200
 v=get(f,p).json();assert v['revision']==32 and len(v['entries'])==12 and not v['can_write'];before=snapshot(f);assert command(f,p,body(v,'REGISTER_ASSUMPTION',source=source)).status_code==409 and snapshot(f)==before


def test_migration028_actual_receipt_idempotence_future_rejection_no_grants(preparation_fixture):
 from pathlib import Path
 f=preparation_fixture;p=setup(f);register(f,p);before=snapshot(f);f[1].migrate();Store(f[1].dsn).migrate();assert snapshot(f)==before
 sql=Path('src/parkweave/migration-028.sql').read_text()
 with pytest.raises(psycopg.errors.RaiseException,match='creation ticket required'):
  with f[1].connect() as c:c.execute(sql)
 with f[1].connect() as c:f[1]._case_fact_fixture_receipt.authorize_migration(c);c.execute(sql)
 assert snapshot(f)==before
 with f[1].connect() as c:c.execute('INSERT INTO schema_version VALUES(29)')
 with pytest.raises(Conflict,match='newer than this code'):f[1].migrate()


def test_duplicate_document_new_key_wrong_case_and_unknown_read_only(preparation_fixture):
 f=preparation_fixture;p=setup(f);b=body(get(f,p).json(),source=document(f,p));key=uuid4().hex;assert command(f,p,b,key).status_code==200;before=snapshot(f);assert command(f,p,body(get(f,p).json(),source=b['source'])).status_code==409 and snapshot(f)==before
 p2=setup(f);foreign=document(f,p);b=body(get(f,p2).json(),source=foreign);before=snapshot(f);assert command(f,p2,b).status_code==409;assert recover(f,p2,key).status_code==409;assert recover(f,p,uuid4().hex).json()['status']=='NOT_OBSERVED';assert snapshot(f)==before


def test_document_bundle_drives_actual_p1_invalidation_and_explicit_reconfirmation(link_fixture):
 from test_case_fact_clarifications_integration import current_parent,human_review_and_confirm,assert_resource_p1_uses_current_fact_descriptor,normalize_preparation_observations
 from test_service_case_steps import adopt,verified,read as plan_read,command as plan_command
 from test_request_intents import save
 from test_service_case_steps import GOALS
 f=link_fixture;p=setup(f);assert save(f,current_parent(f,p),goals=[GOALS[0]]).status_code==200;selected={}
 for field in facts.FIELDS:v,e=register(f,p,field);selected[field]=e['id']
 assert choose(f,p,selected).status_code==200;p=human_review_and_confirm(f,current_parent(f,p));assert adopt(f,p).status_code==201;old_plan=verified(f,p,'P1');old_ids=[x['id'] for x in old_plan['steps']];old_history=deepcopy(fact_read(f,p).json()['history']);old_business=business(f);old_authority=authority(f)
 assert assert_resource_p1_uses_current_fact_descriptor(f,p)['checkpoints']['P1']['current_snapshot']['fact_clarification']['satisfied']
 source=dict(field='employees',value=999,unit='people',validity=period(),note='SYNTHETIC unknown must not auto-select');r=command(f,p,body(get(f,p).json(),'REGISTER_ASSUMPTION',source=source));assert r.status_code==200
 assert fact_read(f,p).json()['state']=='STALE';assert fact_read(f,p).json()['history']==old_history;assert 'CURRENT_FACT_PURPOSE_CONFIRMATION_REQUIRED' in assert_resource_p1_uses_current_fact_descriptor(f,p)['checkpoints']['P1']['issues']
 before=snapshot(f);assert plan_command(f,p,'P1').status_code==409;assert prep_command(f,current_parent(f,p),'CONFIRM',reason='SYNTHETIC cannot inherit old review').status_code==409;assert normalize_preparation_observations(before,snapshot(f))==before and business(f)==old_business
 assert choose(f,p,selected).status_code==200;p=current_parent(f,p);assert prep_command(f,p,'CONFIRM',reason='SYNTHETIC still requires original specialist').status_code==409;p=human_review_and_confirm(f,p);new_plan=verified(f,p,'P1');assert [x['id'] for x in new_plan['steps']]==old_ids;assert fact_read(f,p).json()['history'][:-1]==old_history;assert authority(f)==old_authority and business(f)==old_business


def test_request_revision_change_rebinds_current_basis_retains_original_receipt(preparation_fixture):
 from test_request_intents import save
 from test_case_fact_clarifications_integration import current_parent
 f=preparation_fixture;p=setup(f);v,e=register(f,p);old_receipt=deepcopy(v['history'][0]);assert old_receipt['source_basis']['request_revision']==0;assert old_receipt['source_sha256']==bundle.sha(old_receipt['source_basis']);selected={x['field_name']:x['id'] for x in fact_read(f,p).json()['sources'] if x['source_kind']=='USER_ASSERTED_SYNTHETIC'};selected['region']=e['id'];assert choose(f,p,selected).status_code==200
 r=save(f,current_parent(f,p),text='SYNTHETIC changed explicit original request');assert r.status_code==200;v=get(f,p).json();assert v['current_basis']['request_revision']==r.json()['revision'] and v['current_basis']['request_sha256']!=old_receipt['source_basis']['request_sha256'];assert v['history']==[old_receipt] and v['entries'][0]['eligible_for_case_selection'];assert fact_read(f,p).json()['state']=='STALE';before=snapshot(f);recovered=recover(f,p,old_receipt['request_key']).json();assert recovered['receipt']==old_receipt and recovered['current']['current_basis']==v['current_basis'] and snapshot(f)==before;assert choose(f,p,selected).status_code==200


def test_case_only_document_selection_cannot_be_copied_by_original_assertion_brief(preparation_fixture):
 from test_material_preparation_drafts import preview,save as save_brief,body as brief_body
 f=preparation_fixture;p=setup(f);v,e=register(f,p);selected={x['field_name']:x['id'] for x in fact_read(f,p).json()['sources'] if x['source_kind']=='USER_ASSERTED_SYNTHETIC'};selected['region']=e['id'];assert choose(f,p,selected).status_code==200;before=snapshot(f);x=preview(f,p).json();assert x['state']=='BLOCKED' and not x['can_save'] and x['draft'] is None and 'OWNER_CASE_ONLY_SOURCE_NOT_SHARED_BY_BRIEF_RECIPE' in x['issues'];assert '地区甲' not in json.dumps(x,ensure_ascii=False)
 b=dict(expected_preparation_revision=x['preparation_revision'],expected_source_sha256='0'*64,expected_reviewer_id=x['reviewer_id'],confirm_material_share=True);assert save_brief(f,p,b).status_code==409 and snapshot(f)==before
 assert choose(f,p).status_code==200;x=preview(f,p).json();assert x['state']=='DRAFT' and x['can_save'];assert '地区甲' not in x['draft']['text'] and '地区乙' in x['draft']['text'];assert save_brief(f,p,brief_body(x)).status_code==201
