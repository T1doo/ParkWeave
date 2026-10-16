"""Controlled checker mutations only; not HTTP, browser or PostgreSQL evidence."""
import json
from pathlib import Path
import subprocess
from test_unified_dependency_propagation import changed
from parkweave import typed_source_impact as typed, unified_dependency_propagation as unified


def test_original_client_rejects_self_consistent_noncanonical_graphs():
    args=changed(15)
    graph=unified.build_v1(*args)
    response=dict(scope=unified.PUBLIC_SCOPE,plan_id=args[1]['id'],source_impact=typed.build_v1(*args),
        dependency_propagation=graph,affected=graph['affected'],preserved=graph['preserved'],can_adopt=False,adoption=None)
    script=Path(__file__).with_name('unified_dependency_client_probes.js')
    result=subprocess.run(['node',str(script)],input=json.dumps(response),capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    evidence=json.loads(result.stdout)
    assert evidence['evidence_kind']=='CONTROLLED_ORIGINAL_CLIENT_CHECKER_NO_HTTP_BROWSER_PG'
    assert len(evidence['results'])==8 and all(r['status']=='PASS' for r in evidence['results'])
    assert sum(r['accepted'] for r in evidence['results'])==1
