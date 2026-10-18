from pathlib import Path
import hashlib,io,json,re,shutil,struct,zlib,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/ordinary-reuse-user-flow-20261018';dest=root/'docs/F2/evidence/ordinary-reuse-user-flow-20261018';manifest=json.loads((dest/'manifest.json').read_text());validation=json.loads((dest/'archive-validation.json').read_text());mirror=Path(json.loads((r/'frozen-freeze.json').read_text())['mirror']);initial=len(manifest['records'])
assert initial==230
extra=[]
for p in sorted((mirror/'docs/F2/evidence/material-objections').iterdir()):
 assert p.is_file() and p.suffix in ('.json','.png')
 target=r/'retained-mirror/frozen'/p.relative_to(mirror);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);extra.append(target)
assert len(extra)==4
extra.append(Path(__file__).resolve())
existing={entry['public_path'] for entry in manifest['records']}
verify=r/'verify-delivery.py'
if str(Path('runtime')/verify.relative_to(r)) not in existing:extra.append(verify)
completion=r/'archive-completion.json';completion.write_text(json.dumps(dict(initial_valid_pairs=initial,added_original_mirror_artifacts=4,reason='Original objections regression hardcodes docs evidence in this exact fresh test mirror. Preserve its three screenshots and JSON as well as its independent equivalents.',source_sha=manifest['source_sha'],tests_rerun=False,final_pairs=initial+len(extra)+1),indent=2)+'\n');extra.append(completion)
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
for p in extra:
 raw=p.read_bytes();rel=Path('runtime')/p.relative_to(r);assert str(rel) not in existing
 if p.suffix=='.json':
  json.loads(raw)
  assert not pattern.search(raw),'unexpected candidate in additional JSON; stop before export'
 public=dest/rel;public.parent.mkdir(parents=True,exist_ok=True);public.write_bytes(raw)
 manifest['records'].append(dict(raw_path=str(p),public_path=str(rel),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(raw).hexdigest(),raw_bytes=len(raw),public_bytes=len(raw),redactions=0))
 existing.add(str(rel));validation['counts'][p.suffix]=validation['counts'].get(p.suffix,0)+1
validation['pairs']=len(manifest['records']);validation['root_mirror_objection_artifacts_added']=4
for entry in manifest['records']:
 raw=Path(entry['raw_path']).read_bytes();public=(dest/entry['public_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==entry['raw_sha256'];assert hashlib.sha256(public).hexdigest()==entry['public_sha256'];assert len(raw)==entry['raw_bytes'] and len(public)==entry['public_bytes']
 if entry['public_path'].endswith('.png'):
  assert public[:8]==b'\x89PNG\r\n\x1a\n';at=8;chunks=[]
  while at<len(public):
   n=struct.unpack('>I',public[at:at+4])[0];kind=public[at+4:at+8];chunk=public[at+8:at+8+n];assert zlib.crc32(kind+chunk)&0xffffffff==struct.unpack('>I',public[at+8+n:at+12+n])[0]
   if kind==b'IDAT':chunks.append(chunk)
   at+=n+12
  assert at==len(public);zlib.decompress(b''.join(chunks))
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');(dest/'archive-validation.json').write_text(json.dumps(validation,indent=2)+'\n');print(json.dumps(validation))
