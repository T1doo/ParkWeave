"""Freeze public sibling appendix after completed independent audit."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,subprocess,xml.etree.ElementTree as ET
from audit_archive_pairs import known_private,frozen,record
from fast_known_redaction import KnownTokenRedactor
R=Path('/workspace/ParkWeave');D=R/'.runtime/shared-source-cases-audit';S='731529bc409041f255742e11756ebc4084bb9319'
def save(n,v):(D/n).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
for name in ['archive-independent-audit.json','final-gate.json']:
 p=D/name;v=json.loads(p.read_text());assert v['status']=='PASS'
 v['oracle_unknown_breakdown']='oracle-unknown-breakdown.json'
 v['reviewer_nonproduct_subtype_check_receipt']={'path':'oracle-breakdown-first-assertion.txt','classification':'Supplemental reviewer assumption that all four conservative unknown-category shared records had literal UNKNOWN state; corrected to UNKNOWN2/NO_PLAN1/NO_PREPARATION1. Every actual literal state already matched expected; no product/trace/count changes.','not_product_failure':True}
 v['scope_stop']='All substantive audit gates PASS; no further tests expanded. Public appendix frozen after final artifact indexing.'
 save(name,v)
(D/'README.md').write_text('''# Independent shared-source Case archive audit\n\n**PASS** for final validation SHA `731529bc409041f255742e11756ebc4084bb9319`. Read `final-gate.md` and `archive-independent-audit.json`; `final-gate.json` is the same final gate in machine-readable form. `final-artifact-index.json` lists exact public appendix hashes/bytes; `publicability.json` records the known-private residual/structure check. Cache files are excluded.\n\n259 original/export pairs (25,396,224 exported bytes) were independently reconstructed, with8 exact designated synthetic private replacements and18 fixture repr lines, and zero known private residuals.25XML/71JSON/48JSONL/18Python/2JavaScript structures are intact. Primary metadata deliberately retains its historical root-checkpoint status; this independent sibling appendix is the final gate without index self-reference.\n\nThe64 complete-module/2074 unique PASS coverage is a two-execution-SHA union: `bc4f384f` root900+789/review262; `731529bc` independent123. Three graph-schema probes remain separate. Old failed windows and setup receipts are preserved. Fifteen original HTML modes use Node VM DOM with actual HTTP/ASGI/owned PostgreSQL; real browser, Windows, formal AT, real models, production and remoteCI remain NOT_RUN.\n\nThe preparation snapshot and preparation-result intentionally retain PREPARED_ONLY historical status. Successful actual pair rebuilding, coverage, oracle/HTML and report review artifacts supersede those preparation states. The pure17-test/200-case differential suite was rerun before actual rebuilding. Root and independent auditor share the previously proved token matcher provenance; structured reconstruction imported no root producer/verifier.\n\n`oracle-breakdown-first-assertion.txt` is explicitly a reviewer tool transcription of an overstrict subtype assertion, not a fabricated stdout original or product failure. Correct literal subtypes are UNKNOWN2/NO_PLAN1/NO_PREPARATION1 within the four conservative shared unknown-category records; typed unknown_scope records3 include2 deliberate expansions. All23 literal answers had zero missed/wrong/wrong-preserved comparisons throughout.\n\nOnly two finite selected-source identities/current-owner synthetic Cases are supported. The arbitrary trusted-admin SQL-damaged plan body500 observation remains outside positive validation; handled UNKNOWN claims cover bad headers/original validation conflicts. No raw/primary/product/Git/old-evidence edits occurred.\n''')
values,private=known_private();filter=KnownTokenRedactor(values)
excluded={'final-artifact-index.json','publicability.json'}
files=sorted(p for p in D.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excluded)
assert all('.private.' not in p.name for p in files)
formats={};payload=[]
for p in files:
 b=p.read_bytes();text=b.decode();assert not filter.has_residual(text),'private residual in '+p.name
 if p.suffix=='.json':json.loads(text);formats['json']=formats.get('json',0)+1
 elif p.suffix=='.xml':ET.fromstring(text);formats['xml']=formats.get('xml',0)+1
 elif p.suffix=='.py':ast.parse(text);compile(text,str(p),'exec');formats['python']=formats.get('python',0)+1
 payload.append({'path':str(p.relative_to(D)),**record(p)})
public={'status':'PASS','source_sha':S,'utc':datetime.now(timezone.utc).isoformat(),'payload_files_checked':len(payload),'payload_bytes':sum(x['bytes'] for x in payload),'known_private_pool_values':len(values),'known_private_residuals':0,'private_registry_contents_not_exported':True,'structured_parse_compile':formats,'cache_excluded':True,'scope':'All files in this new independent audit directory except its self-index/publicability metadata; those metadata files are additionally scanned after writing.','supplemental_reviewer_stop_receipt_retained':True,'actual_primary_audit':'PASS'}
save('publicability.json',public)
payload.append({'path':'publicability.json',**record(D/'publicability.json')})
index={'scope':'INDEPENDENT_SHARED_SOURCE_CASES_AUDIT_APPENDIX','status':'PASS','source_sha':S,'entries':payload,'self_index_excluded':True,'cache_excluded':True,'files':len(payload),'bytes':sum(x['bytes'] for x in payload)}
save('final-artifact-index.json',index)
for name in ['publicability.json','final-artifact-index.json']:assert not filter.has_residual((D/name).read_text())
for row in payload:assert record(D/row['path'])=={k:row[k] for k in ['bytes','sha256']}
assert len(frozen(S))==11771 and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R).strip()
print(json.dumps({'status':'PASS','source_sha':S,'public_files_indexed':index['files'],'public_bytes_indexed':index['bytes'],'index_sha256':record(D/'final-artifact-index.json')['sha256'],'known_private_residuals':0,'audit_directory_stop_writing':True}))
