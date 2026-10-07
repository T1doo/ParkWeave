import json, hashlib, subprocess, stat, sys, collections, xml.etree.ElementTree as ET
from pathlib import Path
root=Path.cwd(); out=root/'.runtime'; before=json.loads((out/'pr0-a1e6022-source-before.json').read_text())
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
after=dict(before,head=head,files={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in before['files']},modes={p:oct(stat.S_IMODE((root/p).stat().st_mode)) for p in before['modes']})
(out/'pr0-a1e6022-source-after.json').write_text(json.dumps(after,indent=2)+'\n')
diffs=[p for p in before['files'] if before['files'][p]!=after['files'][p] or before['modes'][p]!=after['modes'][p]]
actual=json.loads((out/'pr0-a1e6022-full-actual-collection.json').read_text()); expected=json.loads((out/'eng106-materialguard-global-collection.json').read_text())
sys.path.insert(0,str(root)); from scripts.windows_ci.regression_shards import junit_cases
observed=[]
for case in ET.parse(out/'pr0-a1e6022-full-linux.xml').iter('testcase'):
 parts=case.get('classname','').split('.'); module_index=next(i for i,v in enumerate(parts) if v.startswith('test_')); node='tests/'+parts[module_index]+'.py::'+'::'.join(parts[module_index+1:]+[case.get('name','')]); status='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'; observed.append((node,status))
loaded=json.loads((out/'pr0-a1e6022-loaded-source.json').read_text())
loaded_mismatch=[]
for row in loaded['loaded_modules']:
 p=Path(row['path']); rel=str(p.relative_to(root)) if p.is_relative_to(root) else None
 if rel in before['files'] and before['files'][rel]!=row['sha256']: loaded_mismatch.append(row)
observation=json.loads((out/'pr0-a1e6022-process-observation.json').read_text()); cleanup=[]
for row in observation['runner']+observation['active_pytest_postgres']:
 proc=Path('/proc',str(row['pid'])); present=proc.exists(); state=proc.joinpath('stat').read_text().split(') ',1)[1].split()[0] if present else None; item=dict(row,proc_entry_present=present,process_state=state,live_process=present and state!='Z')
 if 'data_directory' in row: item['data_directory_present']=Path(row['data_directory']).exists()
 cleanup.append(item)
skips=[dict(nodeid='tests/'+c.get('classname','').split('.')[-1]+'.py::'+c.get('name',''),message=c.find('skipped').get('message')) for c in ET.parse(out/'pr0-a1e6022-full-linux.xml').iter('testcase') if c.find('skipped') is not None]
report={'source_head':head,'frozen_files':len(before['files']),'source_byte_or_mode_differences':diffs,'same_frozen_head':head==before['head'],'collected':len(actual['nodeids']),'same_expected_stable_keys':collections.Counter(actual['case_keys'])==collections.Counter(expected['case_keys']),'junit_matches_actual_collection':collections.Counter(n for n,s in observed)==collections.Counter(actual['nodeids']),'outcomes':dict(collections.Counter(s for n,s in observed)),'skips':skips,'primary_loaded_modules':len(loaded['loaded_modules']),'unexpected_parkweave_sources':loaded['unexpected_parkweave_sources'],'loaded_frozen_hash_mismatches':loaded_mismatch,'pytest_exitstatus':loaded['exitstatus'],'cleanup_observation':cleanup}
(out/'pr0-a1e6022-full-verification.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
assert not diffs and report['same_frozen_head'] and report['same_expected_stable_keys'] and report['junit_matches_actual_collection'] and not loaded_mismatch and not loaded['unexpected_parkweave_sources'] and loaded['exitstatus']==0
