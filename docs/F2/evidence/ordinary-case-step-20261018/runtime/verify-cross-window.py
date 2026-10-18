from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');raw=root/'.runtime/ordinary-case-step-20261018';ind=raw/'independent'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
tested='954825efb66d16f7e41087e1c108b45042732703'
a=raw/'frozen-954825ef';windows=[ind/'frozen-954825ef-window1',ind/'frozen-954825ef-window2']
pre=load(a/'shared-before.json');assert len(pre)==798
def phases(folder,count,failures):
    nodes=load(folder/'collection.json')
    if nodes and isinstance(nodes[0],dict):nodes=[x['nodeid'] for x in nodes]
    calls=[json.loads(x) for x in (folder/'calls.jsonl').read_text().splitlines()]
    tree=ET.parse(folder/'results.xml');cases=tree.findall('.//testcase')
    assert len(nodes)==len(set(nodes))==len(cases)==count
    assert {x.get('classname').replace('.','/')+'.py::'+x.get('name') for x in cases}==set(nodes)
    assert len(tree.findall('.//failure'))==failures
    assert not tree.findall('.//error') and not tree.findall('.//skipped')
    for phase in ['setup','call','teardown']:
        rows=[x for x in calls if x['when']==phase];assert len(rows)==count and {x['nodeid'] for x in rows}==set(nodes)
        assert sum(x['outcome']=='failed' for x in rows)==(failures if phase=='call' else 0)
        assert sum(x['outcome']=='passed' for x in rows)==count-(failures if phase=='call' else 0)
    return set(nodes),{x['nodeid'] for x in calls if x['when']=='call' and x['outcome']=='passed'},{x['nodeid'] for x in calls if x['when']=='call' and x['outcome']=='failed'}
root_nodes,root_pass,_=phases(a,48,0)
first,first_pass,first_fail=phases(windows[0],9,1);retry,retry_pass,_=phases(windows[1],1,0)
assert retry==retry_pass==first_fail and len(first_pass|retry_pass)==9
assert first_pass|retry_pass==first
assert len(root_nodes&first)==3 and len(root_nodes|first)==54
attribute=load(ind/'probe-revision-attribution.json')
assert first_fail=={attribute['failed_nodeid']}
assert sha(ind/attribute['initial_probe'])==attribute['initial_sha256']
assert sha(ind/attribute['revised_probe'])==attribute['revised_sha256']
assert sha(ind/'literal-oracle-plan.json')=='04c02fef368ede67e907d33debc99bf37099e2d5eef8026de1254f12c3231d39'
origin_counts=[];private=[]
for number,folder in enumerate(windows):
    controller=load(folder/'controller-result.json')
    assert controller['source_sha']==controller['actual_HEAD_at_start']==controller['actual_HEAD_at_end']==tested
    assert controller['exit_code']==(1 if number==0 else 0)
    for name in ['shared-before.json','shared-after.json','mirror-before.json','mirror-after.json']:assert load(folder/name)==pre
    before=load(folder/'independent-source-before.json');assert before==load(folder/'independent-source-after.json');private.append(before)
    probe=attribute['initial_sha256'] if number==0 else attribute['revised_sha256']
    assert before['test_independent_ordinary_case_step.py']==probe
    origins=load(folder/'module-origins.json');mirror=folder/'mirror'
    for row in origins:
        path=Path(row['path']);assert path.is_relative_to(mirror) and row['within_mirror']
        expected=probe if row['matches_independent_probe'] else pre[row['relative']]
        assert sha(path)==row['sha256']==expected
    origin_counts.append(dict(total=len(origins),frozen=sum(x['matches_frozen'] for x in origins),probe=sum(x['matches_independent_probe'] for x in origins)))
changed=[p for p,v in private[0].items() if private[1][p]!=v];assert changed==['test_independent_ordinary_case_step.py']
assert all(sha(root/p)==v for p,v in pre.items())
value=dict(tested_sha=tested,root_passed=48,root_new=39,root_old_targeted=9,independent_initial=dict(collection=9,passed=8,private_timing_design_call_failed=1),independent_retry=dict(collection=1,passed=1,only_failed_selector=True),independent_effective_unique_passed=9,independent_own=6,overlap=sorted(root_nodes&first),unique_passed=54,selected_inputs=798,shared_mirror_and_cross_window_inputs_equal=True,current_inputs_equal=True,root_origins=112,independent_window_origins=origin_counts,independent_probe_versions=attribute,private_interwindow_changes=changed,old_69_and_129_not_repeated_or_transferred=True,product_or_root_test_failures=0)
(raw/'cross-window-verification.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
