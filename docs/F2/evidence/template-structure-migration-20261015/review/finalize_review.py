from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
SOURCE = '60ed07b10c854c25ec575c5769c5ad539f7a6ba9'
run = json.loads((OUT/'final60-run.json').read_text())
wheel = json.loads((OUT/'final-wheel-review.json').read_text())
comparison = json.loads((OUT/'final60-tracked-source-comparison.json').read_text())
tree = ET.parse(OUT/'final60-related.xml')
cases = tree.findall('.//testcase')
counts = Counter(item.attrib['classname'] for item in cases)
failures = len(tree.findall('.//failure'))
errors = len(tree.findall('.//error'))
skips = len(tree.findall('.//skipped'))
assert run['source_sha'] == wheel['source_sha'] == comparison['source_sha'] == SOURCE
assert run['pytest_exit'] == 0 and not run['source_drift'] and not run['source_path_deviations']
assert wheel['exact'] and wheel['source_files'] == wheel['wheel_files'] == 155
assert comparison['tracked_files'] == 583 and not comparison['differences']
assert len(cases) == 302 and not failures and not errors and not skips
assert counts['tests.test_structure_review_runtime'] == 16
assert counts['tests.test_template_structure_commit_expiry'] == 3
summary = re.search(r'302 passed, (\d+) warnings in ([0-9.]+)s', (OUT/'final60-related.log').read_text())
assert summary
artifacts = ['oracles-source.py', 'test_apply_actual_commit_expiry_regression.py',
             'final60-before.json', 'final60-run.json', 'final60-related.xml',
             'final60-related.log', 'final60-related.exit', 'final-wheel-review.json',
             'final-wheel-build.log', 'final-wheel-build.exit',
             'final60-tracked-source-comparison.json', 'failure-qualifications.json']
report = dict(decision='LIMITED_PASS', source_sha=SOURCE,
    scope='Append-only template mandatory-goal strengthening already present in the original immutable six-goal Case and P1–P5 plan; underlying steps all VERIFIED; explicitly confirmed per Case, no business effect replay.',
    runtime=dict(pass_count=len(cases), fail=failures, error=errors, skip=skips,
        pytest_exit=run['pytest_exit'], warnings=int(summary.group(1)), seconds=float(summary.group(2)), modules=dict(sorted(counts.items())),
        loaded_private_modules=len(run['loaded_modules']), source_drift=run['source_drift'],
        path_deviations=run['source_path_deviations']),
    wheel={k:v for k,v in wheel.items() if k!='source_file_sha256'},
    tracked_source=comparison,
    fixed_defects=[
        'Canonical stored/recomputed/request structure SHA prevents True/1.0 proof-version equality aliases; real PG damaged original-key recovery rejects.',
        'Apply itself registers existing target SourceLease for actual guarded PG COMMIT; structure/source/description target expiry after original event UPDATE rejects and rolls back all original business/permission/coordination tables, allowing only original DENIED audit.'
    ],
    preserved=['original six goals, coverage and request/adoption fingerprint',
        'stable Case/plan/step IDs, original consumer binding and stages, every old event and verification snapshot',
        'original reservation/resource/acceptance/receipt/lifecycle outputs, unrelated Cases and permissions',
        'unaffected P1 manual lock and source hash through two structure migrations plus a description migration',
        'older original-key result and target after later migrations; no resend or automatic verification'],
    not_run=['browser / historical administrator refusal route', 'Windows/native installed adapter',
        'real model or paid calls', 'production deployment/migration', 'formal AT25–27 acceptance',
        'general destructive or arbitrary graph migration', 'remote delivery and final archive audit by this reviewer'],
    raw_evidence_policy='All red/error/interrupted windows are separate, original and qualified; no counts combined into final pass.',
    artifact_sha256={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in artifacts})
(OUT/'final60-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k in ('decision','source_sha','runtime','wheel')},ensure_ascii=False))
