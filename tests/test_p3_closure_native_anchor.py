"""Owned SQL faults exercise independent DB guards, not API authorization."""
pytest_plugins=['p3_closure_fixture_support']
from copy import deepcopy
from uuid import uuid4
import pytest,psycopg
from psycopg.types.json import Jsonb
from p3_closure_fixture_support import closure_case
from parkweave import controlled_plans as cp


def append_native(t,mode):
 f,p=t['f'],t['p'];protocol=t['protocol']
 with f[1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],)).fetchone()
  snapshot=protocol._snapshot(c,parent);birth,mark=protocol.frontier.birth(c,parent)
  if mode=='offered':
   q=dict(birth=birth,epoch=mark['epoch'],ever_started=True,profile='P3_NEVER_ACCEPTED_CLOSED_V1',state='CLOSED_WITHOUT_ACCEPTANCE')
  else:q=protocol.qualify(c,parent,t['old'])
  if mode=='snapshot':snapshot['service_dispatches'][0]['revision']=62
  saved=dict(schema=1,generation=birth['generation'],preparation_id=p['preparation_id'],previous_plan_id=t['old']['id'],replacement_plan_id=parent['service_case_plan']['id'],plan_revision=parent['service_case_plan']['revision'],request_key=uuid4().hex,fingerprint='0'*64,combination_id=str(uuid4()),link_revision=2,approval_id=str(uuid4()),qualification=q,qualification_sha256=cp._hash(q),snapshot=snapshot)
  c.execute('UPDATE preparations SET candidate_p3_closure_consumptions=candidate_p3_closure_consumptions||%s WHERE id=%s',(Jsonb([saved]),p['preparation_id']))


@pytest.mark.parametrize('closure_case,mode,reason',[
 ({'stop_after':'closed'},'orphan','actual approved delivery'),
 ({'stop_after':'closed'},'snapshot','collection changed'),
 ({'stop_after':'offered'},'offered','bounded original closed dispatch'),
],indirect=['closure_case'])
def test_closure_native_guard_rejects_orphan_fabricated_snapshot_and_actual_offered(closure_case,mode,reason):
 t=closure_case;f,p=t['f'],t['p']
 with f[1].connect() as c:before=deepcopy(c.execute('SELECT candidate_business_frontier,candidate_p3_closure_consumptions FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone())
 with pytest.raises(psycopg.errors.RaiseException,match=reason):append_native(t,mode)
 with f[1].connect() as c:after=c.execute('SELECT candidate_business_frontier,candidate_p3_closure_consumptions FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
 assert after==before
