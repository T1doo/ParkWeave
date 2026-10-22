from pathlib import Path
from hashlib import sha256
import csv,io,json,subprocess,zipfile
from scripts import installed_wheel_support as installed
out=Path(__file__).parent
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head=='e90e16dd0f2151efde4e7be6de6ebe98ffea43b8'
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
wheel=installed.build(out/'build')
def metadata(path,source=head):
 value=dict(package_source_sha=source,file=path.name,bytes=path.stat().st_size,sha256=sha256(path.read_bytes()).hexdigest(),build='Existing setuptools80.9,no-index,no-deps,no-build-isolation',dependency_downloads_during_wheel_build_and_install=0)
 path.with_name('package-source.json').write_text(json.dumps(value,indent=2)+'\n')
metadata(wheel);baseline=installed.package_manifest(wheel)
rows=[]
for omit in ('parkweave/park_demo_web.html','parkweave/migration-033.sql'):
 target=out/('red-'+Path(omit).stem);target.mkdir();bad=target/wheel.name
 with zipfile.ZipFile(wheel) as original,zipfile.ZipFile(bad,'w') as changed:
  for item in original.infolist():
   if item.filename==omit:continue
   data=original.read(item)
   if item.filename.endswith('.dist-info/RECORD'):
    lines=[r for r in csv.reader(io.StringIO(data.decode())) if r[0]!=omit]
    text=io.StringIO(newline='');csv.writer(text).writerows(lines);data=text.getvalue().encode()
   changed.writestr(item,data)
 metadata(bad)
 result=installed.package_manifest(bad)
 rows.append(dict(fault='OMIT_DECLARED_RESOURCE',omitted=omit,baseline_gate='ACCEPTED',files=len(result)))
target=out/'red-fabricated-source';target.mkdir();bad=target/wheel.name;bad.write_bytes(wheel.read_bytes());metadata(bad,'0'*40)
result=installed.package_manifest(bad);rows.append(dict(fault='NONEXISTENT_SOURCE_COMMIT',claimed_source='0'*40,baseline_gate='ACCEPTED',files=len(result)))
report=dict(head=head,browser=False,business=False,dependency_downloads=0,wheel=dict(file=wheel.name,bytes=wheel.stat().st_size,SHA256=sha256(wheel.read_bytes()).hexdigest(),package_files=len(baseline)),red_cases=rows,helper_sha256=sha256(Path(installed.__file__).read_bytes()).hexdigest())
(out/'red.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
