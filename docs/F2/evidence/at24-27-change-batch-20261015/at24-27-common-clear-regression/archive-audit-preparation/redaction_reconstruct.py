"""Independent structured reconstruction; copied from prior own proven audit, never producer code."""
import json,re
import xml.etree.ElementTree as ET
FIXTURE=re.compile(r'^\s*\w+\s*=\s*[({].*Store object at 0x|^\s*(?:tokens|session_tokens)\s*=\s*\{')

def reconstruct(raw,suffix,values,fast_filter=None):
    counts={'exact_private_value':0,'fixture_repr_line':0}
    def text_filter(text):
        if fast_filter is not None:
            text,n=fast_filter.replace(text);counts['exact_private_value']+=n
        else:
            for value in values:
                n=text.count(value)
                if n:counts['exact_private_value']+=n;text=text.replace(value,'[REDACTED_SYNTHETIC_SESSION]')
        result=[]
        for line in text.splitlines(keepends=True):
            if FIXTURE.match(line):
                counts['fixture_repr_line']+=1;line='[REDACTED_SYNTHETIC_FIXTURE_REPR]'+ ('\n' if line.endswith('\n') else '')
            result.append(line)
        return ''.join(result)
    def walk(value):
        if isinstance(value,str):return text_filter(value)
        if isinstance(value,list):return [walk(x) for x in value]
        if isinstance(value,dict):return {k:walk(v) for k,v in value.items()}
        return value
    text=raw.decode('utf-8')
    if suffix=='.xml':
        doc=ET.fromstring(text)
        for n in doc.iter():
            if n.text:n.text=text_filter(n.text)
            if n.tail:n.tail=text_filter(n.tail)
            for key,value in list(n.attrib.items()):n.set(key,text_filter(value))
        export=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
    elif suffix=='.json':export=(json.dumps(walk(json.loads(text)),ensure_ascii=False,indent=2)+'\n').encode()
    elif suffix=='.jsonl':export=''.join(json.dumps(walk(json.loads(line)),ensure_ascii=False)+'\n' for line in text.splitlines() if line.strip()).encode()
    else:export=text_filter(text).encode()
    return (export if any(counts.values()) else raw),counts
