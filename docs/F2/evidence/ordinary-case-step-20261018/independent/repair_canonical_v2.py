"""Packaging-only XML-safe v2 repair; no project imports or test execution."""
from pathlib import Path
import copy,hashlib,json,xml.etree.ElementTree as ET
base=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def encoded(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def create(rel,data):
    p=base/rel;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(data)
    return p
source='954825efb66d16f7e41087e1c108b45042732703'
v1list=load(base/'publication-files.json');assert len(v1list)==len(set(v1list))==115
raw_rel='frozen-954825ef-window1/results.xml'
bad_rel='public/frozen-954825ef-window1/results.xml'
new_rel='public-v2/frozen-954825ef-window1/results.xml'
bad_copy_rel='v1-packaging-failure/invalid-results-xml.shadow.txt'
immutable=set(v1list)|{raw_rel,bad_rel,'frozen-954825ef-window2/results.xml'}
before={p:sha(base/p) for p in immutable}
assert before[bad_rel]=='c2131167ea406e6a7b2c3637b0ab5ea9050312444a971b14e55ab02524824c13'
try:ET.parse(base/bad_rel)
except ET.ParseError as error:bad_error=str(error)
else:raise AssertionError('Expected preserved v1 malformed XML')
raw_tree=ET.parse(base/raw_rel);raw_root=raw_tree.getroot()
tokens=set()
for window in ('frozen-954825ef-window1','frozen-954825ef-window2'):
    tokens.update(load(base/window/'fixture-token-values.private.json'))
counts={'full_token_values':0,'captured_12_character_prefixes':0,'text_fields':0,'tail_fields':0,'attribute_fields':0}
def redact(value,field):
    if value is None:return None
    result=value
    for token in sorted(tokens,key=len,reverse=True):
        n=result.count(token)
        if n:result=result.replace(token,'[REDACTED_SYNTHETIC_FIXTURE_SESSION]');counts['full_token_values']+=n
        prefix=token[:12];n=result.count(prefix)
        if n:result=result.replace(prefix,'[REDACTED_SYNTHETIC_FIXTURE_SESSION_PREFIX]');counts['captured_12_character_prefixes']+=n
    if result!=value:counts[field]+=1
    return result
sanitized=copy.deepcopy(raw_root)
for node in sanitized.iter():
    node.text=redact(node.text,'text_fields');node.tail=redact(node.tail,'tail_fields')
    for key,value in tuple(node.attrib.items()):node.attrib[key]=redact(value,'attribute_fields')
serialized=ET.tostring(sanitized,encoding='utf-8',xml_declaration=True)
parsed_public=ET.fromstring(serialized)
def tree_value(node):return (node.tag,dict(node.attrib),node.text,node.tail,[tree_value(x) for x in node])
assert tree_value(parsed_public)==tree_value(sanitized),'XML text/tail/attribute escaping must round-trip exactly'
def junit(root):
    cases=list(root.iter('testcase'))
    return dict(testcases=len(cases),nodeids=[x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in cases],
        failures=sum(len(list(x.iter('failure'))) for x in cases),errors=sum(len(list(x.iter('error'))) for x in cases),
        skipped=sum(len(list(x.iter('skipped'))) for x in cases),suite_attributes=[dict(x.attrib) for x in root.iter('testsuite')],
        testcase_attributes=[dict(x.attrib) for x in cases])
assert junit(raw_root)==junit(parsed_public)
assert junit(raw_root)['testcases']==9 and junit(raw_root)['failures']==1 and junit(raw_root)['errors']==junit(raw_root)['skipped']==0
collection=load(base/'frozen-954825ef-window1/collection.json')
nodeids={x['nodeid'] for x in collection}
reports=[json.loads(s) for s in (base/'frozen-954825ef-window1/calls.jsonl').read_text().splitlines()]
phases={p:{o:sum(r['when']==p and r['outcome']==o for r in reports) for o in ('passed','failed','skipped')} for p in ('setup','call','teardown')}
assert set(junit(parsed_public)['nodeids'])==nodeids
assert phases=={'setup':{'passed':9,'failed':0,'skipped':0},'call':{'passed':8,'failed':1,'skipped':0},'teardown':{'passed':9,'failed':0,'skipped':0}}
xml_path=create(new_rel,serialized)
bad_copy=create(bad_copy_rel,(base/bad_rel).read_bytes());assert sha(bad_copy)==before[bad_rel]
validation=dict(schema=2,source_sha=source,scope='CANONICAL_PUBLICATION_XML_REPAIR_ONLY_NO_TESTS',
 raw=dict(path=raw_rel,sha256=before[raw_rel],parseable=True),
 malformed_v1=dict(path=bad_rel,sha256=before[bad_rel],parse_error=bad_error,complete_byte_copy=bad_copy_rel),
 canonical_v2=dict(path=new_rel,sha256=sha(xml_path),parseable=True),
 replacement_method='Parse private raw XML; replace captured synthetic session values/prefixes only in element.text, element.tail and attribute values; XML serializer escapes content. No arbitrary byte replacement, node tag changes or additional element insertion.',
 replacement_counts=counts,replacement_count=counts['full_token_values']+counts['captured_12_character_prefixes'],
 semantic_validation=dict(exact_sanitized_tree_roundtrip=True,original_testcase_suite_attributes_unchanged=True,original_nodeids_unchanged=True,
 original_failure_error_skip_counts_unchanged=True,original_failure_text_changed_only_for_captured_session_values=True,raw_and_public_JUnit=junit(raw_root),
 raw_collection_and_phase_nodeids_unchanged=True,original_phases=phases),
 immutable_v1_files={p:before[p] for p in sorted(immutable)},immutable_v1_hashes_unchanged=True,
 tests_run_for_repair=0,tracked_or_git_writes=False)
validation_rel='canonical-xml-repair-validation-v2.json';create(validation_rel,encoded(validation))
report=load(base/'independent-final-review.json')
report.update(raw_evidence_manifest='raw-evidence-manifest-v2.json',publication_list='publication-files-v2.json',raw_public_map='raw-public-redaction-map-v2.json')
report['publication_revision']=2
report['publication_correction']=dict(scope='PACKAGING_ONLY_NO_BUSINESS_RETEST',previous_report='independent-final-review.json',previous_report_sha256=before['independent-final-review.json'],
 cause='Reviewer v1 byte-level redaction inserted an unescaped angle-bracket placeholder into XML failure text and created malformed canonical JUnit; private raw remained valid. This was a reviewer packaging error, not a product/test execution failure.',
 correction='Only XML element text/tail/attribute content sanitized from private valid raw then serialized and parsed; original9 nodeids,8PASS/1 private-probe FAIL, phase counts and all original suite/testcase attributes preserved.',
 validation=validation_rel,current_canonical_JUnit=new_rel,malformed_v1_preserved_at=bad_rel,
 malformed_v1_public_historical_bytes=bad_copy_rel,
 old_metadata_policy='Original v1 report/list/map/manifest kept byte-for-byte as historical metadata. Only explicitly named v2 list/map/manifest/report describe the current publication; historical broken XML is supplied as labeled .txt bytes, not current JUnit.',
 effective_PASS_counts_unchanged=True,additional_tests_run=0)
create('independent-final-review-v2.json',encoded(report))
create('active-review-path-v2.txt',(str(base)+'\n').encode())
# Current list replaces only malformed current JUnit; preserves the complete v1
# broken bytes as labeled text plus all original metadata for audit.
publication=set(v1list)-{bad_rel}
publication.update([new_rel,bad_copy_rel,validation_rel,'repair_canonical_v2.py','independent-final-review-v2.json','active-review-path-v2.txt',
 'publication-files-v2.json','raw-public-redaction-map-v2.json','raw-evidence-manifest-v2.json'])
publication=sorted(publication)
old_map=load(base/'raw-public-redaction-map.json');rows=[]
for row in old_map['files']:
    row=dict(row)
    if row['raw']==raw_rel:
        assert row['public']==bad_rel
        row.update(public=new_rel,public_sha256=sha(xml_path),replacement_count=validation['replacement_count'],
            method='XML text/tail/attribute captured-value replacement with serializer escaping; see validation-v2')
    rows.append(row)
rows.append(dict(raw=bad_rel,public=bad_copy_rel,raw_sha256=before[bad_rel],public_sha256=sha(bad_copy),replacement_count=0,
 method='Malformed v1 canonical bytes preserved exactly as historical text, not active JUnit'))
represented={x['public'] for x in rows}
for rel in publication:
    if rel in represented or rel in ('publication-files-v2.json','raw-public-redaction-map-v2.json','raw-evidence-manifest-v2.json'):continue
    p=base/rel
    rows.append(dict(raw=rel,public=rel,raw_sha256=sha(p),public_sha256=sha(p),replacement_count=0,method='Original unchanged or newly generated token-free metadata'))
assert len({x['public'] for x in rows})==len(rows)
mapping=dict(schema=2,files=sorted(rows,key=lambda x:x['public']),replacements_total=sum(x['replacement_count'] for x in rows),
 captured_fixture_token_values=len(tokens),previous_map='raw-public-redaction-map.json',previous_map_sha256=before['raw-public-redaction-map.json'],
 policy='v2 is canonical. Non-XML v1 canonical shadows reused byte-for-byte without further redaction. Current first-window XML regenerated solely from valid private raw with XML-node content replacement. Every row records private raw/public relative paths, both SHA256 and replacement count. Original malformed shadow and v1 metadata remain immutable. Private inventories/config/mirror/PGdata excluded.')
create('raw-public-redaction-map-v2.json',encoded(mapping))
create('publication-files-v2.json',encoded(publication))
manifest=dict(schema=2,source_sha=source,publication_list='publication-files-v2.json',raw_public_map='raw-public-redaction-map-v2.json',
 self_hash_excluded_to_avoid_recursion=True,previous_manifest='raw-evidence-manifest.json',previous_manifest_sha256=before['raw-evidence-manifest.json'],
 excludes=['mirror','PGdata','private tokens','private config','*.private.json','token-bearing private raw replaced by canonical shadows','malformed v1 XML as active JUnit'],
 files=[dict(path=p,sha256=sha(base/p),bytes=(base/p).stat().st_size) for p in publication if p!='raw-evidence-manifest-v2.json'])
create('raw-evidence-manifest-v2.json',encoded(manifest))
assert {p:sha(base/p) for p in immutable}==before,'v1/raw bytes changed during repair'
for rel in publication:
    data=(base/rel).read_bytes()
    assert not any(t.encode() in data or t[:12].encode() in data for t in tokens),rel
    if rel.endswith('.xml'):ET.parse(base/rel)
for row in rows:
    assert sha(base/row['raw'])==row['raw_sha256'] and sha(base/row['public'])==row['public_sha256']
print(json.dumps(dict(report='independent-final-review-v2.json',report_sha256=sha(base/'independent-final-review-v2.json'),
 publication='publication-files-v2.json',publication_sha256=sha(base/'publication-files-v2.json'),publication_files=len(publication),
 map='raw-public-redaction-map-v2.json',map_sha256=sha(base/'raw-public-redaction-map-v2.json'),
 manifest='raw-evidence-manifest-v2.json',manifest_sha256=sha(base/'raw-evidence-manifest-v2.json'),
 canonical_XML=new_rel,canonical_XML_sha256=sha(xml_path),validation_sha256=sha(base/validation_rel),
 XML_replacements=validation['replacement_count'],all_selected_XML_parseable=True,v1_immutable=True,tests_run=0),sort_keys=True))
