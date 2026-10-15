"""Known-private residual scan and non-self-referential public file manifest.

This directory alone is writable. No source/product/archive writes or imports of
the root exporter/verifier. Print hashes/counts only, never private pool values.
"""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,subprocess
import xml.etree.ElementTree as ET
from audit_archive_pairs import frozen,known_private,record
from fast_known_redaction import KnownTokenRedactor

R=Path('/workspace/ParkWeave');O=R/'.runtime/service-release-preflight-audit'
S='0de44714499ff3ead538dd8dc1436e783ab8f944'
INDEX='final-artifact-index.json'
def paths():return sorted(p for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!=INDEX)
def dump(name,data):(O/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==S
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R).strip()
    gate=json.loads((O/'final-gate.json').read_text());assert gate['status']=='PASS' and gate['source_sha']==S
    source=frozen(S);assert len(source)==12078
    values,sets=known_private();redactor=KnownTokenRedactor(values)
    files=[];syntax={'json':0,'xml':0,'python':0,'javascript':0};residuals=[]
    for p in paths():
        assert not p.is_symlink() and '.private.' not in p.name
        data=p.read_bytes();text=data.decode('utf-8')
        if redactor.has_residual(text):residuals.append(str(p.relative_to(O)))
        if p.suffix=='.json':json.loads(text);syntax['json']+=1
        elif p.suffix=='.xml':ET.fromstring(data);syntax['xml']+=1
        elif p.suffix=='.py':ast.parse(text);compile(text,str(p),'exec');syntax['python']+=1
        elif p.suffix=='.js':
            result=subprocess.run(['node','--check',str(p)],capture_output=True);assert result.returncode==0;syntax['javascript']+=1
        files.append({'path':str(p.relative_to(O)),**record(p)})
    assert not residuals
    dump('publicability.json',{'status':'PASS','source_sha':S,'utc':datetime.now(timezone.utc).isoformat(),'directory':str(O.relative_to(R)),'public_files_scanned_before_this_receipt':len(files),'known_private_values':len(values),'known_private_residuals':0,'designated_private_registry_files':len(sets),'private_values_or_sessions_disclosed':False,'private_files_or_cache_in_public_inventory':False,'structure_checks':syntax,'all_files_UTF8':True,'full_source_git_blob_check':True,'root_producer_verifier_imported':False,'shared_fast_redactor_provenance':'Same previously proved helper method; no algorithm diversity claimed','scan_scope':'Only new independent audit files, known synthetic session pools. Primary archive separately rebuilt and checked. Not a general credential discovery claim.','raw_or_primary_changed':False,'failure_receipts_included':['audit-first-stop-receipts.json','supplemental-self-check-receipt.json'],'not_included':['__pycache__','final-artifact-index.json (self-reference excluded)']})
    # Scan generated receipt too before indexing. All serializable data is public
    # counts/path/hash metadata; still require exact known-pool residual absence.
    assert not redactor.has_residual((O/'publicability.json').read_text())
    entries=[{'path':str(p.relative_to(O)),**record(p)} for p in paths()]
    assert len(entries)==len({x['path'] for x in entries})
    index={'status':'PASS_PUBLIC_ARTIFACTS_FROZEN_NO_MORE_REVIEWER_WRITES','source_sha':S,'utc':datetime.now(timezone.utc).isoformat(),'public_sibling':'docs/F2/evidence/service-release-preflight-audit-20261015','entry_count':len(entries),'indexed_bytes':sum(x['bytes'] for x in entries),'entries':entries,'excluded':['__pycache__','final-artifact-index.json itself'],'primary_archive_mutated':False,'raw_evidence_mutated':False,'source_or_Git_mutated':False,'reference':'final-gate.json','publicability':'publicability.json','first_stop_receipts':'audit-first-stop-receipts.json','bounded_auditor_correction_receipts':'supplemental-self-check-receipt.json'}
    dump(INDEX,index)
    for x in entries:assert record(O/x['path'])=={k:x[k] for k in ['bytes','sha256']}
    assert source==frozen(S)
    print(json.dumps({'status':index['status'],'source_sha':S,'entries':len(entries),'indexed_bytes':index['indexed_bytes'],'final_gate':record(O/'final-gate.json'),'index':record(O/INDEX),'known_private_residuals':0}))

if __name__=='__main__':main()
