"""Real original SQL/API pages, including records older than the old 100 cap."""
from uuid import UUID, uuid4
import secrets

from parkweave import preparation as prep


def test_original_preparation_pages_reach_oldest_and_keep_assignment_scope(fixture):
    store, owner, original, api = fixture
    tokens = dict(original)
    for name in ('fixture-a','fixture-b','fixture-c'):
        tokens['prep-specialist-' + name] = secrets.token_urlsafe(32)
    prep.seed_synthetic(owner,tokens)
    def headers(actor='fixture-a'):
        return {'Authorization':'Bearer '+tokens[actor], 'Idempotency-Key':str(uuid4())}
    created=[]
    for index in range(105):
        run=api.post('/api/runs',headers=headers(),json=dict(goal='SYNTHETIC page boundary '+str(index))).json()['run_id']
        store.finish(store.claim('pagination-original-local'))
        result=api.post('/api/preparations',headers=headers(),json=dict(run_id=run,
            service_id=prep.SERVICE,service_version=1,reviewer_id='prep-specialist-fixture-a'))
        assert result.status_code==201
        created.append(result.json())
    for actor in ('fixture-a','prep-specialist-fixture-a'):
        ids=[];cursor=None
        while True:
            params={'limit':20}
            if cursor:params['before']=cursor
            result=api.get('/api/preparations',headers=headers(actor),params=params)
            assert result.status_code==200
            page=result.json()
            ids.extend(item['id'] for item in page['items'])
            cursor=page['next_before']
            if cursor is None:break
        assert len(ids)==105 and len(set(ids))==105
        assert ids[-1]==created[0]['preparation_id']
    foreign=api.get('/api/preparations',headers=headers('fixture-b'),params=dict(before=created[0]['preparation_id'],limit=20))
    assert foreign.status_code==403
    first=created[0]
    found=api.get('/api/preparations',headers=headers(),params=dict(run_id=first['run_id'])).json()
    assert [item['id'] for item in found['items']]==[first['preparation_id']]
