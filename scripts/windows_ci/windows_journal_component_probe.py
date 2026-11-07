"""Windows file/journal component probe; no production lease or acceptance."""
from pathlib import Path
import os,json,uuid,hashlib
from scripts.windows_portable import fixed_journal as j
from scripts.windows_portable.directories import LeaseRefused
if os.name!='nt':raise RuntimeError('NATIVE_WINDOWS_REQUIRED')
root=Path('.cache/windows-desktop').resolve()/('journal-probe-'+uuid.uuid4().hex);assert root.is_relative_to(Path.cwd().resolve());root.mkdir()
(root/'lock').write_bytes(b'component-test');path=root/'journal'
class FileIO:
 journal_format=j.FixedFormat.INSTANCE_V2
 def __init__(self,fresh=False):
  self.fd=os.open(path,os.O_RDWR|os.O_BINARY|(os.O_CREAT|os.O_EXCL if fresh else 0),0o600)
  self.root_id=self.ident(root.stat());self.lock_id=self.ident((root/'lock').stat());self.file_id=self.identity()
 def ident(self,s):return [s.st_dev,s.st_ino]
 def identity(self):return self.ident(os.fstat(self.fd))
 def verify(self):assert self.identity()==self.file_id==self.ident(path.stat())
 def signature(self):
  s=os.fstat(self.fd);return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
 def length(self):return os.fstat(self.fd).st_size
 def read_at(self,offset,count):os.lseek(self.fd,offset,0);return os.read(self.fd,count)
 def write_at(self,offset,data):os.lseek(self.fd,offset,0);return os.write(self.fd,data)
 def flush_file(self):os.fsync(self.fd)
 def close(self):os.close(self.fd)
io=FileIO(True)
try:
 journal=j.FixedJournal(io,format=j.FixedFormat.INSTANCE_V2)
 record=dict(schema=j.schema(j.FixedFormat.INSTANCE_V2),root=io.root_id,lock=io.lock_id,journal=io.identity(),generation=1,sequence=2,phase='NEW',initialized=False,runtime='STOPPED',handoff='OWNED',instance_id=str(uuid.uuid4()))
 first=journal.write(j.encode(record),None)
 next_record={**record,'sequence':3,'phase':'UNKNOWN','runtime':'UNKNOWN'}
 expected=journal.write(j.encode(next_record),first);before_id=io.identity()
finally:io.close()
io=FileIO()
try:
 journal=j.FixedJournal(io,format=j.FixedFormat.INSTANCE_V2);same=journal.read()==expected and io.identity()==before_id
 io.write_at(100,b'X');io.flush_file()
 try:journal.read();corrupt=False
 except LeaseRefused:corrupt=True
finally:io.close()
assert same and corrupt,'FIXED_JOURNAL_COMPONENT_FAILED'
report={'scope':'WINDOWS_REAL_FILE_IO_WITH_ORIGINAL_FIXED_JOURNAL_COMPONENT','write_flush_readback':True,'same_file_close_reopen':same,'corruption_refused':corrupt,'production_native_lease':'NOT_TESTED','exclusive_open':'NOT_TESTED','process_interruption':'NOT_TESTED','power_loss':'NOT_TESTED','usable_product':False,'source_sha256':hashlib.sha256(Path('scripts/windows_portable/fixed_journal.py').read_bytes()).hexdigest()}
Path('docs/product-closure-20261105/windows-journal-component.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
