"""Independent fixed public-evidence transform, without producer imports."""
import json,re,xml.etree.ElementTree as ET
PLACEHOLDER='[REDACTED_SYNTHETIC_SESSION]'
REPR='[REDACTED_SYNTHETIC_FIXTURE_REPR]'
WORD=re.compile(r'[A-Za-z0-9_-]{43,}')
URL43=re.compile(r'[A-Za-z0-9_-]{43}\Z')


class Transform:
    def __init__(self,values):
        self.values=sorted(set(values),key=lambda x:(-len(x),x))
        self.pool=set(self.values)
        self.regular=all(URL43.fullmatch(v) for v in self.values)

    def exact(self,text):
        if self.regular:
            spans=[]
            for word in WORD.finditer(text):
                value=word.group()
                for index in range(len(value)-42):
                    if value[index:index+43] in self.pool:spans.append((word.start()+index,word.start()+index+43))
            if not spans:return text,0
            if all(a[1]<=b[0] for a,b in zip(spans,spans[1:])):
                cursor=0;chunks=[]
                for start,end in spans:chunks.extend((text[cursor:start],PLACEHOLDER));cursor=end
                chunks.append(text[cursor:])
                return ''.join(chunks),len(spans)
        count=0
        for value in self.values:
            count+=text.count(value)
            text=text.replace(value,PLACEHOLDER)
        return text,count

    def residual(self,text):
        if self.regular:
            return any(word[index:index+43] in self.pool for match in WORD.finditer(text) for word in [match.group()] for index in range(len(word)-42))
        return any(value in text for value in self.values)

    def export(self,raw,suffix):
        counts=dict(exact_private_value=0,fixture_repr_line=0)
        def redact(text):
            text,n=self.exact(text);counts['exact_private_value']+=n
            lines=[]
            for line in text.splitlines(keepends=True):
                fixture=re.match(r'^\s*\w+\s*=\s*[({].*Store object at 0x',line)
                tokens=re.match(r'^\s*(?:tokens|session_tokens)\s*=\s*\{',line)
                if suffix not in ('.py','.js') and (fixture or tokens):
                    counts['fixture_repr_line']+=1
                    line=REPR+('\n' if line.endswith('\n') else '')
                lines.append(line)
            return ''.join(lines)
        def walk(x):
            if isinstance(x,str):return redact(x)
            if isinstance(x,list):return [walk(v) for v in x]
            if isinstance(x,dict):return {k:walk(v) for k,v in x.items()}
            return x
        text=raw.decode('utf-8')
        if suffix=='.xml':
            doc=ET.fromstring(text)
            for node in doc.iter():
                if node.text:node.text=redact(node.text)
                if node.tail:node.tail=redact(node.tail)
                for key,value in list(node.attrib.items()):node.set(key,redact(value))
            result=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
        elif suffix=='.json':result=(json.dumps(walk(json.loads(text)),ensure_ascii=True,indent=2)+'\n').encode()
        elif suffix=='.jsonl':result=''.join(json.dumps(walk(json.loads(line)),ensure_ascii=True)+'\n' for line in text.splitlines() if line.strip()).encode()
        else:result=redact(text).encode()
        if not any(counts.values()):result=raw
        assert not self.residual(result.decode('utf-8')),'known private residual'
        return result,counts


def selftest():
    token='A'*43
    transform=Transform([token])
    assert transform.exact('prefix'+token+'suffix')==('prefix'+PLACEHOLDER+'suffix',1)
    for suffix,raw in [('.json',b'{"escaped":"\\ud800","token":"'+token.encode()+b'"}'),('.jsonl',b'{"token":"'+token.encode()+b'"}\n'),('.xml',b'<root token="'+token.encode()+b'"/>')]:
        output,counts=transform.export(raw,suffix)
        assert counts==dict(exact_private_value=1,fixture_repr_line=0)
        assert PLACEHOLDER.encode() in output
    unchanged=b'{"escaped":"\\ud800"}'
    assert transform.export(unchanged,'.json')==(unchanged,dict(exact_private_value=0,fixture_repr_line=0))
    assert transform.export(b"tokens = {'one': 'truncated'}\n",'.log')==(REPR.encode()+b'\n',dict(exact_private_value=0,fixture_repr_line=1))
