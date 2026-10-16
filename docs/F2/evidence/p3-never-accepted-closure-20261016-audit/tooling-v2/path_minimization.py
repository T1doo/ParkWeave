"""Independent public representation of synthetic artifact basenames.

No producer imports or secret decoding. The original full basename hashes to a
new label; actual paths remain private runtime-only lookups in the auditor.
"""
import re,hashlib,json,xml.etree.ElementTree as ET
COMPONENT=re.compile(r'controlled-owner-history-request_key-[a-f0-9]{32}\.json')
RESIDUAL=re.compile(r'key-[a-f0-9]{32}')
def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def public_name(text):
 return COMPONENT.sub(lambda found:'controlled-owner-history-request-id-sha256-'+digest(found.group(0))+'.json',text)
def transform_paths(raw,suffix):
 count=0
 def scalar(text):
  nonlocal count
  count+=len(COMPONENT.findall(text))
  return public_name(text)
 def visit(value):
  if type(value) is str:return scalar(value)
  if type(value) is list:return [visit(item) for item in value]
  if type(value) is dict:
   result={}
   for key,item in value.items():
    alias=scalar(key)
    if alias in result:raise ValueError('public JSON key alias collision')
    result[alias]=visit(item)
   return result
  return value
 if suffix=='.json':output=(json.dumps(visit(json.loads(raw)),ensure_ascii=True,indent=2)+'\n').encode()
 elif suffix=='.jsonl':output=''.join(json.dumps(visit(json.loads(line)),ensure_ascii=True)+'\n' for line in raw.decode().splitlines() if line.strip()).encode()
 elif suffix=='.xml':
  tree=ET.fromstring(raw)
  for node in tree.iter():
   if node.text:node.text=scalar(node.text)
   if node.tail:node.tail=scalar(node.tail)
   for key,value in list(node.attrib.items()):node.set(key,scalar(value))
  output=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
 else:output=scalar(raw.decode()).encode()
 return (output if count else raw),count
