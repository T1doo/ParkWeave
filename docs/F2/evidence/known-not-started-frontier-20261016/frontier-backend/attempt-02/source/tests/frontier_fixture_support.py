"""Fresh birth-tracked fixture only; no old replacement runtime outputs."""
from copy import deepcopy
from pathlib import Path
from uuid import UUID,uuid4
import os,json
import pytest
from parkweave import business_frontier as bf,service_release_preflight as pf,service_capability_catalog as catalogs
from parkweave.template_consumer import ConsumerRepository
from test_preparation import preparation_fixture,headers,command
from test_executor_receipts import receipt_fixture,ready
from test_service_capability_catalog_actual import capability_catalog,capability_resource_catalog
from test_plan_replacement_reapproval import generate,bind_all
from test_new_enterprise_local_chain import ALL_GOALS
from test_request_intents import save
from test_template_upgrade import publication
from test_service_case_steps import verified
from test_resource_bundles import bundle
from test_case_resource_delivery import quoted,submit
from test_plan_source_reapproval import approved
from test_service_plan_approval import enable


@pytest.fixture
def frontier_case(capability_resource_catalog,tmp_path):
 a=capability_resource_catalog;f=a['f']
 out=Path(os.environ.get('FRONTIER_ARTIFACT_ROOT','.runtime/frontier-fixture/artifacts'));out.mkdir(parents=True,exist_ok=True)
 fd=os.open(out/('fixture-'+uuid4().hex+'.private.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream:stream.write(json.dumps(sorted(f[2].values()))+'\n')
 protocol=bf.KnownNotStartedFrontier(f[1],f[1]._case_fact_fixture_receipt,enabled_for_isolated_tests=True)
 protocol.attach_store(f[0]);oldpairs=bind_all(a)
 p=ready(f);r=save(f,p,goals=ALL_GOALS);assert r.status_code==200,r.text;p={**p,'revision':r.json()['revision']}
 for action,actor in (('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')):
  r=command(f,p,action,actor,reason='SYNTHETIC original frontier material '+action);assert r.status_code==200,r.text;p=r.json()
 generate(a,p);verified(f,p,'P1')
 checker=pf.ServiceReleasePreflight(a['catalog'],ConsumerRepository(tmp_path/'frontier-preflight.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
 bridge=enable(f,p,enabled_for_source_reapproval_tests=True,enabled_for_plan_replacement_tests=True,plan_replacement_preflight=checker,
  enabled_for_known_not_started_tests=True,known_not_started_frontier=protocol)
 holds,b=bundle(f);d=quoted(f,p,b);item,_=approved(f,p,d)
 response=submit(f,p,{**d,'approval_id':item['id']});assert response.status_code==201,response.text;oldreceipt=response.json()
 verified(f,p,'P2')
 with f[1].connect() as c:old=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'])
 a['published']=publication(a,goals=a['published']['snapshot']['definition']['required_goals'],source='1',name='SYNTHETIC explicit known-not-started compatible replacement')
 newpairs=bind_all(a,2)
 for release,_ in oldpairs:
  with a['catalog'].connection() as c:revision=catalogs.proof(catalogs.row(c,'park-a'))['revision']
  a['catalog'].withdraw_release('park-a',uuid4().hex,release['release_id'],revision,'SYNTHETIC original superseded release retirement')
 old_preflights=[checker.preview(f[2]['fixture-a'],UUID(p['preparation_id']),original_release_id=r['release_id'],original_instance_id=i['instance_id'],target_instance_id=ni['instance_id']) for (r,i),(_,ni) in zip(oldpairs,newpairs)]
 assert all(q['classification']=='UNKNOWN' for q in old_preflights)
 for action,actor in (('REOPEN','fixture-a'),('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')):
  r=command(f,p,action,actor,reason='SYNTHETIC fresh frontier catalog review '+action);assert r.status_code==200,r.text;p=r.json()
 old_dispatch_reply=f[3].get('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],'prep-specialist-fixture-a'))
 assert old_dispatch_reply.status_code==200,old_dispatch_reply.text
 old_dispatch_view=old_dispatch_reply.json();old_offer_fence=deepcopy(old_dispatch_view['business_frontier'])
 old_offer_body=dict(expected_preparation_revision=p['revision'],expected_dispatch_revision=0,executor_id='executor-a',reason='SYNTHETIC captured before full replacement',expected_business_frontier=old_offer_fence)
 new=generate(a,p,old['revision']);verified(f,p,'P1')
 with f[1].connect() as c:new=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'])
 return dict(f=f,p=p,a=a,old=old,new=new,oldreceipt=oldreceipt,old_holds=holds,checker=checker,bridge=bridge,protocol=protocol,
  oldpairs=oldpairs,newpairs=newpairs,old_preflights=old_preflights,old_offer_fence=old_offer_fence,old_offer_body=old_offer_body,old_dispatch_view=old_dispatch_view,out=out)
