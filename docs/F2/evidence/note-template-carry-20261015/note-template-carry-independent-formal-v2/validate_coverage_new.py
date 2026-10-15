"""Read-only scoped mapping of fixed design IDs to final JUnit evidence."""
from pathlib import Path
from collections import Counter
import hashlib,json,sys,xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
NAME,SOURCE=sys.argv[1:3]
result=json.loads((BASE/(NAME+'-validation.json')).read_text());assert result['source_sha']==SOURCE and result['counts']==dict(PASS=28,FAIL=0,ERROR=0,SKIP=0)
coverage=json.loads((BASE/'coverage-new-design.json').read_text());assert coverage['source_sha']==SOURCE
path=ROOT/coverage['design_path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==coverage['design_sha256']
design=json.loads(path.read_text());assert len(coverage['mappings'])==22 and {x['id'] for x in coverage['mappings']}=={x['id'] for x in design['scenarios']}
passed=set()
for c in ET.parse(BASE/(NAME+'.xml')).iter('testcase'):
 assert all(c.find(x) is None for x in ('failure','error','skipped'))
 p=c.attrib['classname'].split('.');i=next(i for i,s in enumerate(p) if s.startswith('test_'));passed.add('tests/'+p[i]+'.py::'+'::'.join(p[i+1:]+[c.attrib['name']]))
for row in coverage['mappings']:
 assert set(row['test_nodes'])<=passed
 row['status']='PASS_ONLY_FOR_DESCRIBED_SCOPE' if row['test_nodes'] else 'NOT_RUN_IN_THIS_MODULE'
coverage['coverage_kind_counts']=dict(Counter(x['coverage_kind'] for x in coverage['mappings']));coverage['validator_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(BASE/(NAME+'-design-coverage.json')).write_text(json.dumps(coverage,indent=2)+'\n')
print(json.dumps(dict(source_sha=SOURCE,designs=22,counts=coverage['coverage_kind_counts'],design_is_not_execution_denominator=True)))
