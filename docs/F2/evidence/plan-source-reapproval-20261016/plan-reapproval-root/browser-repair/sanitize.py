from pathlib import Path
import sys,importlib.util,json,xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
root=Path('/workspace/ParkWeave');parent=root/'.runtime/plan-reapproval-root';sys.path.insert(0,str(parent))
spec=importlib.util.spec_from_file_location('repair_exporter_read_only',parent/'export_archive.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
b=parent/'browser-repair'/sys.argv[1];values=module.private_values();rows=[]
for name in ('junit.xml','stdout.log'):
 data,counts=module.export_bytes((b/name).read_bytes(),Path(name).suffix,values)
 (b/('sanitized-'+name)).write_bytes(data)
 if name.endswith('.xml'):
  for case in ET.fromstring(data).iter('testcase'):
   failure=case.find('failure')
   if failure is not None:rows.append(dict(name=case.get('name'),message=failure.get('message'),trace=failure.text))
(b/'sanitized-failures.json').write_text(json.dumps(rows,indent=2)+'\n')
for row in rows:print(json.dumps(dict(name=row['name'],message=row['message'][:500]),ensure_ascii=True))
