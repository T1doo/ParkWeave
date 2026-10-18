from pathlib import Path
import ast,io,hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as E,zlib,struct
root=Path('/workspace/ParkWeave');r=root/'.runtime/ordinary-reuse-user-flow-20261018';dest=root/'docs/F2/evidence/ordinary-reuse-user-flow-20261018';assert not dest.exists()
a=json.loads((r/'accepted-tests.json').read_text());ind=json.loads((r/'independent-final-review.json').read_text());assert ind['source_sha']==a['source_sha']
for call in r.glob('*-invocation.json'):
 d=json.loads(call.read_text());base=Path(d['basetemp']);label=call.name.removesuffix('-invocation.json')
 if not base.is_dir():continue
 for p in sorted(base.rglob('*')):
  if not p.is_file() or p.is_symlink() or p.suffix not in ('.json','.jsonl','.xml','.log','.png','.stdout','.stderr','.txt'):continue
  rel=p.relative_to(base)
  if any(x=='data' or x.startswith('parkweave-pg') for x in rel.parts) or 'private' in p.name:continue
  target=r/'retained-tmp'/label/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
# Mirror source is reproducible from Git, not copied into the public evidence bundle.
def reject_constant(value):raise ValueError('non-JSON constant '+value)
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate key '+k)
  d[k]=v
 return d
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root);known=set(pattern.findall(tracked));identifiers=[]
for name in tracked.decode().split('\0'):
 if name.endswith('.py') and name.startswith(('src/','tests/','scripts/')):
  for node in ast.walk(ast.parse((root/name).read_text())):
   if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and pattern.fullmatch(node.name.encode()):known.add(node.name.encode());identifiers.append(node.name)
records=[];exclusions=[]
for p in sorted(r.rglob('*')):
 if not p.is_file() or p.is_symlink():continue
 rel=p.relative_to(r)
 if 'pre-result-drafts' in rel.parts:
  exclusions.append(dict(path=str(rel),reason='unexecuted pre-result draft, not execution evidence; raw retained locally'));continue
 if any('private' in part.lower() or 'tokens' in part.lower() for part in rel.parts) or p.name in ('web-before.html','diagnostic-frontier.js','process-initial.txt'):
  exclusions.append(dict(path=str(rel),reason='private fixture/bootstrap or baseline reconstructible from recorded Git SHA; raw retained locally'));continue
 if p.suffix not in ('.json','.jsonl','.xml','.log','.png','.stdout','.stderr','.py','.js','.txt','.md'):continue
 public=dest/'runtime'/rel;public.parent.mkdir(parents=True,exist_ok=True);raw=p.read_bytes();count=[0]
 def redact_bytes(data):
  def sub(m):
   if m.group() in known:return m.group()
   count[0]+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
  return pattern.sub(sub,data)
 def scrub(value):
  if isinstance(value,str):return redact_bytes(value.encode()).decode()
  if isinstance(value,list):return [scrub(x) for x in value]
  if isinstance(value,dict):return {k:scrub(v) for k,v in value.items()}
  return value
 if p.suffix in ('.py','.js','.png'):data=raw
 elif p.suffix=='.json':
  value=scrub(json.loads(raw,object_pairs_hook=unique,parse_constant=reject_constant));data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode() if count[0] else raw
 elif p.suffix=='.jsonl':
  changed={}
  for index,line in enumerate(io.BytesIO(raw)):
   previous=count[0];value=scrub(json.loads(line,object_pairs_hook=unique,parse_constant=reject_constant))
   if count[0]!=previous:changed[index]=(json.dumps(value,ensure_ascii=False)+'\n').encode()
  if changed:
   output=io.BytesIO()
   for index,line in enumerate(io.BytesIO(raw)):output.write(changed.get(index,line))
   data=output.getvalue()
  else:data=raw
 elif p.suffix=='.xml':
  tree=E.fromstring(raw)
  for node in tree.iter():
   if node.text:node.text=redact_bytes(node.text.encode()).decode()
   if node.tail:node.tail=redact_bytes(node.tail.encode()).decode()
   if 'message' in node.attrib:node.set('message',redact_bytes(node.get('message').encode()).decode())
  data=E.tostring(tree,encoding='utf-8',xml_declaration=True) if count[0] else raw
 else:data=redact_bytes(raw)
 public.write_bytes(data);records.append(dict(raw_path=str(p),public_path=str(Path('runtime')/rel),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=count[0]))
manifest=dict(source_sha=a['source_sha'],records=records,redactions=sum(x['redactions'] for x in records),source_proven_identifiers=sorted(set(identifiers)),exclusions=exclusions,redaction='43-character URL-safe synthetic temporary session candidates; source-proven paths/AST identifiers excluded; JSON keys and JUnit test identifiers unchanged',limits=['Development dev1 navigation failure, dev2 actual confirmation-button failure, dev3 modified WIP pass are separate. Frozen43 and independent4 overlap; no full project suite or formal AT claim.','Only owned explicit SYNTHETIC PG/ordinary API/Chromium, no real source or authority','No Windows/formal AT/production protected installation/model calls'])
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
counts={};xml_ids=0
for entry in records:
 raw=Path(entry['raw_path']).read_bytes();p=dest/entry['public_path'];data=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==entry['raw_sha256'] and hashlib.sha256(data).hexdigest()==entry['public_sha256'];assert len(raw)==entry['raw_bytes'] and len(data)==entry['public_bytes'];ext=p.suffix;counts[ext]=counts.get(ext,0)+1
 if ext=='.json':json.loads(data,object_pairs_hook=unique,parse_constant=reject_constant)
 elif ext=='.jsonl':
  for line in io.BytesIO(data):json.loads(line,object_pairs_hook=unique,parse_constant=reject_constant)
 elif ext=='.xml':
  original=E.fromstring(raw);public=E.fromstring(data);get_ids=lambda tree:[(c.get('classname'),c.get('name')) for c in tree.findall('.//testcase')];assert get_ids(original)==get_ids(public);xml_ids+=len(get_ids(original))
 elif ext=='.png':
  assert data[:8]==b'\x89PNG\r\n\x1a\n';at=8;compressed=b''
  while at<len(data):
   length=struct.unpack('>I',data[at:at+4])[0];kind=data[at+4:at+8];chunk=data[at+8:at+8+length];crc=struct.unpack('>I',data[at+8+length:at+12+length])[0];assert zlib.crc32(kind+chunk)&0xffffffff==crc
   if kind==b'IDAT':compressed+=chunk
   at+=12+length
  assert at==len(data);zlib.decompress(compressed)
validation=dict(source_sha=a['source_sha'],pairs=len(records),all_raw_public_hashes_and_lengths_valid=True,strict_JSON_JSONL_XML=True,JUnit_identifiers_unchanged=xml_ids,PNG_CRC_and_decompression=True,counts=counts,redactions=manifest['redactions'],private_bootstraps_and_PG_data_exported=False)
(dest/'archive-validation.json').write_text(json.dumps(validation,indent=2)+'\n');print(json.dumps(validation))
