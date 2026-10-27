"""Independent bounded protocol probes. No DB, HTTP, DDL or business execution.

Fake connections only expose stored documents to the real historical reader;
these checks do not prove native trigger installation, locking or SQL behavior.
Run against the selected frozen source, never private copied product modules.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import ast
import inspect
import pytest
from parkweave import business_frontier as bf, business_frontier_types as bt
from parkweave import controlled_plans as cp
from parkweave import plan_replacement_compatibility as compatibility
from parkweave import service_dispatches as sd, executor_receipts as er, case_lifecycle as lc
from parkweave.store import Conflict

U=lambda n:str(UUID(int=n))


def qualification():
 context=dict(preparation_id=U(1),case_id=U(2),run_id=U(3),owner_id='owner',park_id='park',org_id='org')
 birth=dict(scope=bf.SCOPE,schema=1,generation=U(4),birth_xid='123',**context)
 q=dict(schema=1,profile='KNOWN_NOT_STARTED_V1',state='KNOWN_NOT_STARTED',previous_plan_id=U(5),
  birth=birth,birth_sha256=cp._hash(birth),protocol_sha256='a'*64,epoch=0,ever_started=False,collection_bound=1,
  collections=[dict(table=t,count=0,complete=True,known=True,sha256=cp._hash([])) for t in bf.TABLES],
  verified_prefix=[dict(adapter_id=a,step_id=U(10+i),event_id=U(20+i),event_revision=i+2,source_sha256='b'*64,event_sha256='c'*64) for i,a in enumerate(('P1','P2'))],
  tail=dict(P3='NEVER_DISPATCHED_OR_ACCEPTED',P4='NO_RECEIPT_EFFECT',P5='NO_LOCAL_LIFECYCLE_EFFECT'),**{k:context[k] for k in ('preparation_id','case_id','run_id')})
 return q,SimpleNamespace(expected_previous_plan_id=UUID(U(5))),context


def test_real_source_imports_are_selected_workspace():
 root=Path(__file__).resolve()
 while not (root/'src/parkweave').is_dir():
  assert root!=root.parent,'repository not found'
  root=root.parent
 for module in (bf,bt,compatibility,sd,er,lc):
  assert Path(module.__file__).resolve().parent==root/'src/parkweave'


def test_exact_positive_qualification_is_accepted():
 q,data,context=qualification();bf.validate_qualification(q,data,context)


@pytest.mark.parametrize('mutation',[
 'unknown','extra','schema_bool','epoch_bool','epoch_nonzero','started','bound_bool',
 'missing_table','reordered_tables','count_bool','unknown_collection','extra_collection',
 'bad_birth','birth_digest','prefix_adapter','prefix_revision_bool','tail_unknown'])
def test_qualification_mutations_refuse(mutation):
 q,data,context=qualification()
 if mutation=='unknown':q['state']='UNKNOWN'
 elif mutation=='extra':q['inferred_authority']=True
 elif mutation=='schema_bool':q['schema']=True
 elif mutation=='epoch_bool':q['epoch']=False
 elif mutation=='epoch_nonzero':q['epoch']=1
 elif mutation=='started':q['ever_started']=True
 elif mutation=='bound_bool':q['collection_bound']=True
 elif mutation=='missing_table':q['collections'].pop()
 elif mutation=='reordered_tables':q['collections'].reverse()
 elif mutation=='count_bool':q['collections'][0]['count']=False
 elif mutation=='unknown_collection':q['collections'][0]['known']=False
 elif mutation=='extra_collection':q['collections'][0]['pagination']='first_page'
 elif mutation=='bad_birth':q['birth']['generation']='UNKNOWN';q['birth_sha256']=cp._hash(q['birth'])
 elif mutation=='birth_digest':q['birth_sha256']='d'*64
 elif mutation=='prefix_adapter':q['verified_prefix'][1]['adapter_id']='P3'
 elif mutation=='prefix_revision_bool':q['verified_prefix'][0]['event_revision']=True
 elif mutation=='tail_unknown':q['tail']['P3']='PENDING'
 with pytest.raises((ValueError,TypeError,KeyError)):
  bf.validate_qualification(q,data,context)


def test_absent_none_fence_preserves_old_request_bytes():
 commands=[sd.Offer(expected_preparation_revision=1,expected_dispatch_revision=0,executor_id='e',reason='r'),
  sd.Command(action='ACCEPT',expected_revision=1,reason='r'),
  er.Create(preparation_id=U(1),expected_preparation_revision=1,executor_id='e'),
  er.Command(action='SUBMIT',expected_revision=1,text='t',source_kind='SYNTHETIC',source_label='s'),
  lc.Command(action='REOPEN',expected_revision=0,expected_cycle=1,reason='r')]
 for command in commands:
  old=command.model_dump(mode='json');old.pop('expected_business_frontier')
  assert bt.request(command)==old
  assert cp._hash(bt.request(command))==cp._hash(old)


def test_fence_participates_in_request_fingerprint():
 fence=dict(generation=U(4),preparation_id=U(1),plan_id=U(5),plan_revision=2,epoch=0)
 command=sd.Command(action='ACCEPT',expected_revision=1,reason='r',expected_business_frontier=fence)
 first=bt.request(command);assert first['expected_business_frontier']==fence
 later=deepcopy(first);later['expected_business_frontier']['plan_id']=U(6)
 assert cp._hash(first)!=cp._hash(later)
 with pytest.raises(ValueError):bt.BusinessFrontierFence.model_validate(dict(fence,extra='authority'))


class DocumentConnection:
 def __init__(self,anchors):self.anchors=anchors;self.reads=[]
 def execute(self,query,args):
  self.reads.append(query)
  assert query=='SELECT candidate_frontier_consumptions FROM preparations WHERE id=%s'
  return self
 def fetchone(self):return {bf.ANCHORS:self.anchors}


def historical_setup(monkeypatch):
 from parkweave import case_goal_results
 q,_,_=qualification();protocol=object.__new__(bf.KnownNotStartedFrontier)
 protocol.generation=q['birth']['generation'];protocol.schema_sha256=q['protocol_sha256']
 events={}
 for proof in q['verified_prefix']:
  event=dict(id=proof['event_id'],revision=proof['event_revision'],source_sha256=proof['source_sha256'])
  proof['event_sha256']=cp._hash(event);events[proof['step_id']]=event
 previous=dict(id=q['previous_plan_id'],steps=[dict(id=p['step_id'],adapter_id=p['adapter_id'],coordination_state='VERIFIED') for p in q['verified_prefix']]+[dict(id=U(30+i),adapter_id=a) for i,a in enumerate(('P3','P4','P5'))],events=[])
 # Simulate current started marker; only historical document handling is under test.
 monkeypatch.setattr(protocol,'birth',lambda c,p:(q['birth'],dict(epoch=7,ever_started=True)))
 monkeypatch.setattr(case_goal_results,'verification',lambda parent,plan,step:events[step['id']])
 anchor=dict(generation=protocol.generation,previous_plan_id=previous['id'],request_key='original',qualification=q,qualification_sha256=cp._hash(q))
 return protocol,previous,q,anchor


def test_historical_saved_anchor_survives_later_started_marker(monkeypatch):
 protocol,previous,q,anchor=historical_setup(monkeypatch);c=DocumentConnection([anchor])
 assert protocol.qualify(c,dict(id=UUID(U(1))),previous,historical=True,consumption_key='original')==q
 assert len(c.reads)==1


@pytest.mark.parametrize('mutation',['missing','duplicate','digest','prefix_rehashed','birth_rehashed','protocol_rehashed','previous','key'])
def test_historical_anchor_mutations_refuse(monkeypatch,mutation):
 protocol,previous,q,anchor=historical_setup(monkeypatch);anchors=[deepcopy(anchor)]
 if mutation=='missing':anchors=[]
 elif mutation=='duplicate':anchors.append(deepcopy(anchor))
 elif mutation=='digest':anchors[0]['qualification_sha256']='e'*64
 elif mutation.endswith('_rehashed'):
  value=anchors[0]['qualification']
  if mutation=='prefix_rehashed':value['verified_prefix'][0]['event_id']=U(99)
  elif mutation=='birth_rehashed':value['birth']['owner_id']='other'
  else:value['protocol_sha256']='f'*64
  anchors[0]['qualification_sha256']=cp._hash(value)
 elif mutation=='previous':anchors[0]['previous_plan_id']=U(99)
 elif mutation=='key':anchors[0]['request_key']='other'
 with pytest.raises(Conflict):protocol.qualify(DocumentConnection(anchors),dict(id=UUID(U(1))),previous,historical=True,consumption_key='original')


def test_live_started_marker_cannot_be_historicalized_implicitly(monkeypatch):
 protocol,previous,q,anchor=historical_setup(monkeypatch)
 with pytest.raises(Conflict):protocol.qualify(DocumentConnection([anchor]),dict(id=UUID(U(1))),previous)


def test_original_full_five_branch_keeps_original_verification_guard():
 tree=ast.parse(inspect.getsource(compatibility.compare))
 branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=='frontier_profile is None')
 text=ast.unparse(ast.Module(body=branch.body,type_ignores=[]))
 assert "for step in previous['steps']" in text
 assert 'verification(parent, previous, step)' in text
 assert "step.get('coordination_state') != 'VERIFIED'" in text
 assert "step['verified_sha256'] != cp._hash(step['verified_sources'])" in text
