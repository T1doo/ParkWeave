"""Preparation only: bind analyzer schema to original raw traces. No gate run."""
from pathlib import Path
p=Path('.runtime/plan-reapproval-archive-audit/final_gate.py');s=p.read_text()
a=s.index("    assert len(classification['modes'])==4");b=s.index('\ndef coverage(',a)
s=s[:a]+"""    assert len(classification['modes'])==4
    for expected in classification['modes']:
        actual=found[expected['mode']]
        assert expected['trace']==actual['trace'] and expected['trace_sha256']==actual['trace_sha256'] and expected['actual_nativefetch_calls']==actual['native_fetches']
        assert expected['method_counts']['POST']==actual['posts'] and expected['method_counts']['GET']==actual['native_fetches']-actual['posts'] and expected['actual_403_count']==actual['backend403']
        assert expected['resource_commit_count']==(1 if expected['mode'] in ('positive','lost_ack') else 0)
        assert expected['verify_count']==(5 if expected['mode'] in ('positive','lost_ack') else 0)
        assert expected['real_browser']=='NOT_RUN'
    assert classification['actual_nativefetch_total']==sum(v['native_fetches'] for v in found.values())
    assert classification['python_control_http_total']=='NOT_RECORDED'
    return dict(modes=list(found.values()),native_fetches=sum(v['native_fetches'] for v in found.values()),python_control_API_total='NOT_RECORDED',real_browser='NOT_RUN')
"""+s[b:]
s=s.replace("            counts[row['coverage_kind']]+=1", """            if row.get('browser_variant'):
                variant=row['browser_variant'];assert variant['coverage_kind']=='CHROMIUM_ACTUAL_HTTP' and variant['evidence'] and variant['note']
                for evidence in variant['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            counts[row['coverage_kind']]+=1""")
s=s.replace("assert value['status']=='LIMITED_PASS' and value['records_are_not_unique_cases'] is True", """assert value['status']=='LIMITED_PASS' and value['record_counts_are_not_unique_cases'] is True
    art=ROOT/config['formal_base']/'artifacts/new-independent/test_plan_source_reapproval_independent'
    groups={prefix:[json.loads(line) for p in art.glob(prefix+'-*.jsonl') for line in p.read_text().splitlines() if line.strip()] for prefix in ('closures','closure','refusals','source-adopt','rollback','html-results')}
    assert {name:len(rows) for name,rows in groups.items()}==value['record_counts']
    assert len(groups['html-results'])==4 and len(groups['closure'])==2
    assert groups['closures'] and all(r['six_goals_current'] and r['worklist_complete'] and r['stable_ids_history'] and r['worklist_recorded_only'] for r in groups['closures'])
    assert all(r['old_occupancy_preserved'] and r['old_receipt_cold_get'] and r['six_goals'] for r in groups['closure'])
    assert all(r['no_business_writes'] for r in groups['refusals']+groups['rollback'])""")
a=s.index('def browser_checks(');b=s.index('\ndef prior_pairs(',a)
s=s[:a]+"""def browser_checks(ready,freeze,main_nodes):
    value=load(ready['browser_classification']);assert value['source_sha']==freeze['source_sha']
    assert value['status']=='LIMITED_ACTUAL_CHROMIUM_PASS' and value['included_in_new_union'] is True and value['formal_passes']==4
    assert value['raw_window_sha256']==sha((ROOT/'.runtime/plan-reapproval-final/new-chromium.json').read_bytes())
    assert len(value['modes'])==4 and {row['mode'] for row in value['modes']}=={'positive','lost_commit','lost_propose','lost_approve'}
    found=[]
    for row in value['modes']:
        path=ROOT/row['raw'];assert sha(path.read_bytes())==row['sha256'];actual=json.loads(path.read_bytes())
        assert actual['mode']==row['mode'] and actual['actual_browser']==row['actual_browser']=='INSTALLED_CHROMIUM'
        assert actual['executable']=='/usr/bin/chromium' and actual['browser_version']==row['browser_version'] and not actual['page_errors']
        assert actual['screenshots']=='NOT_TAKEN' and actual['negative_modes']=='NODE_ONLY' and actual['windows']==actual['formal_at']=='NOT_RUN'
        calls=actual['calls'];assert len(calls)==row['request_count'] and all('headers' not in c and 'token' not in c for c in calls)
        commits=[c for c in calls if c['method']=='POST' and c['path'].endswith('/resource-delivery') and c['status']==201]
        proposals=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/proposals')]
        approvals=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/commands')]
        assert len(commits)==row['resource_commits']==1 and len(proposals)==row['proposal_posts']==1 and len(approvals)==row['approval_posts']==1
        assert proposals[0]['status']==201 and approvals[0]['status']==200
        lost=[c for c in calls if c.get('committed_response_controlled_lost') or c.get('approval_response_controlled_lost')]
        assert lost==row['controlled_lost_replies']
        if row['mode']=='positive':assert not lost
        else:
            assert len(lost)==1 and lost[0].get('request_key')
            if row['mode']=='lost_commit':assert lost[0].get('committed_response_controlled_lost') is True
            else:assert lost[0].get('approval_response_controlled_lost')==('PROPOSE' if row['mode']=='lost_propose' else 'APPROVE')
            endpoint='/resource-delivery/recovery/' if row['mode']=='lost_commit' else '/plan-approval/recovery/'
            assert any(c['method']=='GET' and c['status']==200 and c['path'].endswith(endpoint+lost[0]['request_key']) for c in calls)
        identity='tests/test_plan_source_reapproval_chromium.py::test_actual_installed_chromium_explicit_source_reapproval_to_six_goals['+row['mode']+']'
        assert main_nodes.get(identity)=='PASS'
        found.append(row['raw'])
    actual_files={str(p.relative_to(ROOT)) for p in (ROOT/'.runtime/plan-reapproval-final/artifacts/new-chromium').rglob('*-calls.json')}
    assert set(found)==actual_files and len(found)==len(set(found))
    return value
"""+s[b:]
s=s.replace("bounded_Chrome_modes=len(browser['modes'])", "bounded_Chrome_modes=len(browser['modes'])")
p.write_text(s)
