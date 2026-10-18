from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET

root=Path('/workspace/ParkWeave');raw=root/'.runtime/case-step-notices-20261018'
final='1da2e6c28024e3d7f518a2b8d62ce271c5ddb749'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
a=raw/'frozen-1da2e6c2';b=raw/'independent/frozen-1da2e6c2-window2'
ra=load(a/'result.json');rb=load(b/'controller-result.json')
assert ra['head']==rb['source_sha']==final and ra['exit_code']==rb['exit_code']==0
def phases(folder,expected):
    nodes=load(folder/'collection.json')
    if nodes and isinstance(nodes[0],dict):nodes=[r['nodeid'] for r in nodes]
    calls=[json.loads(s) for s in (folder/'calls.jsonl').read_text().splitlines()]
    cases=ET.parse(folder/'results.xml').findall('.//testcase')
    assert len(nodes)==len(set(nodes))==len(cases)==expected
    assert {t.get('classname').replace('.','/')+'.py::'+t.get('name') for t in cases}==set(nodes)
    assert not any(ET.parse(folder/'results.xml').findall('.//'+x) for x in ['error','failure','skipped'])
    for phase in ['setup','call','teardown']:
        rows=[r for r in calls if r['when']==phase]
        assert len(rows)==expected and {r['nodeid'] for r in rows}==set(nodes)
        assert all(r['outcome']=='passed' for r in rows)
    return set(nodes)
an=phases(a,63);bn=phases(b,9)
pre=load(a/'shared-before.json');assert len(pre)==792
for folder in [a,b]:
    for name in ['shared-before.json','shared-after.json','mirror-before.json','mirror-after.json']:
        assert load(folder/name)==pre,(folder,name)
assert load(b/'independent-source-before.json')==load(b/'independent-source-after.json')
for relative,digest in load(b/'independent-source-before.json').items():
    assert sha(raw/'independent'/relative)==digest
assert all(sha(root/p)==digest for p,digest in pre.items())
origins=load(b/'module-origins.json');probe=load(b/'independent-probe-mirror-hash.json')
probe_sha=probe['private_original_sha256_at_window_pre']
assert probe['equal'] and probe_sha==probe['mirror_PRE_sha256_from_exact_copy']==probe['mirror_POST_sha256']
for row in origins:
    assert row['within_mirror']
    assert row['sha256']==(probe_sha if row['relative']==probe['path'] else pre[row['relative']])
assert len(origins)==104 and sum(r['matches_frozen'] for r in origins)==103
assert sum(r['matches_independent_probe'] for r in origins)==1
report=raw/'independent/independent-final-review.json';review=load(report)
assert sha(report)=='60034fcc57a8371f7da3bd344374b74e9b1d79b38f8092b87b5110ad8730ff28'
assert set(review['actual_parent_overlap_nodeids'])==an&bn and len(an&bn)==3
assert len(an|bn)==69 and review['open_P1']==review['open_P2']==[]
assert review['effective_combined_unique_PASS'] is None
old=raw/'frozen-928be187';oldnodes=load(old/'collection.json')
oldcalls=[json.loads(s) for s in (old/'calls.jsonl').read_text().splitlines()]
assert len(oldnodes)==63
oldphase=[r for r in oldcalls if r['when']=='call']
assert sum(r['outcome']=='passed' for r in oldphase)==62
assert sum(r['outcome']=='failed' for r in oldphase)==1
src_trees=[subprocess.check_output(['git','rev-parse',s+':src'],cwd=root,text=True).strip() for s in ['928be187f4513d3821b7b96ec3baba0bb30a2089',final]]
assert src_trees[0]==src_trees[1]
changed=[p for p,digest in load(old/'shared-before.json').items() if pre[p]!=digest]
assert changed==['tests/dispatch_notice_pagination_offline.js']
value=dict(tested_sha=final,root_passed=63,root_new=28,root_original_notice=32,root_original_offline=3,independent_passed=9,independent_own=6,overlap=sorted(an&bn),unique_passed=69,selected_inputs=792,shared_mirror_and_cross_window_inputs_equal=True,current_inputs_equal=True,root_origins=105,independent_origins=104,independent_frozen_origins=103,independent_probe_origins=1,all_origins_match=True,independent_report_sha256=sha(report),independent_combined_field_preserved=None,root_union_verified_separately=True,old_root_window=dict(tested_sha='928be187f4513d3821b7b96ec3baba0bb30a2089',passed=62,call_failed=1,retained=True,not_transferred=True),only_interwindow_input_change=changed,product_src_tree=src_trees[0],product_src_equal_between_windows=True,old_129_rerun_or_counted=False)
(raw/'cross-window-verification.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value))
