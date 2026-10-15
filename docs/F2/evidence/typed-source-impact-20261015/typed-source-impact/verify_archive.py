from pathlib import Path
import hashlib,importlib.util,json,xml.etree.ElementTree as ET
ROOT=Path.cwd();OUT=ROOT/'docs/F2/evidence/typed-source-impact-20261015'
spec=importlib.util.spec_from_file_location('exporter',ROOT/'.runtime/typed-source-impact/export_archive.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
index=json.loads((OUT/'index.json').read_text());values=m.private_values();seen=set();counts={'xml':0,'json':0,'jsonl':0,'python':0}
for entry in index['entries']:
    source=ROOT/entry['raw_path'];target=ROOT/entry['export_path']
    assert target.is_relative_to(OUT) and target not in seen
    seen.add(target);raw=source.read_bytes();export=target.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['raw_sha256'] and len(raw)==entry['raw_bytes']
    assert hashlib.sha256(export).hexdigest()==entry['export_sha256'] and len(export)==entry['export_bytes']
    expected,redactions=m.export_bytes(raw,source.suffix,values)
    assert export==expected and redactions==entry['redactions']
    assert not any(v.encode() in export for v in values)
    if target.suffix=='.xml':
        a=ET.fromstring(raw);b=ET.fromstring(export)
        assert [(n.tag,sorted(n.attrib)) for n in a.iter()]==[(n.tag,sorted(n.attrib)) for n in b.iter()]
        assert len(list(a.iter('testcase')))==len(list(b.iter('testcase')))
        counts['xml']+=1
    elif target.suffix=='.json':json.loads(export);counts['json']+=1
    elif target.suffix=='.jsonl':
        for line in export.splitlines():json.loads(line)
        counts['jsonl']+=1
    elif target.suffix=='.py':compile(export,str(target),'exec');assert raw==export;counts['python']+=1
    elif target.suffix=='.js':assert raw==export
required=['typed-source-impact/freeze.json', 'typed-source-impact/ui-first.log', 'typed-source-impact/ui-first.xml', 'typed-source-impact/ui-second.xml', 'typed-source-impact/root-1-v1.json', 'typed-source-impact/root-1-v1.xml', 'typed-source-impact/root-2-v1.json', 'typed-source-impact/root-2-v1.xml', 'typed-source-impact/final-coverage.json', 'typed-source-impact-backend/scalar-red.log', 'typed-source-impact-backend/scalar-red.xml', 'typed-source-impact-backend/final-focused.xml', 'typed-source-impact-independent/development2.xml', 'typed-source-impact-independent/localcheck-repro.xml', 'typed-source-impact-independent/localcheck-green.xml']
assert all(OUT/p in seen for p in required)
result=dict(status='PASS',source_sha=index['source_sha'],indexed_files=len(seen),raw_hashes_sizes_unchanged=True,export_hashes_sizes_exact=True,deterministic_redaction=True,known_synthetic_session_residuals=0,structured_checks=counts,required_final_and_failed_evidence_present=True,redaction_counts={key:sum(e['redactions'][key] for e in index['entries']) for key in ['exact_private_value','fixture_repr_line']},shared_snapshot_note='Task windows retain their own actual freeze/source scope; WIP developmental windows are not relabeled frozen. Private synthetic redaction sets are excluded.')
(ROOT/'.runtime/typed-source-impact/archive-audit.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
