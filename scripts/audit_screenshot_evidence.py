"""Read-only local screenshot reference audit; never substitute newer image bytes."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEGACY=('.runtime/f2-before.png','.runtime/f2-confirmed.png','.runtime/f2-final.png')

def audit():
    refs={};hashes={}
    def add(path,doc):
        if path.startswith('.runtime/') and path.endswith('.png'):refs.setdefault(path,set()).add(doc)
    def walk(value,doc):
        if isinstance(value,dict):
            for k,v in value.items():
                add(k,doc)
                if k.startswith('.runtime/') and k.endswith('.png') and isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v):hashes.setdefault(k,set()).add(v)
                walk(v,doc)
        elif isinstance(value,list):
            for v in value:walk(v,doc)
        elif isinstance(value,str):
            for path in re.findall(r'\.runtime/[\w./-]+\.png',value):add(path,doc)
    for p in sorted((ROOT/'docs').rglob('*')):
        doc=str(p.relative_to(ROOT))
        if p.suffix=='.json':walk(json.loads(p.read_text()),doc)
        elif p.suffix=='.md':walk(p.read_text(),doc)
    for path in LEGACY:refs.setdefault(path,set()).add('historical preparation browser fixed output; see ScreenshotEvidence.md')
    rows=[]
    for path,documents in sorted(refs.items()):
        p=ROOT/path;expected=sorted(hashes.get(path,set()));actual=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        status='NOT_REPRODUCIBLE_LEGACY_OVERWRITTEN' if path in LEGACY else 'MISSING' if actual is None else 'NO_RECORDED_HASH' if not expected else 'HASH_MATCH' if expected==[actual] else 'HASH_MISMATCH'
        rows.append(dict(path=path,documents=sorted(documents),expected_sha256=expected,current_sha256=actual,status=status))
    return dict(scope='LOCAL_SCREENSHOT_REFERENCES_ONLY',rows=rows,legacy_previous_bytes='NOT_RECOVERABLE; current bytes never validate historical screenshots',counts={s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args();r=audit();a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r['counts']))
