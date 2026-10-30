"""Import vendor source from held verified bytes, never filesystem pycache.

Vendor is intentionally absent from ordinary sys.path/package search paths.
Only exact manifest .py/.pyd modules exist to this finder. Private native DLL
dependencies are preloaded from the same pinned manifest using SYSTEM32-only
dependency search before a pinned extension is initialized.
"""
import ctypes as C
import importlib.abc
import importlib.machinery as machinery
import importlib.metadata as metadata
import importlib.util
import io
from pathlib import Path
import re
import sys
import sysconfig


def restrict_bootstrap_imports(repo,pins):
    """Trust the reviewed checkout/runner stdlib; isolate candidate imports.

    This is not a hostile-same-user sandbox for the GitHub checkout. Candidate
    code and metadata, unlike those trusted coordinator inputs, use held bytes.
    """
    root=Path(repo).resolve()
    standard={Path(sysconfig.get_path(name)).resolve() for name in ('stdlib','platstdlib')}
    standard.update((Path(sys.base_prefix).resolve()/'DLLs',Path(sys.base_prefix).resolve()/'python312.zip'))
    allowed=(root,*standard)
    for module in tuple(sys.modules.values()):
        origin=getattr(module,'__file__',None)
        if not origin:continue
        path=Path(origin).resolve()
        if any(part.lower() in ('site-packages','dist-packages') for part in path.parts):
            raise ImportError('AMBIENT_PACKAGE_LOADED_BEFORE_PINNED_IMPORTS')
        if not any(path==base or path.is_relative_to(base) for base in allowed):
            raise ImportError('UNREVIEWED_BOOTSTRAP_MODULE_ALREADY_LOADED')
    sys.path[:]=[str(root),str(root/'src'),*(str(path) for path in sorted(standard))]
    sys.meta_path[:]=[finder for finder in sys.meta_path if finder in
        (machinery.BuiltinImporter,machinery.FrozenImporter,machinery.PathFinder)]
    return PinnedVendorFinder(pins).install()


class PinnedVendorFinder(importlib.abc.MetaPathFinder):
    def __init__(self,pins):
        self.pins=pins;self.names=frozenset(n for n in pins.files if n.startswith('vendor/'))
        self.roots=set();self.dlls={};self.loaded={};self.loading=set()
        self.distributions=sorted({n.split('/')[1] for n in self.names
            if n.split('/')[1].endswith('.dist-info')})
        for name in self.names:
            relative=name[len('vendor/'):];first=relative.split('/')[0]
            if '/' not in relative:
                for suffix in ('.py',*machinery.EXTENSION_SUFFIXES):
                    if first.endswith(suffix):first=first[:-len(suffix)];break
            if first.isidentifier():self.roots.add(first)
            if name.lower().endswith('.dll'):
                key=name.rsplit('/',1)[1].lower()
                if key in self.dlls:raise ImportError('AMBIGUOUS_PINNED_PRIVATE_DLL')
                self.dlls[key]=name

    def install(self):
        if any(name in sys.modules for name in self.roots):raise ImportError('VENDOR_ALREADY_IMPORTED_BEFORE_PINS')
        sys.meta_path.insert(0,self)
        return self

    def _private_dependencies(self,name):
        if name in self.loaded:return
        if name in self.loading:raise ImportError('PINNED_PRIVATE_DLL_CYCLE')
        self.loading.add(name)
        try:
            from scripts.windows_portable.payload import pe_imports
            raw=self.pins.read(name)
            for dependency in pe_imports(raw):
                target=self.dlls.get(dependency.lower())
                if target is not None:self._private_dependencies(target)
            # Do not search the importing directory/PATH for unlisted private
            # dependencies. Known private dependencies are already loaded;
            # remaining dependencies must come from SYSTEM32/existing runtime.
            library=C.WinDLL(str(self.pins.payload/Path(name)),winmode=0x800)
            self.loaded[name]=library
        finally:self.loading.remove(name)

    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] not in self.roots:return None
        base='vendor/'+fullname.replace('.','/')
        for name,package in ((base+'/__init__.py',True),(base+'.py',False)):
            if name in self.names:
                loader=_Source(self,name,package)
                spec=importlib.util.spec_from_loader(fullname,loader,is_package=package)
                spec.origin=str(self.pins.payload/Path(name))
                if package:spec.submodule_search_locations=['pinned-vendor://'+base]
                return spec
        for suffix in machinery.EXTENSION_SUFFIXES:
            for name,package in ((base+'/__init__'+suffix,True),(base+suffix,False)):
                if name in self.names:
                    self._private_dependencies(name)
                    loader=machinery.ExtensionFileLoader(fullname,str(self.pins.payload/Path(name)))
                    spec=importlib.util.spec_from_file_location(fullname,loader.path,loader=loader)
                    if package:spec.submodule_search_locations=['pinned-vendor://'+base]
                    return spec
        # Explicit namespace directories are manifested by their children.
        if any(name.startswith(base+'/') for name in self.names):
            spec=machinery.ModuleSpec(fullname,loader=None,is_package=True)
            spec.submodule_search_locations=['pinned-vendor://'+base]
            return spec
        raise ModuleNotFoundError('module absent from pinned vendor manifest',name=fullname)

    def find_distributions(self,context=metadata.DistributionFinder.Context()):
        wanted=re.sub('[-_.]+','-',context.name).lower() if context.name else None
        for directory in self.distributions:
            dist=_Distribution(self,directory)
            actual=dist.metadata.get('Name','')
            if wanted is None or re.sub('[-_.]+','-',actual).lower()==wanted:yield dist


class _Source(importlib.abc.Loader):
    def __init__(self,finder,name,package):self.finder,self.name,self.package=finder,name,package
    def create_module(self,spec):return None
    def exec_module(self,module):
        raw=self.finder.pins.read(self.name)
        origin=str(self.finder.pins.payload/Path(self.name))
        module.__file__=origin
        if self.package:module.__path__=['pinned-vendor://'+self.name.rsplit('/',1)[0]]
        exec(compile(raw,origin,'exec',dont_inherit=True),module.__dict__)
    def get_source(self,fullname):return self.finder.pins.read(self.name).decode('utf-8')
    def get_resource_reader(self,fullname):return _Resources(self.finder,self.name.rsplit('/',1)[0])
    def get_data(self,path):
        relative=Path(path).relative_to(self.finder.pins.payload).as_posix()
        return self.finder.pins.read(relative)


class _Resources(importlib.abc.ResourceReader):
    def __init__(self,finder,prefix):self.finder,self.prefix=finder,prefix
    def open_resource(self,resource):return io.BytesIO(self.finder.pins.read(self.prefix+'/'+resource))
    def resource_path(self,resource):raise FileNotFoundError('held resource has no mutable path')
    def is_resource(self,name):return self.prefix+'/'+name in self.finder.names
    def contents(self):return iter(sorted({n[len(self.prefix)+1:].split('/')[0] for n in self.finder.names if n.startswith(self.prefix+'/')}))


class _Distribution(metadata.Distribution):
    def __init__(self,finder,directory):self.finder,self.directory=finder,directory
    def read_text(self,filename):
        name='vendor/'+self.directory+'/'+filename
        return self.finder.pins.read(name).decode('utf-8') if name in self.finder.names else None
    def locate_file(self,path):
        name='vendor/'+str(path).replace('\\','/')
        if name!='vendor/' and name not in self.finder.names:raise FileNotFoundError('resource absent from pinned manifest')
        return self.finder.pins.payload/Path(name)
