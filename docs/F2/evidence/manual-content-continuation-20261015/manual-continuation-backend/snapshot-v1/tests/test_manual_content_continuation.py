"""Exact content carriage and original owner continuation against actual PG/HTTP."""
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import plan_source_conflicts as notes, controlled_plans as cp
from test_plan_source_conflicts import (
    http_f,link_fixture,receipt_fixture,preparation_fixture,read,edit,changed,cold,
    send as old_send,path,stored,snapshot,complete,adopt,source_preview,plan_command,
)
from test_preparation import headers


def send(f,p,value,action,text=None,key=None):
    data=deepcopy(value['action_requests'][action]);data['reason']='SYNTHETIC explicit exact-content continuation'
    if action in ('EDIT_NOTE','MERGE_NOTE'):data['text']=text
    return f[3].post(path(p)+'/commands',headers=headers(f[2],key=key or uuid4().hex),json=data)


@pytest.mark.parametrize('manual,source,known,satisfied,counts',[
    ('  A\nA\nA\n','  A\nA\nA\n',True,True,[(1,1),(2,2)]),
    ('A\nA','A\nA\nA',True,False,[(3,2)]),
    ('prefix A suffix','A',True,False,[(1,0)]),
    ('A',' A',True,False,[(1,0)]),
    ('a','A',True,False,[(1,0)]),
    ('A\r\nB','A\nB',True,True,[(1,1),(1,1)]),
    ('A',' \n\t\n',False,False,[]),
    ('A\n'*128,'A\n'*128,True,True,[(128,128)]),
    ('A\n'*129,'A\n'*129,False,False,[]),
])
def test_frozen_line_carriage_is_exact_bounded_and_counts_duplicates(manual,source,known,satisfied,counts):
    result=notes.line_coverage_v1(manual,source)
    assert result['coverage_known'] is known and result['coverage_satisfied'] is satisfied
    assert [(row['required_count'],row['present_count']) for row in result['conditions']]==counts
    assert all(row['missing_count']==max(0,row['required_count']-row['present_count']) for row in result['conditions'])


def test_real_append_merge_preserves_manual_and_allows_only_original_source_adopt(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);manual='  SYNTHETIC owner authored explanation\n preserve exact whitespace  '
    first=edit(f,p,manual);p,card=changed(f,p,mixed=True,text='SYNTHETIC incoming exact row\n  second exact row')
    v=read(f,p,card);assert v.status_code==200,v.text;v=v.json();c=v['continuation']
    assert c['baseline']['text']==first['current']['source']['text'] and c['manual']['text']==manual and c['incoming']['text']==v['source']['text']
    assert c['can_merge'] and not c['can_keep_and_continue'] and not c['semantic_evaluated']
    before=stored(f,p);merged=manual+'\n'+v['source']['text'];key=uuid4().hex
    r=send(f,p,v,'MERGE_NOTE',merged,key);assert r.status_code==200,r.text;receipt=r.json()['receipt'];after=stored(f,p)
    assert r.json()['current']['state']=='CONTINUED_AWAITING_RECHECK'
    note=r.json()['current']['note'];assert note['text']==merged and note['origin']=='MANUAL' and note['verified_package_sha256'] is None
    assert receipt['plan_note']['version']==2 and receipt['plan_note']['preview_basis']['schema']==2
    assert after['steps']==before['steps'] and after['events'][:-1]==before['events']
    r=cold(f,p,key);assert r.status_code==200 and r.json()['receipt']==receipt
    preview=source_preview(f,p,card);assert preview.status_code==200 and preview.json()['can_adopt'],preview.text
    adopted=adopt(f,p,preview.json()['adoption']);assert adopted.status_code==201,adopted.text
    assert stored(f,p)['id']==after['id'] and stored(f,p)['owner_amendments']==after['owner_amendments']
