"""Verify frozen whole-module results; never execute tests or splice node scores.

Without retry selections every planned window must pass on its original run.
An alternate whole-module attempt needs explicit reason and replaces records:
 {"window":"retry-name","modules":[...],"reason":"...",
  "replaces":[{"window":"original-name","modules":[...]}]}
The original full receipt/collection/JUnit/manifests remain independently checked.
"""
from pathlib import Path
from datetime import datetime
import argparse,collections,hashlib,json,subprocess,xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def check(condition,message):
    if not condition:raise AssertionError(message)


def identity(case):
    parts=case.get('classname','').split('.')
    pos=next((i for i,v in enumerate(parts) if v.startswith('test_')),None)
    check(pos is not None,'JUnit classname has no test module')
    return 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[case.get('name','')])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,default=Path('.runtime/plan-reapproval-final/v2'))
    parser.add_argument('--root',type=Path,default=Path('.runtime/plan-reapproval-root/v2'))
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--effective',type=Path)
    parser.add_argument('--ci-selection',type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args();base=args.base;root=args.root
    freeze_path=args.freeze or root/'freeze.json';selection_path=args.selection or base/'selection.json'
    freeze=load(freeze_path);planned=load(selection_path)
    effective_path=args.effective or base/'final-main-selection.json'
    chosen=load(effective_path) if effective_path.exists() else [dict(window=k,modules=v) for k,v in planned['main_windows'].items()]
    ci_path=args.ci_selection or base/'final-ci-selection.json'
    ci_choice=load(ci_path) if ci_path.exists() else dict(window='ci-metadata-solo',modules=planned['separate_ci_window'])
    expected=sum(planned['main_windows'].values(),[])
    check(len(expected)==len(set(expected))==planned['planned_disjoint_modules'],'planned modules must be disjoint')
    new_modules=sum((v for k,v in planned['main_windows'].items() if k=='new' or k.startswith('new-')),[])
    check(len(new_modules)==len(set(new_modules))==planned['new_modules'],'new module declarations differ')
    check(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==freeze['source_sha'],'HEAD differs from frozen source')
    initial={p:sha(p) for group in ('source_paths','all_tracked_sha256','runner_paths') for p in freeze[group]}
    for group in ('source_paths','all_tracked_sha256','runner_paths'):
        check({p:initial[p] for p in freeze[group]}==freeze[group],group+' differs from freeze')
    receipts={};evidence={};read_windows={}
    def read(name):
        if name in read_windows:return read_windows[name]
        check(isinstance(name,str) and name and '/' not in name and '\\' not in name,'invalid window name')
        path=base/(name+'.json');data=load(path);collection_path=base/(name+'-collection.json');collection=load(collection_path)
        check(data['source_sha']==freeze['source_sha'],name+': source SHA mismatch')
        check(collection==data['collected_nodes'] and len(collection)==len(set(collection)),name+': collection mismatch/duplicate')
        check(not data['source_drift'] and not data['all_tracked_drift'] and not data['runner_drift'],name+': actual drift reported')
        check(data['collection_junit_exact_match'] and data['unique_junit_nodes'],name+': runner JUnit reconciliation failed')
        files=[path,collection_path,base/(name+'.xml')]
        for suffix,field in (('', 'source_paths'),('-all-tracked','all_tracked_sha256')):
            before=base/(name+suffix+'-before.json');after=base/(name+suffix+'-after.json')
            check(load(before)==load(after)==freeze[field],name+': '+field+' before/after mismatch');files.extend([before,after])
        check(data['tracked_source_paths']==len(freeze['source_paths']) and data['all_tracked_paths']==len(freeze['all_tracked_sha256']),name+': path counts differ')
        provenance_path=base/(name+'-collection-plugin-provenance.json');provenance=load(provenance_path)
        expected_plugin=base/'shared_capture.py'
        check(provenance==data['capture_plugin_provenance'],name+': plugin provenance copies differ')
        check(Path(provenance['actual_path']).resolve()==Path(provenance['expected_path']).resolve()==expected_plugin.resolve(),name+': capture plugin path differs')
        check(provenance['scope']=='ARTIFACT_COLLECTION_CAPTURE_ONLY' and provenance['product_logic_patched'] is False,name+': invalid capture scope')
        check(provenance['sha256']==freeze['runner_paths'][str(expected_plugin)],name+': capture plugin hash differs');files.append(provenance_path)
        nodes={};keys=[];skips=[]
        for case in ET.parse(base/(name+'.xml')).iter('testcase'):
            node=identity(case);check(node not in nodes,name+': duplicate JUnit node')
            keys.append(dict(classname=case.get('classname'),name=case.get('name')))
            nodes[node]='ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
            if nodes[node]=='SKIP':
                skipped=case.find('skipped');reason=(skipped.get('message','')+' '+''.join(skipped.itertext())).strip()
                check(bool(reason),name+': unrecorded skip reason');skips.append(dict(node=node,reason=reason))
        check(set(nodes)==set(collection) and len(nodes)==len(collection),name+': collection/JUnit differ')
        check(keys==data['testcase_keys'],name+': raw JUnit keys differ')
        check(collections.Counter(nodes.values())==collections.Counter({k:v for k,v in data['counts'].items() if v}),name+': counts differ')
        check(len(data['modules'])==len(set(data['modules'])) and {n.split('::',1)[0] for n in nodes}==set(data['modules']),name+': complete module collection required')
        for key in ('started_utc','finished_utc'):check(datetime.fromisoformat(data[key]).utcoffset() is not None,name+': UTC offset missing')
        check(datetime.fromisoformat(data['started_utc'])<=datetime.fromisoformat(data['finished_utc']),name+': reversed interval')
        evidence.update({str(p):sha(p) for p in files});receipts[name]=dict(receipt=str(path),counts=data['counts'],exit_code=data['exit_code'],modules=data['modules'])
        read_windows[name]=(data,nodes,skips);return read_windows[name]
    # Check original complete windows even if some whole modules are superseded.
    for name,modules in planned['main_windows'].items():
        data,_,_=read(name);check(data['modules']==modules,name+': original module list differs from selection')
    all_nodes={};all_modules=[];windows={};retry_records=[];all_intervals=[]
    for item in chosen:
        name=item['window'];selected=item['modules'];data,nodes,_=read(name)
        check(name not in windows,'effective window selected twice')
        check(bool(selected) and len(selected)==len(set(selected)) and set(selected)<=set(data['modules']),name+': invalid module subset')
        if name not in planned['main_windows']:
            check(bool(item.get('reason')) and isinstance(item.get('replaces'),list) and bool(item['replaces']),name+': retry reason/replaces required')
            replaced=[]
            for old in item['replaces']:
                prior,_,_=read(old['window']);check(set(old['modules'])<=set(prior['modules']),name+': invalid replacement modules');replaced.extend(old['modules'])
            check(len(replaced)==len(set(replaced)) and set(replaced)==set(selected),name+': whole module retry must replace exact modules')
            check(set(data['modules'])==set(selected),name+': retry must run exactly selected complete modules')
            retry_records.append(item)
        if set(selected)==set(data['modules']):check(data['exit_code']==0,name+': full selected window failed')
        else:check(bool(item.get('reason')),name+': whole-module exclusion reason required')
        subset={n:s for n,s in nodes.items() if n.split('::',1)[0] in selected}
        check(subset and set(subset.values())=={'PASS'},name+': selected module not entirely PASS')
        check(not set(subset)&set(all_nodes),name+': duplicate effective test node')
        check(not set(selected)&set(all_modules),name+': duplicate effective module')
        all_nodes.update(subset);all_modules.extend(selected)
        windows[name]=dict(passes=len(subset),modules=len(selected),elapsed_seconds=data['elapsed_seconds'],receipt=str(base/(name+'.json')),reason=item.get('reason'),raw_counts=data['counts'],raw_exit_code=data['exit_code'])
    check(set(all_modules)==set(expected) and len(all_modules)==len(expected),'effective complete modules differ from plan')
    new_nodes={n for n in all_nodes if n.split('::',1)[0] in new_modules}
    check(len(new_nodes)==planned['expected_new_tests'],'actual new-test count differs from selection')
    ci_name=ci_choice['window'];ci,ci_nodes,ci_skips=read(ci_name)
    check(len(ci['modules'])==len(planned['separate_ci_window'])==12 and set(ci['modules'])==set(planned['separate_ci_window']),'CI complete modules differ')
    check(ci['exit_code']==0 and ci['counts']==dict(PASS=433,FAIL=0,ERROR=0,SKIP=14),'CI expected 433 PASS and 14 original skips')
    check(not set(ci_nodes)&set(all_nodes),'CI/test overlap')
    if ci_name!='ci-metadata-solo':
        check(bool(ci_choice.get('reason')) and ci_choice.get('replaces')=='ci-metadata-solo','CI retry needs explicit full-window replacement')
        original,_,_=read('ci-metadata-solo');check(original['modules']==ci['modules'],'CI replacement changes modules')
        retry_records.append(dict(kind='separate_ci',**ci_choice))
    # Every CI attempt is solo from its first execution, including a failed
    # original if an explicit later whole-window replacement is selected.
    ci_modules=set(planned['separate_ci_window'])
    for ci_attempt,(ci_data,_,_) in read_windows.items():
        if set(ci_data['modules'])!=ci_modules:continue
        for name,(data,_,_) in read_windows.items():
            if name==ci_attempt:continue
            lo=max(datetime.fromisoformat(ci_data['started_utc']),datetime.fromisoformat(data['started_utc']))
            hi=min(datetime.fromisoformat(ci_data['finished_utc']),datetime.fromisoformat(data['finished_utc']))
            check(lo>=hi,ci_attempt+' overlaps pytest window '+name)
    recovery,_,_=read('recovery-solo')
    recovery_modules=set(recovery['modules'])
    for name,(data,_,_) in read_windows.items():
        if set(data['modules']) in (ci_modules,recovery_modules):continue
        check(datetime.fromisoformat(data['finished_utc'])<=datetime.fromisoformat(recovery['started_utc']),'recovery-solo did not follow other affected windows: '+name)
    for p,h in initial.items():check(sha(p)==h,'verification input changed: '+p)
    output=dict(status='PASS',source_sha=freeze['source_sha'],modules=len(all_modules),unique_passes=len(all_nodes),new_passes=len(new_nodes),windows=windows,
        separate_ci=dict(modules=len(ci['modules']),counts=ci['counts'],receipt=str(base/(ci_name+'.json')),selection_reason=ci_choice.get('reason'),skip_reasons=ci_skips,solo_intervals_checked=True),
        source_paths=len(freeze['source_paths']),all_tracked_paths=len(freeze['all_tracked_sha256']),runner_paths=len(freeze['runner_paths']),all_inputs_stable=True,
        effective_selection=chosen,retry_records=retry_records,complete_attempts=receipts,evidence_sha256=evidence,
        scope='Complete affected modules only; retries require explicit whole-module replacement. Separate CI433/14 original skips. No old failure/retry required or presumed. New Chromium scope is only actual recorded modes; Windows/formal AT/models/production remain unexecuted.')
    target=args.out or root/'final-regression-verification.json';target.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in {'windows','effective_selection','complete_attempts','evidence_sha256'}}))


if __name__=='__main__':main()
