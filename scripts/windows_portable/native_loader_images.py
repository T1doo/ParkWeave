"""Issue only original held-installation native image bytes, never path input."""
from hashlib import sha256
import time
import weakref
from . import native_trial_authority as a
from .endpoint_plan import _key_held


class HeldImages:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('held images cannot be transferred')
    def __copy__(self):raise TypeError('held images cannot be copied')
    def __deepcopy__(self,memo):raise TypeError('held images cannot be copied')


_issued=weakref.WeakKeyDictionary()


def capture(lease,security,deadline):
    from .native_instance_security import NativeFixedStoreSecurity
    from .native_runtime_staging import NativeRuntimeInstallation,CHUNK
    from .native_acceptance_issuer import _deadline
    from .windows_process_handles import native_file_path
    from .crt_pe import Image
    _deadline(deadline);deadline=a.budget(lease,deadline)
    a.need(a.bound_state(lease) is not None and type(security) is NativeFixedStoreSecurity
        and security.lease is lease and type(security.runtime_installation) is NativeRuntimeInstallation)
    installation=security.runtime_installation;installation._issued_binding(lease,security.runtime)
    a.need(_key_held(lease)==installation.key)
    installation.deadline=installation.probe.deadline=deadline
    result={}
    for name,size,digest in installation.files:
        if not name.lower().endswith(('.exe','.dll','.pyd')):continue
        installation._gate();handle,directory,before=installation.rows[name]
        a.need(not directory and size==before[0].size and installation._inspect(handle,False)==before)
        installation.api.need(installation.seek(handle,0,None,0));parts=[];remaining=size
        while remaining:
            installation._gate();part=installation.api.read(handle,min(CHUNK,remaining))
            a.need(0<len(part)<=remaining);parts.append(part);remaining-=len(part)
        raw=b''.join(parts)
        a.need(installation.api.read(handle,1)==b'' and sha256(raw).hexdigest()==digest
            and installation._inspect(handle,False)==before)
        image=Image(raw);image.import_slots()
        result[name]=(native_file_path(installation.api,handle),raw)
    installation._issued_binding(lease,security.runtime)
    cap=HeldImages();_issued[cap]=(lease,security,installation,tuple(sorted(security.runtime.items())),result,a.bound_state(lease).deadline)
    return cap


def inspect(cap,lease,witness,deadline):
    from .crt_pe import Image
    from .native_acceptance_issuer import _deadline
    _deadline(deadline)
    a.need(type(cap) is HeldImages and cap in _issued)
    original,security,installation,runtime,raw,expires=_issued[cap]
    a.need(original is lease and witness.lease is lease and witness.installation is installation
        and time.monotonic()<deadline<=expires and _key_held(lease)==installation.key)
    a.budget(lease,deadline);installation._issued_binding(lease,dict(runtime))
    return {name:(path,Image(data)) for name,(path,data) in raw.items()}
