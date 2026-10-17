from pathlib import Path
import hashlib,json,struct,zlib,xml.etree.ElementTree as E
r=Path('/workspace/ParkWeave/.runtime/demo-original-page-intake');d=Path('/workspace/ParkWeave/docs/F2/evidence/demo-original-page-intake-20261017');m=json.loads((d/'manifest.json').read_text());counts={};redactions=0
for record in m['records']:
 raw=Path(record['raw_path']).read_bytes();p=d/record['public_path'];public=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==record['raw_sha256'];assert hashlib.sha256(public).hexdigest()==record['public_sha256'];redactions+=record['redactions'];counts[p.suffix]=counts.get(p.suffix,0)+1
 if p.suffix=='.json':json.loads(public)
 if p.suffix=='.xml':E.fromstring(public)
 if p.suffix=='.png':
  assert public[:8]==b'\x89PNG\r\n\x1a\n';offset=8;data=b'';last=None
  while offset<len(public):
   size=struct.unpack('>I',public[offset:offset+4])[0];kind=public[offset+4:offset+8];chunk=public[offset+8:offset+8+size];crc=struct.unpack('>I',public[offset+8+size:offset+12+size])[0];assert zlib.crc32(kind+chunk)&0xffffffff==crc
   if kind==b'IHDR':width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',chunk);assert width>0 and height>0 and depth==8 and color in (2,6) and interlace==0
   if kind==b'IDAT':data+=chunk
   offset+=12+size;last=kind
  assert offset==len(public) and last==b'IEND';pixels=zlib.decompress(data);assert len(pixels)==height*(1+width*(3 if color==2 else 4))
assert redactions==m['redactions']==3
result=dict(pairs=len(m['records']),counts=counts,redactions=redactions,raw_and_public_hashes_verified=True,structured_files_valid=True,PNG='signature, all chunk CRC, dimensions, zlib stream and pixel byte count checked; no image editing',notes='First conservative export retained privately; stable path/ref identifiers exempted. Earlier pytest-owned deleted tmp not represented as raw files.')
(r/('archive-validation-'+str(len(m['records']))+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
