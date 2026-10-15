"""Independent pair auditor; prepare is not audit. No root exporter imports."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import argparse,ast,hashlib,json,re,subprocess
import xml.etree.ElementTree as ET
from fast_known_redaction import KnownTokenRedactor
from redaction_reconstruct import reconstruct
from scan_fixture_contexts import scan_fixture_contexts

ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/at24-27-audit'
ARCHIVE=ROOT/'docs/F2/evidence/at24-27-change-batch-20261015'
DIRS=('at24-27-root','at24-27-independent','at24-27-review','at24-27-backend','at24-27-rebind-tests','at24-27-repair-review','at24-27-review-v2')
SUFFIXES={'.log','.xml','.json','.jsonl','.txt','.exit','.py','.js','.md','.patch'}
EXCLUDED={'archive-index.json','archive-audit.json','archive-independent-audit.json','delivery-draft.md','delivery-report-template.md','critical-path-draft.md'}
TEMPLATE=ROOT/'.runtime/at24-27-root/delivery-report-template.md'
TOKEN=re.compile(rb'[\"\']([A-Za-z0-9_-]{43})[\"\']')
def sha(b):return hashlib.sha256(b).hexdigest()
def record(path):
 data=path.read_bytes();return {'bytes':len(data),'sha256':sha(data)}
def load(path):return json.loads(path.read_text())
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def now():return datetime.now(timezone.utc).isoformat()
def frozen(sha_ref):
 result={};bad=[]
 for row in subprocess.check_output(['git','ls-tree','-rz','--full-tree',sha_ref],cwd=ROOT).split(b'\0'):
  if not row:continue
  meta,path=row.split(b'\t',1);mode,kind,oid=meta.decode().split();path=path.decode();assert kind=='blob'
  b=(ROOT/path).read_bytes();result[path]={'bytes':len(b),'sha256':sha(b),'git_blob':oid}
  if hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()!=oid:bad.append(path)
 assert not bad,'frozen Git bytes mismatch: '+repr(bad)
 return result

def candidates():
 paths=[]
 for name in DIRS:
  paths.extend(p for p in (ROOT/'.runtime'/name).rglob('*') if p.is_file() and p!=TEMPLATE and p.suffix in SUFFIXES and p.name not in EXCLUDED and '.private.' not in p.name and '__pycache__' not in p.parts and 'worktree' not in p.parts and not any(x.startswith('pytest-') for x in p.parts))
 return sorted(paths)

def known_private():
 paths=[ROOT/'.runtime/template-migration-tests-20261014/redaction-values.private.json',ROOT/'.runtime/template-structure-tests-20261015/redaction-values.private.json']
 # Include nested test-created redaction sets too: missing a producer's private
 # registry must not turn an actual known session residual into a public PASS.
 paths += [p for name in DIRS for p in (ROOT/'.runtime'/name).rglob('*redaction*.private.json')]
 values=set();inventory=[]
 for p in sorted(set(paths)):
  if not p.is_file():continue
  data=load(p);assert isinstance(data,list) and all(isinstance(x,str) for x in data)
  values.update(v for v in data if len(v)>=16);inventory.append({'path':str(p.relative_to(ROOT)),**record(p),'values':len(data)})
 return sorted(values,key=len,reverse=True),inventory

def prepare(source_sha):
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==source_sha
 f=load(ROOT/'.runtime/at24-27-root/final-freeze-v2.json');assert f['source_sha']==source_sha and len(f['source_paths'])==605
 allfiles=frozen(source_sha)
 assert all(allfiles[p]['sha256']==v for p,v in f['source_paths'].items())
 save('prepare-source-snapshot.json',{'status':'PREPARED_ONLY_NOT_AUDITED','source_sha':source_sha,'utc':now(),'all_tracked_count':len(allfiles),'all_tracked':allfiles,'candidate_evidence':{str(p.relative_to(ROOT)):record(p) for p in candidates()},'notice':'Root shard outputs are still active; pre-export inventory is historical and final pair snapshots are taken only after explicit archive-ready signal. All72 final formal modules must execute5a7eee8. Previous77059b4 full windows include26 real test-driver startup failures, reviewer388PASS and interrupted independent208/235; repaired focused26 at77059b4 plus the one uncommitted web line stays WIP evidence, not final72 coverage. Earlier WIP, fixture, setup, integration and reviewer-oracle failures remain historical evidence and do not contribute passing frozen coverage.'})
 print(json.dumps({'status':'PREPARED_ONLY_NOT_AUDITED','source_sha':source_sha,'tracked':len(allfiles)}))

def state(t):return 'ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
def audit(source_sha):
 start=now();all_before=frozen(source_sha);indexbytes=(ARCHIVE/'index.json').read_bytes();index=json.loads(indexbytes)
 assert index['source_sha']==source_sha and index['scope']=='AT24_27_INTEGRATED_CHANGE_BATCH_EVIDENCE'
 values,private_before=known_private();redactor=KnownTokenRedactor(values);seen=set();raw_seen=set();raw_before={};export_before={};counts=Counter();reds=Counter();xml={};js=[];tokens=[]
 metadata_before={name:record(ARCHIVE/name) for name in ('.gitattributes','README.md','audit.json','index.json')}
 for entry in index['entries']:
  rawpath=ROOT/entry['raw_path'];target=ROOT/entry['export_path']
  assert rawpath.is_file() and not rawpath.is_symlink() and target.is_file() and not target.is_symlink()
  assert rawpath.resolve().is_relative_to(ROOT/'.runtime') and target.resolve().is_relative_to(ARCHIVE)
  assert rawpath.relative_to(ROOT/'.runtime').parts[0] in DIRS and target.relative_to(ARCHIVE)==rawpath.relative_to(ROOT/'.runtime')
  assert '.private.' not in rawpath.name and '__pycache__' not in rawpath.parts and target not in seen and rawpath not in raw_seen
  seen.add(target);raw_seen.add(rawpath);raw=rawpath.read_bytes();data=target.read_bytes()
  assert (len(raw),sha(raw))==(entry['raw_bytes'],entry['raw_sha256']),'raw identity: '+entry['raw_path']
  assert (len(data),sha(data))==(entry['export_bytes'],entry['export_sha256']),'export identity: '+entry['export_path']
  expected,replacements=reconstruct(raw,rawpath.suffix,values,redactor)
  assert data==expected and replacements==entry['redactions'],'independent redaction mismatch: '+entry['raw_path']
  assert not redactor.has_residual(data.decode()),'known private residual: '+entry['export_path']
  fixture_residuals=scan_fixture_contexts(data,target.suffix)
  assert not fixture_residuals,'fixture context residual (hash-only): '+repr(dict(path=entry['export_path'],matches=fixture_residuals))
  raw_before[entry['raw_path']]=record(rawpath);export_before[entry['export_path']]=record(target);counts['files']+=1;counts['bytes']+=len(data);reds.update(replacements)
  for value in set(TOKEN.findall(data)):
   if re.search(rb'[A-Z]',value) and re.search(rb'[a-z]',value) and re.search(rb'[0-9]',value):tokens.append({'path':entry['export_path'],'sha256':sha(value),'length':43})
  if target.suffix=='.xml':
   a=ET.fromstring(raw);b=ET.fromstring(data)
   assert [(n.tag,sorted(n.attrib)) for n in a.iter()]==[(n.tag,sorted(n.attrib)) for n in b.iter()]
   identity=lambda root:Counter((t.get('classname'),t.get('name'),state(t)) for t in root.iter('testcase'))
   assert identity(a)==identity(b),'testcase identity/status changed: '+entry['raw_path']
   xml[entry['raw_path']]=dict(Counter(state(t) for t in a.iter('testcase')));counts['xml']+=1
  elif target.suffix=='.json':json.loads(data);counts['json']+=1
  elif target.suffix=='.jsonl':
   for line in data.splitlines():json.loads(line)
   counts['jsonl']+=1
  elif target.suffix=='.py':ast.parse(data);compile(data,str(target),'exec');assert raw==data;counts['python']+=1
  elif target.suffix=='.js':
   assert raw==data;r=subprocess.run(['node','--check',str(target)],capture_output=True);js.append({'path':entry['export_path'],'exit_code':r.returncode});counts['javascript']+=1
 assert raw_seen==set(candidates()),'primary candidate inventory changed/omitted'
 extras=sorted(str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob('*') if p.is_file() and p not in seen)
 assert set(extras)=={'.gitattributes','README.md','audit.json','index.json'},repr(extras)
 assert (ARCHIVE/'.gitattributes').read_text().splitlines()[-1]=='* -text'
 save('unclassified-token-hashes.json',tokens);assert not tokens,'unclassified43-character candidate(s), hash-only list retained'
 assert all_before==frozen(source_sha) and indexbytes==(ARCHIVE/'index.json').read_bytes()
 assert metadata_before=={name:record(ARCHIVE/name) for name in metadata_before}
 for path,old in raw_before.items():assert record(ROOT/path)==old,'raw changed: '+path
 for path,old in export_before.items():assert record(ROOT/path)==old,'export changed: '+path
 _,private_after=known_private();assert private_before==private_after
 save('raw-snapshot.json',raw_before);save('export-snapshot.json',export_before)
 result={'status':'PAIR_REBUILD_PASS_FINAL_COVERAGE_GATE_PENDING','source_sha':source_sha,'started_utc':start,'finished_utc':now(),'index_sha256':sha(indexbytes),'checks':dict(counts),'redactions':dict(reds),'independent_reconstruction':True,'producer_verifier_imported':False,'known_private_residuals':0,'known_private_values':len(values),'private_sets':private_before,'redactor_statistics':redactor.public_statistics(),'historical_xml_counts':xml,'javascript_syntax':js,'supplemental_metadata':metadata_before,'all_tracked':len(all_before),'all_tracked_bytes':sum(p['bytes'] for p in all_before.values()),'raw_export_and_source_before_after_unchanged':True,'limitations':['Pair checks alone are not final source/coverage signoff','All formal windows must execute the exact final freeze; earlier WIP/setup/integration/reviewer-oracle failures stay historical','Owner note and explicit choices are coordination history, not facts, authorization, automatic source adoption, unlock or VERIFY','Windows/real browser/formal AT/business sources/real models/production/remoteCI NOT_RUN']}
 save('archive-independent-pairs.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['private_sets','historical_xml_counts']},ensure_ascii=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--audit',action='store_true');parser.add_argument('--source-sha',required=True);args=parser.parse_args();assert re.fullmatch('[a-f0-9]{40}',args.source_sha);OUT.mkdir(exist_ok=True,parents=True)
 prepare(args.source_sha) if args.prepare else audit(args.source_sha)
