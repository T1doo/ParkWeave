"""Independent offline test inventory and owned schema-2 byte fixtures."""
import ast
import hashlib
import json
from pathlib import Path
from test_windows_ci_preparation import ROOT,module


def catalog_ids(root=ROOT):
    result=[]
    for path in sorted((root/'tests').glob('test_*.py')):
        prefix=path.relative_to(root).as_posix()+'::'
        for node in ast.parse(path.read_bytes()).body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):result.append(prefix+node.name)
            elif isinstance(node,ast.ClassDef) and node.name and node.name[0].isalpha() and node.name.isascii():
                result.extend(prefix+node.name+'::'+m.name for m in node.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and m.name.startswith('test_'))
    return sorted(result)


def owned_catalog(tmp_path,monkeypatch,sources=None):
    cv=module('diagnostic_catalog').cv
    sources=sources or {'tests/test_a.py':'def test_alpha(): pass\n','tests/test_b.py':'class Demo:\n def test_beta(self): pass\n'}
    root=tmp_path/'repo';(root/'tests').mkdir(parents=True)
    for name,text in sources.items():(root/name).write_text(text,encoding='utf-8')
    mapping={name:('MATERIAL' if name.endswith('test_b.py') else 'FOUNDATION_HOST') for name in sources}
    monkeypatch.setattr(cv,'FILE_DOMAINS',mapping)
    (root/cv.CATALOG).parent.mkdir(parents=True)
    raw,payloads,_=cv.generate(root);index=cv.decode(raw)
    install(root,cv,index,payloads)
    return root,cv


def install(root,cv,index,payloads):
    index['ids']=sum(x['ids'] for x in index['domains']);index['files']=sum(x['files'] for x in index['domains'])
    for row in index['domains']:
        raw=payloads[row['domain']];row['bytes']=len(raw);row['sha256']=hashlib.sha256(raw).hexdigest()
    index['generation']=cv.generation(index)
    folder=root/cv.DIRECTORY/index['generation'];folder.mkdir(parents=True,exist_ok=True)
    for domain,raw in payloads.items():(folder/(domain+'.jsonl')).write_bytes(raw)
    (root/cv.CATALOG).write_bytes(cv.encode(index))


def mutate(root,cv,domain,change,*,id_delta=0):
    index=cv.decode((root/cv.CATALOG).read_bytes())
    folder=root/cv.DIRECTORY/index['generation']
    payloads={d:(folder/(d+'.jsonl')).read_bytes() for d in cv.DOMAINS}
    payloads[domain]=change(payloads[domain])
    next(row for row in index['domains'] if row['domain']==domain)['ids']+=id_delta
    install(root,cv,index,payloads)
    return index,payloads
