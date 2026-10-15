from pathlib import Path
from collections import Counter
import hashlib,json,subprocess,re,xml.etree.ElementTree as ET
BASE=Path('.runtime/source-adoption');FROZEN='4c163fe23d8a841ece7b796e40e35511d70a0797';OLD='6b8da028182d9b4ce35996eaaef2e6a78cff0666'

def cases(path):
    result={}
    for c in ET.parse(path).iter('testcase'):
        key=(c.get('classname'),c.get('name'));assert key not in result
        result[key]='ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
    return result

def node(key):
    parts=key[0].split('.');pos=next(i for i,v in enumerate(parts) if v.startswith('test_'))
    return 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[key[1]])

def normalize(value):
    prefix='tests/test_template_candidate.py::test_old_identity_material_and_result_fields_are_forbidden[case_id-'
    if value.startswith(prefix):
        assert re.fullmatch(re.escape(prefix)+r'[a-f0-9-]{36}\]',value)
        return prefix+'<IMPORT_TIME_UUID>]'
    return value

collection=json.loads((BASE/'root-collection.json').read_text());root=cases(BASE/'root-final.xml');followup=cases(BASE/'hold-recheck.xml');delta=cases(BASE/'delta-4c163fe.xml');triage=cases('.runtime/source-adoption-backend-diagnostics-triage.xml')
actual=[node(key) for key in root];expected=collection['nodes'];missing=sorted(set(expected)-set(actual));extra=sorted(set(actual)-set(expected))
assert len(missing)==len(extra)==1
assert Counter(map(normalize,expected))==Counter(map(normalize,actual))
assert len(root)==1688 and len(followup)==7 and set(followup.values())=={'PASS'}
hold={('tests.test_template_hold','test_post_check_pre_cas_revocation_must_wait_for_journal_commit'),('tests.test_template_hold','test_original_template_page_first_refusal_and_obsolete_terminal_keep_handle')}
diag={key for key,value in triage.items() if value=='FAIL'};assert len(diag)==25
assert {key for key,value in root.items() if value!='PASS'}==hold|diag
for c in ET.parse(BASE/'root-final.xml').iter('testcase'):
    if (c.get('classname'),c.get('name')) in hold:
        failure=c.find('failure');assert 'FileNotFoundError' in failure.text and '.runtime/template-hold-20261014/' in failure.text
        assert 'During handling of the above exception' not in failure.text
assert set(delta.values())=={'PASS','SKIP'}
root_scope={**root,**followup,**{k:v for k,v in delta.items() if k[0]=='tests.test_ci_diagnostics'}}
assert len(root_scope)==1689 and set(root_scope.values())=={'PASS'}
expanded={**root_scope,**delta};record=json.loads((BASE/'root-final.json').read_text());change=json.loads((BASE/'delta-4c163fe.json').read_text())
assert record['source_sha']==OLD and not record['source_drift'] and record['exit_code']==1
assert change['source_sha']==FROZEN and change['exit_code']==0 and not change['source_drift'] and change['collection_junit_exact_match']
changed=change['changed_since_business_window'];assert set(changed)=={'scripts/windows_ci/diagnostics.py','scripts/windows_ci/diagnostic-test-ids.json','tests/test_ci_diagnostics.py'}
frozen=json.loads((BASE/'tracked-freeze-6b8da028.json').read_text());paths=list(frozen['manifest']);manifest={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
assert [p for p in paths if p not in changed and manifest[p]!=frozen['manifest'][p]]==[]
assert manifest==json.loads((BASE/'delta-4c163fe-after.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==FROZEN
(BASE/'tracked-freeze-4c163fe.json').write_text(json.dumps(dict(source_sha=FROZEN,tracked_source_paths=len(paths),manifest=manifest),indent=2)+'\n')
result=dict(source_sha=FROZEN,business_execution_sha=OLD,root_modules=52,root_collected=len(expected),root_junit=len(root),collection_junit_raw_exact_match=False,collection_junit_scoped_normalized_match=True,collection_raw_missing=missing,collection_raw_extra=extra,normalization='Only test_template_candidate case_id import-time UUID; all other full parameter strings preserved.',root_window_counts=dict(Counter(root.values())),root_seconds=record['elapsed_seconds'],original_hold_failures=[node(k) for k in sorted(hold)],original_diagnostic_failures=[node(k) for k in sorted(diag)],hold_followup_counts=dict(Counter(followup.values())),diagnostic_followup_counts=dict(Counter(delta.values())),diagnostic_same_invocation_collection_exact=True,current_52_module_test_set_outcomes_across_windows=dict(Counter(root_scope.values())),expanded_unique_outcomes_across_windows=dict(Counter(expanded.values())),changed_since_business_execution=changed,all_src_bytes_unchanged=True,other_tracked_bytes_unchanged=True,tracked_source_paths=len(paths),interpretation='Historical full run:1661 PASS/27 FAIL. HOLD7 passed after only output directory creation. Final-source 8-module diagnostics run supersedes the 25 metadata failures and adds one boundary test; 8 native prerequisites remain SKIP. Current 52-module coverage is assembled from explicitly separate windows with unchanged relevant bytes, NOT a single 1689-PASS execution.')
(BASE/'final-coverage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
