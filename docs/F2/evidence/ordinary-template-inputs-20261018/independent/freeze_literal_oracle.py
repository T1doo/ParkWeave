"""Source-blind original-text oracle. No product imports, DB, or business test."""
from pathlib import Path
import datetime,subprocess,json,hashlib
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/ordinary-template-inputs-20261018/independent'
BASE='0b7ee3544fa669e621c8b8ffd58714fa357264b3';CONTRACT='c482afe0ff8ab582072fcdfec3dbdfe380c1173d';CP='docs/F2/OrdinaryTemplateInputContract-20261018.md'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def get(p,rev=BASE):return git('show',rev+':'+p)
def sha(x):return hashlib.sha256(x).hexdigest()
def write(name,obj):
 p=OUT/name
 with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
 return sha(p.read_bytes())
# Only the fixed historical Git tree is read, irrespective of later WIP/HEAD.
raw=git('ls-tree','-rz',BASE,'src','tests','scripts','pyproject.toml')
code={}
for item in raw.split(b'\0'):
 if not item:continue
 metadata,path=item.split(b'\t',1);mode,typ,oid=metadata.decode().split();assert typ=='blob'
 code[path.decode()]=oid
anchors=['README.md','docs/平台产品设计.md','docs/分阶段开发计划.md','docs/sources/V1/平台产品设计 (2).md','docs/sources/V1/分阶段开发计划 (2).md','docs/验收规格.json','docs/F1/ATBindings.json','docs/F2/TemplateLocalMigrationContract-20261014.md','docs/F2/TemplateStructureMigrationContract-20261015.md','docs/F2/TemplateUpgradeCheckContract.md','docs/F2/OrdinaryCaseStepContract-20261018.md','docs/F2/OrdinarySyntheticDemoContract-20261018.md','docs/F2/OrdinarySyntheticScopesContract-20261018.md','docs/F2/NewEnterpriseLocalChainContract.md','docs/F2/UnifiedSourcePropagationOracle-20261016.json']
objects=dict(code)
for path in anchors:objects[path]=git('rev-parse',BASE+':'+path).decode().strip()
ordered=sorted(objects);result=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=('\n'.join(objects[p] for p in ordered)+'\n').encode(),capture_output=True,check=True).stdout
position=0;inputs={}
for path in ordered:
 end=result.index(b'\n',position);oid,kind,size=result[position:end].decode().split();size=int(size);position=end+1
 content=result[position:position+size];position+=size;assert result[position:position+1]==b'\n';position+=1
 assert oid==objects[path] and kind=='blob'
 inputs[path]={'git_blob':oid,'bytes':size,'sha256':sha(content)}
assert position==len(result)
map_sha=write('baseline-inputs.json',dict(revision=BASE,selection='all baseline tracked src/tests/scripts/pyproject plus15 explicit original/fixed-AT/template/ordinary anchors; no evidence scan, no working-tree implementation',count=len(inputs),code_count=len(code),files=inputs))
contract=get(CP,CONTRACT)
with (OUT/'contract-first-read.md').open('xb') as f:f.write(contract)
product='docs/sources/V1/平台产品设计 (2).md';plan='docs/sources/V1/分阶段开发计划 (2).md'
refs=[(product,129),(product,133),(product,135),(product,139),(product,141),(product,145),(product,197),(product,208),(product,210),(product,216),(product,339),(plan,89),(plan,280),(plan,307)]
literal=[dict(path=p,line=n,revision=BASE,text=get(p).decode().splitlines()[n-1]) for p,n in refs]
ats=json.loads(get('docs/验收规格.json'));ats={x['id']:x for x in ats['cases'] if x['id'] in ['AT-04','AT-08','AT-35']}
rows=[
('TINPUT-01','product§5.2:145;F2-T06:89;contract:3,11','Scope/classification','A new original-page parameter form and current catalog pin/recovery can complete this bounded UI+isolated-consumer slice. Ordinary configured startup without legal sources must remain unavailable/refused.','Never label isolated candidate publication/permit as formal template approval or declare whole F2-T06/AT08/35 complete.'),
('TINPUT-02','consumer:196-220;engine:217-235;ParkConsumer:48-57;api:15-20,1131-1155','Admission isolation','Keep exact local fixture_UUID DB/org allowlists, exact isolated engine/catalog/repository binding and original current grants. CURRENT_PREPARATION/provider/Native mutual exclusion stays unchanged; no new provider discovery.','No failed old guard fallback, manufactured source/permission/identity, or private fixture injected into ordinary approval.'),
('TINPUT-03','product:129,135,145;engine:27-30,89-106;Consume:69-101','Explicit new parameter input','Original form takes newly supplied goal and exactly need_summary/material_outline texts, allowed source_kind/source_label, reviewer and reason under the published fixed parameter schema; preserve all mandatory template goals/constraints.','Reject empty/duplicate/missing slots, unknown fields/actions/oldCase or old evidence IDs, unsupported shape and executable data. No user JSON editing, old result copying or arbitrary schema execution.'),
('TINPUT-04','engine:254-278,300-318;consumer:243-255;contract:5','Current catalog and release binding','Discover only current actor scope: exact template release UUID/SHA, definition/hash/required goals/fixed schema plus matching current preparation_catalog service/version and canonical current source pin. Reader source and catalog source remain separate evidence domains.','No title-only/index-only selection; no automatic newest-version substitution; catalog source hash proves current directory only, not REVIEW/publication authority.'),
('TINPUT-05','contract:5;consumer:365-377','New optional pin with historical compatibility','Omitting expected_catalog_sha256 preserves old canonical CONSUME bodies/fingerprints and immutable old instances. Explicit null/invalid hash is rejected. New nonnull pin is stored in the original immutable input/binding.','No retroactive pin insertion or refingerprinting of old rows; no new journal/schema/permission kind to introduce the field.'),
('TINPUT-06','contract:5;consumer:288-294,354-381,473-506','Server revalidation','Before first Run and every existing consumer stage/current availability read, recheck original live identity/grants/reviewer/release and exact service version/current directory source pin. Stale/missing/changed source or release cannot issue a new stage.','Client GET alone is never authorization. Do not repair directory/withdrawal, substitute source, refresh expiry or reseed authority to make an instance available.'),
('TINPUT-07','product:145,208,210;contract:3','Independent instance/result','A supported new isolated input produces distinct consumer instance, Run, Case, preparation/material evidence and original journal binding while preserving prior input/material/instance history. Reauthorize the current subject.','No previous enterprise data, identity, artifact, step marker, approval or saved successful result reused as the new input result.'),
('TINPUT-08','consumer:354-381,473-511;contract:3,9','Separate decisions','Initial consume records original admission/CREATE_RUN; after observed CREATE_RUN and actual SUCCEEDED Run, explicitly resume only existing stages. Stop at PLAN_CONFIRMATION_REQUIRED after materials.','No automatic REVIEW/CONFIRM/ADOPT, verification, resource/dispatch/receipt/P1-P5 or complete-business claim from RECORDED/CONFIRMED technical journal state.'),
('TINPUT-09','consumer:365-378;contract:9','Original-key GET proof','GET recovery scopes by authenticated actor+park/org+actual database+original key. Reconstruct canonical flat action=CONSUME fingerprint from immutable saved normalized input; compare saved request fp, supplied expected fp and complete binding/release/catalog coherence.','Reject mismatched hash or another-action RESUME/EDIT/CONFIRM key; hash equality is not authority. Do not return another actor instance or infer a foreign key exists.'),
('TINPUT-10','contract:9;consumer repository:167-182','Read-only recovery and unknown','New GET executes no consume/resume/product send/journal update, no key renewal. RECORDED means original admission exists; stage results remain separate. NOT_OBSERVED is a bounded current absence, never permanent noncommit proof.','A current403/revocation never clears or disproves previous unknown commit. Keep original key/body frozen, do not automatically POST/replay or create a second key.'),
('TINPUT-11','contract:7,9;product:133,339','Original full HTML UI lifecycle','Edit/session change/navigation/ABA invalidate old current-catalog response and submission state; immediately before explicit first POST, reread and compare selected release and directory pin. Unknown create freezes body/key and permits only GET recovery.','Late successful/403 GET or POST response cannot restore old actor/form; no body/token browser storage, URL interpolation, untrusted HTML execution or hidden automatic new request.'),
('TINPUT-12','contract:5,9;consumer:211-229,263-279','Fresh authorization and availability','Current READ/PREPARE/EXECUTE/case.create and reviewer same-scope REVIEW_ASSIGNED stay original. Directory/release withdrawal or changed source marks current use unavailable or rejects new action. Historical recovery may separately report only what current auth permits.','No cached catalog/grant/previous review used to resurrect current availability or cross-owner/park/org access.'),
('TINPUT-13','product:216;contract:11;engine:44-80;ParkConsumer:111-126','Formal missing inputs','List exact immutable reviewed release/source/head/revocation proofs and current subject/role/service/field/journal mappings needed for future formal work, separate from existing legal PG preparation rights.','Do not create generic DTO/loader or treat field presence, a REVIEW string or SYNTHETIC_CONTRACT_FIXTURE as formal authority. Supplying fields does not remove the existing hard isolated gate.'),
('TINPUT-14','contract:13,15;AT08/35','Evidence boundary','Freeze actual SHA, limited pure/API/ownedPG/worker/originalHTML NodeVM nodes, PREPOST inputs, module origins and all failure/token-safe raw-public pairs; effective node counts by actual identity.','No old10/14/P1-P5 or full template matrix rerun for count; no browser/Windows/model/thirdscope/real production. Previous HTTP timeout cause remains UNKNOWN, not closed by laterPASS.')
]
oracle={'kind':'SOURCE_BLIND_LITERAL_ORACLE','frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline':BASE,'contract_commit':CONTRACT,'contract_path':CP,'contract_sha256':sha(contract),'baseline_inputs_sha256':map_sha,'literal_originals':literal,'fixed_AT_cases':ats,'rows':[dict(id=i,source=s,topic=t,must=m,must_not=n) for i,s,t,m,n in rows],'read_boundary':'Only baseline Git objects and committed contract; no new implementation or WIP read, no product imports/DB/service/business tests.','write_boundary':'Only reviewer-owned private runtime','status':'FROZEN_WAITING_FOR_FINAL_SOURCE_SHA'}
oracle_sha=write('literal-oracle-plan.json',oracle)
# Independently literal inputs from the documented existing model; no product canonicalizer.
body=dict(release_id='11111111-1111-4111-8111-111111111111',expected_release_sha256='a'*64,goal='新企业独立材料准备',reviewer_id='reviewer-new',materials=[dict(slot='need_summary',text='全新诉求资料',source_kind='USER_STATEMENT',source_label='新企业明确输入'),dict(slot='material_outline',text='全新材料目录',source_kind='DOCUMENT_EXCERPT',source_label='新授权文本')],reason='明确使用已有已审模板')
def literal_fp(x):
 text=json.dumps(dict(action='CONSUME',**x),ensure_ascii=False,sort_keys=True,separators=(',',':'))
 return dict(normalized_body=x,canonical_flat_CONSUME=text,sha256=sha(text.encode()))
write('literal-consume-fingerprints.json',dict(source='Literal manual valid values and standard JSON sorting/UTF8; no product imports or new implementation.',omitted_catalog_pin=literal_fp(body),explicit_pin=literal_fp(dict(**body,expected_catalog_sha256='b'*64)),null_catalog_pin='REJECT',notes=['Input object keys sorted; array order preserved.','Use normalized Pydantic semantic values and exclude absent/null optional fields for legacy body; new explicit pin null must fail validation.','Hash is an input equality fingerprint, not authority, approval, or a signed receipt.']))
