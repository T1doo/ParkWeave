"""Recount final independent literal oracles and real-HTTP HTML evidence.

Called only by the archive audit after all referenced files have passed pair
hash/reconstruction checks. Test values and request bodies are never emitted.
"""
from collections import Counter
import json
from pathlib import Path

ROOT=Path('/workspace/ParkWeave');SHA='a5d9da251c223e3a64e20d3d47987d5b58fcdb6f'
def load(path):return json.loads(path.read_text())
def run():
    oracle_windows=[];html=[]
    for label,expected in [('formal',11),('mixed',3)]:
        validation=load(ROOT/f'.runtime/typed-source-impact-independent/freeze-a5d9da2-{label}-validation.json')
        assert validation['source_sha']==SHA
        records=[]
        for path in validation['oracle_statistics']['oracle_files']:
            p=ROOT/path;assert p.parent==ROOT/'.runtime/typed-source-impact-independent'
            records.extend(json.loads(line) for line in p.read_text().splitlines() if line.strip())
        assert len(records)==expected
        stats=Counter(records=len(records));run_ids=set()
        for row in records:
            assert row['head']==SHA;run_ids.add(row['run_id'])
            e=set(row['expected_affected']);a=set(row['actual_affected']);ep=set(row['expected_preserved']);ap=set(row['actual_preserved'])
            assert len(e)==len(row['expected_affected']) and len(a)==len(row['actual_affected'])
            assert not e&ep and not a&ap and e|ep==a|ap
            missed=len(e-a);wrong=len(a-e);preserved=len(ap^ep)
            assert (missed,wrong,preserved)==(row['missed_count'],row['wrong_count'],row['wrong_preserved_count'])
            assert not missed and not wrong and not preserved
            stats.update(expected_affected_pairs=len(e),actual_affected_pairs=len(a),missed_count=missed,wrong_count=wrong,wrong_preserved_count=preserved,
                         intentional_unknown_expansion_records=int(row['intentional_unknown_expansion']),unknown_scope_records=int(row['unknown_scope']=='THIS_CASE'),known_scope_records=int(row['unknown_scope'] is None))
        assert len(run_ids)==1
        expected_scenarios=Counter({'unchanged':1,'resource_collection':1,'resource_rule':1,'resource_capacity':1,'run_access':1,'receipt':1,'local_check':1,'material':1,'fact':1,'unknown':2}) if label=='formal' else Counter({'resource_collection':3})
        assert Counter(row['scenario'] for row in records)==expected_scenarios
        for key,value in stats.items():assert validation['oracle_statistics'][key]==value
        oracle_windows.append({'window':label,'literal_records':len(records),'recomputed_statistics':dict(stats),'distinct_run_ids':len(run_ids),'source_sha':SHA})
        for run in validation['full_original_html_runs']:
            rows=[json.loads(line) for line in (ROOT/run['path']).read_text().splitlines() if line.strip()]
            evidence=[x for x in rows if x.get('scope')=='FULL_ORIGINAL_HTML_TYPED_SOURCE_REAL_HTTP_ASGI_OWNED_PG']
            assert len(evidence)==1
            e=evidence[0];mode=e['mode'];assert mode==run['mode']
            calls=e['calls'];posts=[c for c in calls if c['method']=='POST'];denied=[c for c in calls if c['status']==403]
            assert len(calls)==run['requests'] and len(posts)==run['posts'] and len(denied)==run['denied_http_responses'] and e['checks']==run['checks']
            assert all(c['path'].startswith('/api/') for c in calls)
            assert any(c['path'].endswith('/source-impact') and c['method']=='GET' for c in calls)
            assert all(c['method']=='GET' for c in calls if c['path'].endswith('/source-impact'))
            if mode in ('positive','lost'):
                actions=[c.get('body',{}).get('action') for c in posts]
                assert actions==['IMPORT','REFRESH',None,'VERIFY','VERIFY','VERIFY','VERIFY']
                adoptions=[c for c in posts if c.get('body',{}).get('opportunity_proof')]
                assert len(adoptions)==1 and adoptions[0]['status']==201 and adoptions[0]['body']['local_revision'] is True
                assert len(adoptions[0]['body']['required_goals'])==6
                assert any('/goal-results' in c['path'] and c['method']=='GET' and c['status']==200 for c in calls)
                assert calls[-1]['method']=='GET' and '/api/cases/worklist' in calls[-1]['path']
                if mode=='lost':assert any('/service-case-plan/command-recovery' in c['path'] and c['method']=='GET' and c['status']==200 for c in calls)
            else:
                assert not posts
                if mode in ('open_current_403','late_read_403','open_late_403'):assert denied
                else:assert mode=='late_read_aba'
            html.append({'mode':mode,'requests':len(calls),'posts':len(posts),'denied_http_responses':len(denied),'script_checks':e['checks'],'source_sha':SHA,'full_browser':False})
    assert {r['mode'] for r in html}=={'positive','lost','open_current_403','late_read_403','open_late_403','late_read_aba'} and len(html)==6
    return {'status':'RECOUNTED_PASS','source_sha':SHA,'oracle_windows':oracle_windows,'html_runs':html,'no_values_or_bodies_emitted':True,'limits':'HTML executed with small mechanics-only DOM over actual HTTP/ASGI/owned PG; this is not a real browser or formal AT.'}
