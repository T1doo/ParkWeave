from pathlib import Path
import subprocess,hashlib,threading,json
root=Path('/workspace/ParkWeave');raw=root/'.runtime/case-step-assignment-20261018';base='a31cb8b551a8f335387e83174e94c789dbb2c165'
def save(name,v):(raw/name).write_text(json.dumps(v,indent=2)+'\n')
entries=[l.split('\t',1) for l in subprocess.check_output(['git','ls-tree','-r',base,'docs/F2/evidence'],cwd=root,text=True).splitlines()]
reader=subprocess.Popen(['git','cat-file','--batch'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def feed():reader.stdin.write(('\n'.join(e.split()[2] for e,p in entries)+'\n').encode());reader.stdin.close()
feeder=threading.Thread(target=feed);feeder.start();inherited={}
for entry,path in entries:
 oid,kind,length=reader.stdout.readline().split();remaining=int(length);digest=hashlib.sha256()
 while remaining:
  chunk=reader.stdout.read(min(remaining,1024*1024));assert chunk;digest.update(chunk);remaining-=len(chunk)
 assert reader.stdout.read(1)==b'\n'
 with (root/path).open('rb') as current:actual=hashlib.file_digest(current,'sha256').hexdigest()
 assert oid.decode()==entry.split()[2] and kind==b'blob' and digest.hexdigest()==actual
 inherited[path]=actual
feeder.join();assert reader.wait()==0;save('inherited-evidence-before.json',dict(base_sha=base,count=len(inherited),sha256=inherited))
print(json.dumps(dict(inherited_evidence=len(inherited),all_current_sha256_equal_base=True)))
