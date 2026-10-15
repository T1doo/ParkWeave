"""Six literal reservation checks against the new v3 view branch.

Dependencies supply a known saved inspection. This is a pure view-branch probe,
not a PostgreSQL event-budget end-to-end test or a complete module regression.
"""
from copy import deepcopy
from pathlib import Path
import json
import os

from parkweave import material_package_continuation as package


def test_literal_v3_plan_and_opportunity_reservation_edges(monkeypatch):
    note=dict(text='SYNTHETIC unchanged manual',text_sha256='a'*64,revision=1,
              event_id='00000000-0000-4000-8000-000000000009')
    steps=[dict(id='00000000-0000-4000-8000-'+str(i).zfill(12),adapter_id='P'+str(i)) for i in range(1,6)]
    # Expected outcomes are literal from the frozen 64/128 contract. Neither
    # the tested implementation nor its closure computes these expectations.
    cases=[('plan57_ledger126_no_lock',57,126,False,True),
           ('plan58_ledger126_no_lock',58,126,False,False),
           ('plan56_ledger126_one_P3_lock',56,126,True,True),
           ('plan57_ledger126_one_P3_lock',57,126,True,False),
           ('plan57_ledger127_no_lock',57,127,False,False),
           ('plan57_ledger125_no_lock',57,125,False,True)]
    results=[]
    for name,plan_revision,ledger_revision,locked,expected in cases:
        plan=dict(id='00000000-0000-4000-8000-000000000008',revision=plan_revision,
                  steps=deepcopy(steps),events=[],history=[])
        if locked:plan['steps'][2]['probe_manual_lock']=True
        parent=dict(service_case_plan=plan)
        base=dict(note=deepcopy(note),ledger_revision=ledger_revision,materials=[],
                  card_id='00000000-0000-4000-8000-000000000007')
        core=dict(coverage=dict(required=False,coverage_known=True,coverage_satisfied=True,conditions=[]))
        known_basis=dict(base,package_confirmation=core)
        common=dict(state='NO_CHANGE',note=deepcopy(note),blocking_reasons=[],
                    affected=[],preserved=[s['id'] for s in steps])
        with monkeypatch.context() as patch:
            patch.setattr(package.notes,'_view',lambda *a,**k:(deepcopy(common),deepcopy(base)))
            patch.setattr(package,'command_basis',lambda *a,**k:deepcopy(known_basis))
            patch.setattr(package.service,'_manual_lock',lambda p,s:s.get('probe_manual_lock'))
            view,_=package._view(None,None,None,parent,base['card_id'])
        actual=set(view['action_requests'])=={'KEEP_AND_CONTINUE','MERGE_NOTE'}
        results.append(dict(name=name,expected_confirm_allowed=expected,actual_confirm_allowed=actual))
        assert actual is expected,name
    output=Path(os.environ.get('MULTIFIELD_REVIEW_PROBE_OUT',Path(__file__).parent))
    output.mkdir(parents=True,exist_ok=True)
    (output/'budget-six-checks.json').write_text(json.dumps(dict(status='PASS',
        units=len(results),unit_kind='PURE_VIEW_RESERVATION_CHECKS_WITH_KNOWN_BASIS_STUB',
        actual_PG_budget_execution=False,results=results),indent=2)+'\n')
