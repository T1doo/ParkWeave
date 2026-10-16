"""Independent final archive byte/structure audit. Outputs hashes/counts only."""
from pathlib import Path
import sys,json,re,hashlib,xml.etree.ElementTree as ET,collections,datetime
sys.dont_write_bytecode=True
ROOT=Path('/workspace/ParkWeave');AUDIT=ROOT/'.runtime/plan-replacement-audit'
PUBLIC=ROOT/'docs/F2/evidence/plan-replacement-reapproval-20261016'
TOPS={'plan-replacement-'+n for n in ('root','oracle','backend','ui','review')}
TRACE=TOPS|{'plan-replacement-ui-fixture','plan-replacement-real-html','plan-replacement-chromium'}
EXT={'.log','.xml','.json','.jsonl','.txt','.exit','.py','.js','.md','.patch','.diff','.html'}
EXCLUDED={'archive-index.json','archive-audit.json','archive-independent-audit.json','delivery-draft.md','delivery-report-template.md','critical-path-draft.md','archive-readme-draft.md'}
DENIED={'__pycache__','.pytest_cache','pytest-cache','node_modules','.git','.venv','venv','xdg-cache','tmp','temp','data','pgdata','postgres','screenshots'}
CODE={
 'tests/fixture-attempt4-original.txt','tests/fixture-attempt3-original.txt','tests/fixture-attempt2-original.txt','tests/fixture-attempt1-original.txt',
 'src/parkweave/plan_replacement_compatibility.py','src/parkweave/api.py','src/parkweave/case_resource_delivery.py','src/parkweave/case_resources.py','src/parkweave/resource_plan_binding.py','src/parkweave/service_plan_approval.py','src/parkweave/web.html',
 'tests/test_plan_replacement_epoch_probes.py','tests/plan_replacement_fixture_support.py','tests/test_plan_replacement_chromium.py','tests/test_plan_replacement_reapproval.py','tests/test_replacement_oracle_fixture.py','tests/test_plan_replacement.py','tests/test_plan_replacement_independent.py','tests/test_plan_replacement_client.py','tests/plan_replacement_client_probes.js','tests/test_plan_replacement_real_html.py','tests/plan_replacement_real_html.js','tests/test_plan_reapproval_client.py','tests/test_plan_source_reapproval.py','tests/test_plan_source_reapproval_candidate.py','tests/test_plan_source_reapproval_chromium.py','tests/test_plan_source_reapproval_independent.py','tests/plan_reapproval_client_probes.js','tests/plan_source_reapproval_real_html.js','tests/test_case_resource_delivery_browser.py','tests/test_new_enterprise_local_chain_browser.py'}
def sha(b):return hashlib.sha256(b).hexdigest()
def eligible(p):
 if not p.is_file() or p.is_symlink() or p.suffix not in EXT:return False
 ps=p.relative_to(ROOT/'.runtime').parts
 if ps[0] not in TOPS or p.name in EXCLUDED or '.private.' in p.name or p.name.endswith('private.json'):return False
 if any(x in DENIED or x.startswith(('parkweave-pg','pgsql_tmp','pytest-')) or 'screenshot' in x.lower() for x in ps):return False
 for i,x in enumerate(ps):
  if x in {'src','tests','scripts'}:return '/'.join(ps[i:]) in CODE
 if 'docs' in ps:return False
 for i,x in enumerate(ps[:-1]):
  if x=='.runtime' and ps[i+1] not in TRACE:return False
 return p.name not in {'README.md','LICENSE','LICENSE.md'}
def main():
 attempt=sys.argv[1] if len(sys.argv)>1 else 'final-v1'
 require_name=re.fullmatch('[A-Za-z0-9_-]{1,60}',attempt)
 if not require_name:raise ValueError('bounded audit attempt name required')
 run_dir=AUDIT/attempt;run_dir.mkdir(exist_ok=False)
 index_raw=(PUBLIC/'index.json').read_bytes();index=json.loads(index_raw)
 errors=[];entries=index['entries'];raw_names=[x['raw_path'] for x in entries];export_names=[x['export_path'] for x in entries]
 def require(ok,msg):
  if not ok:errors.append(msg)
 final_freeze=json.loads((ROOT/'.runtime/plan-replacement-root/v2/freeze.json').read_text())
 require(index['source_sha']==final_freeze['source_sha'],'archive final source does not match latest freeze')
 require(len(raw_names)==len(set(raw_names)),'duplicate raw path');require(len(export_names)==len(set(export_names)),'duplicate export path')
 actual_eligible={str(p.relative_to(ROOT)) for n in TOPS for p in (ROOT/'.runtime'/n).rglob('*') if eligible(p)}
 require(set(raw_names)==actual_eligible,'eligible raw inventory differs from index')
 expected_public=set(export_names)|{str((PUBLIC/'index.json').relative_to(ROOT)),str((PUBLIC/'.gitattributes').relative_to(ROOT))}
 actual_public={str(p.relative_to(ROOT)) for p in PUBLIC.rglob('*') if p.is_file()}
 require(expected_public==actual_public,'public inventory has missing or unindexed files')
 registry_paths=[ROOT/'.runtime/template-migration-tests-20261014/redaction-values.private.json',ROOT/'.runtime/template-structure-tests-20261015/redaction-values.private.json']
 registry_paths+=list((ROOT/'.runtime/plan-replacement-ui-fixture').rglob('*redaction*.private.json'))
 registry_paths += [p for n in TOPS for p in (ROOT/'.runtime'/n).rglob('*redaction*.private.json')]
 registry_before={};pool=set()
 for p in registry_paths:
  if not p.is_file():continue
  raw=p.read_bytes();registry_before[str(p.relative_to(ROOT))]=sha(raw);obj=json.loads(raw)
  require(not isinstance(obj,dict) or set(obj)<={'synthetic_private_values','provenance'},'unknown private registry schema')
  require(not isinstance(obj,dict) or 'provenance' not in obj or isinstance(obj['provenance'],str),'private provenance must be string')
  vals=obj['synthetic_private_values'] if isinstance(obj,dict) else obj
  require(isinstance(vals,list) and all(isinstance(v,str) for v in vals),'private registry has non-string values')
  pool.update(v for v in vals if len(v)>=16)
 require(all(re.fullmatch('[A-Za-z0-9_-]{43}',v) for v in pool),'independent fast pool requires exact 43 URLsafe')
 ordered=sorted(pool,key=lambda v:(-len(v),v));token=re.compile(r'(?=([A-Za-z0-9_-]{43}))');placeholder='[REDACTED_SYNTHETIC_SESSION]'
 def text_redact(text,suffix,counts):
  spans=[(m.start(),m.start()+43) for m in token.finditer(text) if m.group(1) in pool]
  if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):
   for value in ordered:
    counts['exact_private_value']+=text.count(value);text=text.replace(value,placeholder)
  else:
   counts['exact_private_value']+=len(spans);pieces=[];last=0
   for start,end in spans:pieces += [text[last:start],placeholder];last=end
   pieces.append(text[last:]);text=''.join(pieces)
  lines=[]
  for line in text.splitlines(keepends=True):
   if suffix not in {'.py','.js'} and (re.match(r'^\s*\w+\s*=\s*[({].*Store object at 0x',line) or re.match(r'^\s*(?:tokens|session_tokens)\s*=\s*\{',line)):
    counts['fixture_repr_line']+=1;line='[REDACTED_SYNTHETIC_FIXTURE_REPR]'+('\n' if line.endswith('\n') else '')
   lines.append(line)
  return ''.join(lines)
 def transform(raw,suffix):
  counts={'exact_private_value':0,'fixture_repr_line':0};text=raw.decode('utf-8')
  def red(t):return text_redact(t,suffix,counts)
  def walk(o):
   if isinstance(o,str):return red(o)
   if isinstance(o,list):return [walk(v) for v in o]
   if isinstance(o,dict):return {k:walk(v) for k,v in o.items()}
   return o
  if suffix=='.json':expected=(json.dumps(walk(json.loads(text)),ensure_ascii=True,indent=2)+'\n').encode()
  elif suffix=='.jsonl':expected=''.join(json.dumps(walk(json.loads(line)),ensure_ascii=True)+'\n' for line in text.splitlines() if line.strip()).encode()
  elif suffix=='.xml':
   doc=ET.fromstring(text)
   for node in doc.iter():
    if node.text:node.text=red(node.text)
    if node.tail:node.tail=red(node.tail)
    for k,v in list(node.attrib.items()):node.set(k,red(v))
   expected=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
  else:expected=red(text).encode()
  if not any(counts.values()):expected=raw
  return expected,counts
 checked=[];totals=collections.Counter()
 for e in entries:
  p=ROOT/e['raw_path'];q=ROOT/e['export_path']
  require(eligible(p),'ineligible indexed raw '+e['raw_path'])
  require(q.resolve().is_relative_to(PUBLIC.resolve()) and not q.is_symlink(),'unsafe export path '+e['export_path'])
  require(q.relative_to(PUBLIC)==p.relative_to(ROOT/'.runtime'),'export mapping mismatch '+e['raw_path'])
  raw=p.read_bytes();export=q.read_bytes();raw_sha=sha(raw);export_sha=sha(export)
  require(raw_sha==e['raw_sha256'] and len(raw)==e['raw_bytes'],'raw hash or bytes mismatch '+e['raw_path'])
  require(export_sha==e['export_sha256'] and len(export)==e['export_bytes'],'export hash or bytes mismatch '+e['export_path'])
  expected,counts=transform(raw,p.suffix)
  require(expected==export,'independent transformed bytes mismatch '+e['raw_path']);require(counts==e['redactions'],'independent redaction counts mismatch '+e['raw_path'])
  require(not any(m.group(1) in pool for m in token.finditer(export.decode('utf-8'))),'private residual '+e['export_path'])
  if q.suffix=='.json':json.loads(export)
  elif q.suffix=='.jsonl':
   for line in export.splitlines():json.loads(line)
  elif q.suffix=='.xml':ET.fromstring(export)
  require(sha(p.read_bytes())==raw_sha,'raw changed during independent audit '+e['raw_path'])
  checked.append(dict(raw_path=e['raw_path'],raw_sha256=raw_sha,export_path=e['export_path'],export_sha256=export_sha));totals.update(counts)
 for pair in checked:
  require(sha((ROOT/pair['raw_path']).read_bytes())==pair['raw_sha256'],'raw changed across audit '+pair['raw_path'])
  require(sha((ROOT/pair['export_path']).read_bytes())==pair['export_sha256'],'public export changed across audit '+pair['export_path'])
 for extra in (PUBLIC/'index.json',PUBLIC/'.gitattributes'):
  require(not any(m.group(1) in pool for m in token.finditer(extra.read_text())),'private residual in public index/attributes')
 require(actual_eligible=={str(p.relative_to(ROOT)) for n in TOPS for p in (ROOT/'.runtime'/n).rglob('*') if eligible(p)},'eligible inventory changed across audit')
 for n,h in registry_before.items():require(sha((ROOT/n).read_bytes())==h,'private registry changed during audit')
 require((PUBLIC/'index.json').read_bytes()==index_raw,'index changed during audit')
 review=ROOT/'.runtime/plan-replacement-review';seal=json.loads((review/'seal.json').read_text())
 for name,proof in seal['files'].items():require(sha((review/name).read_bytes())==proof['sha256'],'sealed independent review changed '+name)
 new_review=ROOT/'.runtime/plan-replacement-root/v2/frozen-review';new_seal=json.loads((new_review/'seal.json').read_text())
 for name,proof in new_seal['files'].items():require(sha((new_review/name).read_bytes())==proof['sha256'],'sealed new frozen review changed '+name)
 require(new_seal['source_sha']==final_freeze['source_sha'],'new independent review source mismatches freeze')
 for name,h in final_freeze['source_paths'].items():require(sha(ROOT/name)==h,'frozen source drift '+name)
 for name,h in final_freeze['runner_paths'].items():require(sha(ROOT/name)==h,'frozen runner drift '+name)
 result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS' if not errors else 'FAIL',index_sha256=sha(index_raw),source_sha=index['source_sha'],frozen_source_count=len(final_freeze['source_paths']),frozen_runner_count=len(final_freeze['runner_paths']),pairs=len(entries),public_files=len(actual_public),raw_eligible=len(actual_eligible),private_registry_count=len(registry_before),private_pool_count=len(pool),redactions=dict(totals),review_seal_sha256=sha((review/'seal.json').read_bytes()),new_review_seal_sha256=sha((new_review/'seal.json').read_bytes()),errors=errors,checked_pairs=checked)
 target=run_dir/'final-archive-audit.json';target.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checked_pairs'}))
 if errors:raise SystemExit(1)
if __name__=='__main__':main()
