"""Bounded AMD64 import/export/version readers; never load a PE image."""
import struct
from .payload import PayloadRefused,pe_imports
from pathlib import PurePosixPath

CRT_DLLS=frozenset(('vcruntime140.dll','msvcp140.dll'))


def need(ok):
    if not ok:raise PayloadRefused('SYSTEM_CRT_PE_COMPATIBILITY_REFUSED')


class Image:
    def __init__(self,raw):
        need(type(raw) is bytes and 64<=len(raw)<=128*1024*1024)
        self.raw=raw;need(raw[:2]==b'MZ')
        pe=self.u(0x3c,'I');need(raw[pe:pe+4]==b'PE\0\0' and self.u(pe+4,'H')==0x8664)
        count=self.u(pe+6,'H');size=self.u(pe+20,'H');opt=pe+24
        need(0<count<=96 and size>=240 and self.u(opt,'H')==0x20b and self.u(opt+108,'I')>=14)
        self.opt=opt;self.sections=[];self.memory_sections=[]
        self.image_size=self.u(opt+56,'I')
        for i in range(count):
            s=opt+size+40*i
            length,offset=self.u(s+16,'I'),self.u(s+20,'I')
            need(offset+length<=len(raw))
            address=self.u(s+12,'I')
            self.sections.append((address,length,offset))
            # File metadata must remain backed by bytes. An exported data
            # address may instead name the loader's zero-filled section tail.
            self.memory_sections.append((address,max(self.u(s+8,'I'),length)))

    def u(self,p,fmt):
        n=struct.calcsize('<'+fmt);need(0<=p<=len(self.raw)-n)
        return struct.unpack_from('<'+fmt,self.raw,p)[0]

    def offset(self,rva,length=1):
        need(type(rva) is int and rva>=0 and length>=0)
        matches=[o+rva-v for v,n,o in self.sections if v<=rva and rva+length<=v+n]
        need(len(matches)==1);return matches[0]

    def text(self,rva):
        p=self.offset(rva);end=self.raw.find(b'\0',p,min(len(self.raw),p+1025))
        need(end>p and all(32<=c<127 for c in self.raw[p:end]))
        self.offset(rva,end-p+1)
        return self.raw[p:end].decode('ascii')

    def memory_target(self,rva):
        """Validate a direct export RVA; never invent a file offset for BSS."""
        need(type(rva) is int and 0<rva<self.image_size)
        need(all(address+length<=self.image_size for address,length in self.memory_sections))
        matches=[address for address,length in self.memory_sections if address<=rva<address+length]
        need(len(matches)==1)

    def directory(self,index):
        p=self.opt+112+8*index;return self.u(p,'I'),self.u(p+4,'I')

    def crt_imports(self):
        result={}
        for index,stride in ((1,20),(13,32)):
            rva,size=self.directory(index)
            if not rva:need(size==0);continue
            need(stride<=size<=1024*stride);done=False
            for i in range(size//stride):
                p=self.offset(rva+i*stride,stride)
                if not any(self.raw[p:p+stride]):done=True;break
                if index==13:
                    need(self.u(p,'I')==1)  # RVA form only; no legacy VA guessing.
                    name=self.u(p+4,'I');thunk=self.u(p+16,'I')
                else:name=self.u(p+12,'I');thunk=self.u(p,'I')
                dll=self.text(name).lower()
                if dll not in CRT_DLLS:continue
                need(thunk>0);symbols=result.setdefault(dll,set());terminated=False
                for n in range(8192):
                    value=self.u(self.offset(thunk+n*8,8),'Q')
                    if not value:terminated=True;break
                    if value&(1<<63):need(value&~((1<<63)|65535)==0);symbol='#'+str(value&65535)
                    else:symbol=self.text(value+2);need(not symbol.startswith('#'))
                    symbols.add(symbol)
                need(terminated)
            need(done)
        return result

    def exports(self):
        rva,size=self.directory(0);need(rva>0 and 40<=size<=16*1024*1024)
        p=self.offset(rva,40);base=self.u(p+16,'I');count=self.u(p+20,'I');names=self.u(p+24,'I')
        need(0<count<=65536 and names<=count)
        functions=self.u(p+28,'I');strings=self.u(p+32,'I');ordinals=self.u(p+36,'I')
        result={}
        for i in range(count):
            target=self.u(self.offset(functions+i*4,4),'I')
            if target:
                forwarded=rva<=target<rva+size
                if forwarded:self.text(target)
                else:self.memory_target(target)
                result['#'+str(base+i)]=forwarded
        for i in range(names):
            name=self.text(self.u(self.offset(strings+i*4,4),'I'))
            ordinal=self.u(self.offset(ordinals+i*2,2),'H');need(ordinal<count and name not in result)
            key='#'+str(base+ordinal);need(key in result);result[name]=result[key]
        return result

    def version(self):
        rva,size=self.directory(2);need(rva>0 and 16<=size<=16*1024*1024)
        versions=[];visited=set()
        def walk(relative,depth):
            need(depth<=3 and relative not in visited and len(visited)<256)
            visited.add(relative);p=self.offset(rva+relative,16)
            count=self.u(p+12,'H')+self.u(p+14,'H');need(count<=256 and relative+16+count*8<=size)
            for i in range(count):
                name=self.u(p+16+8*i,'I');child=self.u(p+20+8*i,'I')
                if depth==0 and name!=16:continue  # RT_VERSION only.
                if child&0x80000000:walk(child&0x7fffffff,depth+1)
                else:
                    need(depth==2 and child+16<=size)
                    q=self.offset(rva+child,16);where=self.u(q,'I');length=self.u(q+4,'I')
                    need(92<=length<=1024*1024);v=self.offset(where,length)
                    need(self.u(v,'H')<=length and self.u(v+2,'H')==52 and self.u(v+4,'H')==0)
                    key='VS_VERSION_INFO\0'.encode('utf-16-le')
                    need(self.raw[v+6:v+6+len(key)]==key)
                    fixed=(v+6+len(key)+3)&~3;need(fixed+52<=v+self.u(v,'H'))
                    need(self.u(fixed,'I')==0xfeef04bd and self.u(fixed+4,'I')==0x10000 and self.u(fixed+36,'I')==2)
                    ms,ls=self.u(fixed+8,'I'),self.u(fixed+12,'I')
                    versions.append((ms>>16,ms&65535,ls>>16,ls&65535))
        walk(0,0);need(versions and len(set(versions))==1);return versions[0]


def requirements(files):
    result={}
    for path,raw in files.items():
        if not path.startswith('runtime/postgresql/') or not path.lower().endswith(('.exe','.dll')):continue
        for dll,names in Image(raw).crt_imports().items():result.setdefault(dll,set()).update(names)
    need(set(result)==CRT_DLLS)
    by_path={name.casefold():name for name in files};processes={}
    for root in ('runtime/postgresql/bin/initdb.exe','runtime/postgresql/bin/postgres.exe'):
        need(root in files);queue=[root];seen=set();needed=set()
        while queue:
            path=queue.pop()
            if path in seen:continue
            seen.add(path);need(len(seen)<=16000)
            for dll in pe_imports(files[path]):
                if dll in CRT_DLLS:needed.add(dll)
                else:
                    for candidate in (str(PurePosixPath(path).parent/dll),'runtime/postgresql/bin/'+dll):
                        actual=by_path.get(candidate.casefold())
                        if actual is not None:queue.append(actual);break
        need(needed);processes[root]=tuple(sorted(needed))
    return dict(symbols={name:tuple(sorted(symbols)) for name,symbols in sorted(result.items())},processes=processes)


def compatible(raw,symbols):
    """Machine, 14.x family and exact direct exports only; no toolset acceptance."""
    image=Image(raw);version=image.version();need(version[0]==14)
    exports=image.exports()
    need(symbols and all(s in exports and not exports[s] for s in symbols))
    return version
