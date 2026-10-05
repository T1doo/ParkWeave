"""Engineering execution with fixed bindings; whole AT/EX never inferred from pytest."""
import os
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from parkweave.process_env import minimal_environment

ROOT=Path(__file__).resolve().parents[1]


def validate_bindings(bindings,spec):
    expected={c['id'] for c in spec['cases']};rows=bindings['cases']
    if len(rows)!=len(expected) or {c['id'] for c in rows}!=expected:raise ValueError('missing/duplicate fixed acceptance IDs')
    for row in rows:
        if row['whole_status']!='NOT_RUN':raise ValueError('whole acceptance status cannot be prefilled PASS')
        for selector in row['engineering_selectors']:
            if not re.fullmatch(r'tests/test_[a-z0-9_]+\.py::test_[a-z0-9_]+',selector):raise ValueError('unsafe selector')
            if not (ROOT/selector.split('::')[0]).is_file():raise ValueError('missing bound test file')
    return rows


def summarize(rows,junit,exit_code):
    results={}
    for case in ET.parse(junit).getroot().iter('testcase'):
        classname=case.get('classname','').split('.')[-1]
        selector='tests/'+classname+'.py::'+case.get('name','').split('[')[0]
        outcome='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        results.setdefault(selector,[]).append(outcome)
    reports=[]
    for row in rows:
        statuses=[s for selector in row['engineering_selectors'] for s in results.get(selector,[])]
        missing=[s for s in row['engineering_selectors'] if s not in results]
        state='NOT_RUN' if not statuses else 'FAIL' if 'FAIL' in statuses else 'INCOMPLETE' if missing else 'SKIP' if all(s=='SKIP' for s in statuses) else 'PARTIAL_PASS_WITH_SKIPS' if 'SKIP' in statuses else 'PARTIAL_PASS'
        reports.append({'id':row['id'],'stage':row['stage'],'whole_status':'NOT_RUN','engineering_subset':state,
                        'counts':{s:statuses.count(s) for s in ('PASS','FAIL','SKIP')},'missing_selectors':missing,'gate':row['gate']})
    all_statuses=[s for values in results.values() for s in values]
    return {'execution_exit_code':exit_code,'whole_AT_EX':'NOT_RUN','engineering_total_counts':{s:all_statuses.count(s) for s in ('PASS','FAIL','SKIP')},'cases':reports,
            'note':'Selectors can overlap; do not sum per-AT counts. Local/mock PASS never completes LIVE/native/business acceptance.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,default=ROOT/'.runtime/engineering-acceptance.json')
    parser.add_argument('--ids',help='Optional comma-separated fixed IDs; default runs full engineering regression')
    args=parser.parse_args()
    bindings=json.loads((ROOT/'docs/F1/ATBindings.json').read_text());spec=json.loads((ROOT/'docs/验收规格.json').read_text())
    rows=validate_bindings(bindings,spec)
    if args.ids:
        ids=set(args.ids.split(','))
        if not ids<={r['id'] for r in rows}:parser.error('unknown fixed acceptance ID')
        rows=[r for r in rows if r['id'] in ids]
    private=ROOT/'.runtime';private.mkdir(mode=0o700,exist_ok=True)
    junit=private/('pytest-'+uuid.uuid4().hex+'.xml');log=private/('pytest-'+uuid.uuid4().hex+'.log')
    selectors=sorted({s for r in rows for s in r['engineering_selectors']}) if args.ids else ['tests']
    code=0
    if selectors:
        with log.open('w',encoding='utf-8') as f:
            process=subprocess.run([sys.executable,'-m','pytest','-q','--junitxml',str(junit),*selectors],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=minimal_environment(os.environ,**({'PARKWEAVE_TEST_OWNER_DSN':os.environ['PARKWEAVE_TEST_OWNER_DSN']} if os.name=='nt' and 'PARKWEAVE_TEST_OWNER_DSN' in os.environ else {})))
        code=process.returncode
    if not junit.exists():junit.write_text('<testsuites/>')
    report=summarize(rows,junit,code)
    report.update(environment=sys.platform,model_calls=0,native_windows='NOT_RUN: native manual gates not auto-graded',
                  full_regression=not bool(args.ids),private_log=str(log.relative_to(ROOT)),private_junit=str(junit.relative_to(ROOT)))
    source_files=sorted(p for folder in ('src/parkweave','tests','scripts') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.ps1','.psm1','.sql','.html'))
    report['tested_source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'whole_AT_EX':'NOT_RUN','engineering_exit_code':code,'report':str(args.report),'native_windows':'NOT_RUN','model_calls':0},ensure_ascii=False))
    raise SystemExit(code)


if __name__=='__main__':main()
