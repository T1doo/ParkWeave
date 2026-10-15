"""Independent typed-source archive auditor. No import of producer/verifier code.

--prepare captures sources and a pre-export inventory only, never a PASS.
--audit is an explicit separate action after root announces the completed archive.
Private test values are read only from the documented synthetic test sets; values
are never printed or written into this auditor's outputs.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse, ast, hashlib, json, re, subprocess
import xml.etree.ElementTree as ET

ROOT=Path('/workspace/ParkWeave')
OUT=ROOT/'.runtime/typed-source-impact-audit'
ARCHIVE=ROOT/'docs/F2/evidence/typed-source-impact-20261015'
SHA='a5d9da251c223e3a64e20d3d47987d5b58fcdb6f'
DIRS=('typed-source-impact','typed-source-impact-independent','typed-source-impact-review','typed-source-impact-backend')
SUFFIXES={'.log','.xml','.json','.jsonl','.txt','.exit','.py','.js','.md'}
EXCLUDED={'archive-index.json','archive-audit.json','archive-independent-audit.json','delivery-draft.md','critical-path-draft.md'}
FIXTURE=re.compile(r'^\s*\w+\s*=\s*[({].*Store object at 0x|^\s*(?:tokens|session_tokens)\s*=\s*\{')
TOKEN_RE=re.compile(rb'[\"\']([A-Za-z0-9_-]{43})[\"\']')

def sha(data):return hashlib.sha256(data).hexdigest()
def load(path):return json.loads(path.read_text())
def record(path):
    data=path.read_bytes();return {'bytes':len(data),'sha256':sha(data)}
def now():return datetime.now(timezone.utc).isoformat()
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def frozen_sources():
    entries={};bad=[]
    for row in git('ls-tree','-rz','--full-tree',SHA).split(b'\0'):
        if not row:continue
        meta,name=row.split(b'\t',1);mode,kind,oid=meta.decode().split();name=name.decode()
        assert kind=='blob', 'non-blob tracked path: '+name
        data=(ROOT/name).read_bytes()
        entries[name]={'sha256':sha(data),'bytes':len(data),'git_blob':oid}
        if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=oid:bad.append(name)
    assert not bad,'frozen tracked bytes differ: '+repr(bad)
    return entries

def evidence_sources():
    paths=[]
    for directory in DIRS:
        for p in (ROOT/'.runtime'/directory).rglob('*'):
            if p.is_file() and p.suffix in SUFFIXES and p.name not in EXCLUDED and '.private.' not in p.name and '__pycache__' not in p.parts and not any(x.startswith('pytest-') for x in p.parts):paths.append(p)
    return sorted(paths)

def private_sets():
    paths=[ROOT/'.runtime/template-migration-tests-20261014/redaction-values.private.json',ROOT/'.runtime/template-structure-tests-20261015/redaction-values.private.json']
    paths += [p for name in DIRS for p in (ROOT/'.runtime'/name).glob('*redaction*.private.json')]
    values=set();inventory=[]
    for p in paths:
        if not p.is_file():continue
        data=load(p);assert isinstance(data,list) and all(isinstance(x,str) for x in data)
        values.update(x for x in data if len(x)>=16)
        inventory.append({'path':str(p.relative_to(ROOT)),**record(p),'registered_values':len(data)})
    return sorted(values,key=len,reverse=True),inventory

def reconstruct(raw,suffix,values):
    counts={'exact_private_value':0,'fixture_repr_line':0}
    def text_filter(text):
        for value in values:
            n=text.count(value)
            if n:counts['exact_private_value']+=n;text=text.replace(value,'[REDACTED_SYNTHETIC_SESSION]')
        result=[]
        for line in text.splitlines(keepends=True):
            if FIXTURE.match(line):
                counts['fixture_repr_line']+=1;line='[REDACTED_SYNTHETIC_FIXTURE_REPR]'+ ('\n' if line.endswith('\n') else '')
            result.append(line)
        return ''.join(result)
    def walk(value):
        if isinstance(value,str):return text_filter(value)
        if isinstance(value,list):return [walk(x) for x in value]
        if isinstance(value,dict):return {k:walk(v) for k,v in value.items()}
        return value
    text=raw.decode('utf-8')
    if suffix=='.xml':
        doc=ET.fromstring(text)
        for n in doc.iter():
            if n.text:n.text=text_filter(n.text)
            if n.tail:n.tail=text_filter(n.tail)
            for key,value in list(n.attrib.items()):n.set(key,text_filter(value))
        export=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
    elif suffix=='.json':export=(json.dumps(walk(json.loads(text)),ensure_ascii=False,indent=2)+'\n').encode()
    elif suffix=='.jsonl':export=''.join(json.dumps(walk(json.loads(line)),ensure_ascii=False)+'\n' for line in text.splitlines() if line.strip()).encode()
    else:export=text_filter(text).encode()
    return (export if any(counts.values()) else raw),counts

def testcase_status(t):return 'ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
def junit(path,modules):
    result={}
    for t in ET.parse(path).iter('testcase'):
        parts=t.get('classname','').split('.')
        matches=[(i,m) for i,part in enumerate(parts) for m in modules if Path(m).stem==part]
        assert len(matches)==1,'ambiguous testcase module: '+str(path)
        i,module=matches[0];node=module+'::'+'::'.join(parts[i+1:]+[t.get('name')])
        assert node not in result,'duplicate testcase in '+str(path)
        result[node]=testcase_status(t)
    return result

def collection(path):
    value=load(path)
    if isinstance(value,dict):value=value.get('nodeids',value.get('nodes'))
    assert isinstance(value,list) and all(isinstance(x,str) for x in value)
    return value

def expected_windows():
    plan=load(ROOT/'.runtime/typed-source-impact/planned-regression.json')
    shards=plan['root_shards'];assert len(shards)==2 and len(shards[0])==27 and len(shards[1])==25
    assert len(set(sum(shards,[])))==52
    windows=[]
    for n,modules in enumerate(shards,1):
        base=ROOT/f'.runtime/typed-source-impact/root-{n}-v1'
        report=load(base.with_suffix('.json'));assert report['source_sha']==SHA
        result=junit(base.with_suffix('.xml'),modules)
        assert Counter(collection(Path(str(base)+'-collection.json')))==Counter(result.keys())
        assert not report['source_drift'] and report['exit_code']==0 and report['collection_junit_exact_match'] and report['unique_junit_nodes']
        assert Counter(result.values())==report['counts'] or dict(Counter(result.values()))=={k:v for k,v in report['counts'].items() if v}
        before=load(Path(str(base)+'-before.json'));after=load(Path(str(base)+'-after.json'));assert before==after
        windows.append({'label':f'root-shard-{n}','source_sha':SHA,'modules':modules,'nodes':result,'reported_elapsed_seconds':report['elapsed_seconds']})
    for label,count,seconds in [('formal',53,None),('mixed',3,None)]:
        base=ROOT/f'.runtime/typed-source-impact-independent/freeze-a5d9da2-{label}'
        report=load(Path(str(base)+'-result.json'));modules=report['modules'];result=junit(Path(str(base)+'-junit.xml'),modules)
        assert report['source_sha']==report['head_after']==SHA and report['exit_code']==0 and not report['tracked_changed'] and not report['tracked_status_after']
        assert Counter(collection(Path(str(base)+'-collection.json')))==Counter(result.keys())
        assert len(result)==count and Counter(result.values())=={'PASS':count}
        before=load(Path(str(base)+'-before.json'))['files'];after=load(Path(str(base)+'-after.json'))['files'];assert before==after
        windows.append({'label':'independent-'+label,'source_sha':SHA,'modules':modules,'nodes':result,'junit_seconds':report['junit_seconds']})
    base=ROOT/'.runtime/typed-source-impact-review/extra-a5d9da25'
    report=load(Path(str(base)+'-result.json'));result=junit(base.with_suffix('.xml'),report['modules'])
    assert report['source_sha']==SHA and report['exit_code']==0 and not report['changed_files']
    assert len(result)==262 and Counter(result.values())=={'PASS':262}
    assert Counter(collection(Path(str(base)+'-collection.json')))==Counter(result.keys())
    windows.append({'label':'independent-review-extra8','source_sha':SHA,'modules':report['modules'],'nodes':result,'junit_seconds':float(report['junit_seconds'])})
    root_nodes={};regular={};all_nodes={}
    for window in windows:
        nodes=window['nodes']
        assert not set(all_nodes)&set(nodes),'cross-window duplicate nodes require explicit attribution'
        all_nodes.update(nodes)
        if window['label'].startswith('root-'):root_nodes.update(nodes)
        if window['label']!='independent-mixed':regular.update(nodes)
    assert len({m for w in windows if w['label']!='independent-mixed' for m in w['modules']})==62
    return windows,root_nodes,regular,all_nodes

def prepare():
    assert git('rev-parse','HEAD').decode().strip()==SHA
    freeze=load(ROOT/'.runtime/typed-source-impact/freeze.json');assert freeze['source_sha']==SHA
    tracked=frozen_sources();source_paths=[p for p in git('ls-files','-z','src','tests','scripts','pyproject.toml').decode().split('\0') if p]
    assert len(source_paths)==591
    inventory={str(p.relative_to(ROOT)):record(p) for p in evidence_sources()}
    save('pre-export-snapshot.json',{'status':'PREPARED_ONLY_NOT_AUDITED','utc':now(),'source_sha':SHA,'all_frozen_git_tracked':tracked,'source_paths':source_paths,'candidate_evidence':inventory,'candidate_inventory_note':'Root shard log, result and redaction-set files can still grow before archive generation. This snapshot is not a claim of immutable final evidence. Final audit re-snapshots every indexed raw/export.'})
    save('audit-checklist.json',{'status':'PREPARED_ONLY_NOT_AUDITED','source_sha':SHA,'archive':str(ARCHIVE),'execute_only_after':'Root explicitly announces 归档已生成','checks':['frozen Git/source bytes and current HEAD scope','raw/export exact SHA256+byte sizes, unique safe paths, inventory equality','independent reconstruction without importing producer/verifier','XML structure plus testcase identity/status, JSON/JSONL parsing and numeric structure','raw Python parse/compile and raw/export JS equality; classify historical syntax failures separately','only designated synthetic private-value sets, no values emitted; private set hash/size before/after','retain all original red/failure windows','same-invocation collection exactness and disjoint root52/review8/new2 formal nodes; mixed3 separately','literal oracle expected/actual missed and wrong counts; full original HTML six modes HTTP assertions','no single-run label for disjoint shards, no historical SHA relabeling','raw/export/source before/after unchanged during audit, audit outputs excluded from primary index self-reference','limitations and final delivery/critical-path wording exact'], 'not_run':['actual archive audit','Windows','real browser','formal AT','models','production']})
    print(json.dumps({'status':'PREPARED_ONLY_NOT_AUDITED','tracked':len(tracked),'candidate_artifacts':len(inventory),'source_sha':SHA}))

def audit():
    assert (ARCHIVE/'index.json').is_file(),'archive not generated'
    start=now();source_before=frozen_sources();index_bytes=(ARCHIVE/'index.json').read_bytes();index=json.loads(index_bytes)
    assert index['source_sha']==SHA and index['scope']=='TYPED_SOURCE_IMPACT_TASK_EVIDENCE'
    values,private_before=private_sets();seen=set();raw_seen=set();counts=Counter();reds=Counter();raw_snapshot={};export_snapshot={};token_candidates=[];xml_statuses={};js_syntax=[]
    for e in index['entries']:
        raw_path=(ROOT/e['raw_path']);export_path=(ROOT/e['export_path'])
        assert raw_path.is_file() and not raw_path.is_symlink() and export_path.is_file() and not export_path.is_symlink()
        assert raw_path.resolve().is_relative_to(ROOT/'.runtime') and export_path.resolve().is_relative_to(ARCHIVE)
        assert raw_path.relative_to(ROOT/'.runtime').parts[0] in DIRS
        assert export_path.relative_to(ARCHIVE)==raw_path.relative_to(ROOT/'.runtime')
        assert '.private.' not in raw_path.name and '__pycache__' not in raw_path.parts
        assert raw_path not in raw_seen and export_path not in seen;raw_seen.add(raw_path);seen.add(export_path)
        raw=raw_path.read_bytes();data=export_path.read_bytes();raw_snapshot[str(raw_path.relative_to(ROOT))]=record(raw_path);export_snapshot[str(export_path.relative_to(ROOT))]=record(export_path)
        assert (sha(raw),len(raw))==(e['raw_sha256'],e['raw_bytes']),'raw hash/size mismatch: '+e['raw_path']
        assert (sha(data),len(data))==(e['export_sha256'],e['export_bytes']),'export hash/size mismatch: '+e['export_path']
        rebuilt,replacements=reconstruct(raw,raw_path.suffix,values)
        assert rebuilt==data and replacements==e['redactions'],'independent reconstruction mismatch: '+e['raw_path']
        assert not any(secret.encode() in data for secret in values),'known synthetic session residual: '+e['export_path']
        reds.update(replacements);counts['files']+=1;counts['export_bytes']+=len(data)
        for token in set(TOKEN_RE.findall(data)):
            if re.search(rb'[A-Z]',token) and re.search(rb'[a-z]',token) and re.search(rb'[0-9]',token):token_candidates.append({'path':e['export_path'],'sha256':sha(token),'length':len(token)})
        if export_path.suffix=='.xml':
            a=ET.fromstring(raw);b=ET.fromstring(data)
            assert [(n.tag,sorted(n.attrib)) for n in a.iter()]==[(n.tag,sorted(n.attrib)) for n in b.iter()]
            status=lambda root:Counter((t.get('classname'),t.get('name'),testcase_status(t)) for t in root.iter('testcase'))
            assert status(a)==status(b),'testcase identity/status changed: '+e['raw_path']
            xml_statuses[e['raw_path']]=dict(Counter(testcase_status(t) for t in a.iter('testcase')));counts['xml']+=1
        elif export_path.suffix=='.json':json.loads(data);counts['json']+=1
        elif export_path.suffix=='.jsonl':
            for line in data.splitlines():json.loads(line)
            counts['jsonl']+=1
        elif export_path.suffix=='.py':ast.parse(data);compile(data,str(export_path),'exec');assert data==raw;counts['python']+=1
        elif export_path.suffix=='.js':
            assert data==raw;check=subprocess.run(['node','--check',str(export_path)],capture_output=True);js_syntax.append({'path':e['export_path'],'syntax_exit':check.returncode});counts['javascript']+=1
    assert raw_seen==set(evidence_sources()),'producer inventory not equal to independent candidate inventory'
    extras=sorted(str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob('*') if p.is_file() and p not in seen)
    assert set(extras)=={'.gitattributes','README.md','audit.json','index.json'},'unexpected primary supplemental files: '+repr(extras)
    assert (ARCHIVE/'.gitattributes').read_text().splitlines()[-1]=='* -text'
    windows,root_nodes,regular,all_nodes=expected_windows()
    coverage=load(ROOT/'.runtime/typed-source-impact/final-coverage.json')
    save('computed-coverage.json',{'source_sha':SHA,'root52_counts':dict(Counter(root_nodes.values())),'regular62_counts':dict(Counter(regular.values())),'mixed3_counts':dict(Counter(windows[3]['nodes'].values())),'all_including_mixed_counts':dict(Counter(all_nodes.values())),'windows':[{k:v for k,v in w.items() if k!='nodes'}|{'counts':dict(Counter(w['nodes'].values()))} for w in windows],'root_final_coverage_claim':coverage})
    from verify_oracles_and_html import run as verify_oracles
    oracle_html=verify_oracles();save('oracle-html-recount.json',oracle_html)
    save('token-candidate-hashes.json',token_candidates)
    assert not token_candidates,'unclassified possible synthetic session token(s); see hash-only snapshot'
    source_after=frozen_sources();assert source_before==source_after
    assert index_bytes==(ARCHIVE/'index.json').read_bytes()
    for path,before in raw_snapshot.items():assert record(ROOT/path)==before,'raw changed during audit: '+path
    for path,before in export_snapshot.items():assert record(ROOT/path)==before,'export changed during audit: '+path
    _,private_after=private_sets();assert private_before==private_after
    save('archive-raw-snapshot.json',raw_snapshot);save('archive-export-snapshot.json',export_snapshot)
    report={'status':'ARCHIVE_PAIR_CHECKS_PASS_FINAL_GATE_REVIEW_PENDING','source_sha':SHA,'started_utc':start,'finished_utc':now(),'index_sha256':sha(index_bytes),'independent_export_reconstruction':True,'checks':dict(counts),'redactions':dict(reds),'private_sets':private_before,'known_private_residuals':0,'unclassified_token_candidates':token_candidates,'supplemental_files':extras,'javascript_syntax':js_syntax,'historical_xml_statuses':xml_statuses,'raw_export_before_after_unchanged':True,'all_frozen_tracked_unchanged':len(source_before),'root52_counts':dict(Counter(root_nodes.values())),'review8_counts':{'PASS':262},'new2_counts':{'PASS':53},'mixed_probe_counts':{'PASS':3},'not_run':['Windows','real browser','formal AT','models','production'],'separate_audit_sibling_required':True}
    save('archive-independent-audit.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('historical_xml_statuses','private_sets')},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--prepare',action='store_true');group.add_argument('--audit',action='store_true');args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.prepare:prepare()
    else:audit()
