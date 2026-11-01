"""Desktop pipe/lifecycle protocol on Linux; not Windows/window acceptance."""
import io
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from scripts.windows_portable import desktop_bridge as d,entry


def value(**changes):
    return dict(action='reopen',instance='E:\\Software\\instance',database_port=0,
        api_port=0,passwords={},initialize_profile=False,**changes)


def test_bounded_first_request_rejects_duplicate_fields_secrets_on_reopen_and_second_launch():
    row=value();assert d.request(io.BytesIO(json.dumps(row).encode()+b'\n'))==row
    for raw in (b'{"action":"new","action":"reopen"}\n',b'x'*32769,
                json.dumps({**row,'passwords':{'enterprise':'SYNTHETIC_PRIVATE'}}).encode()+b'\n',
                json.dumps({**row,'initialize_profile':1}).encode()+b'\n'):
        with pytest.raises(ValueError):d.request(io.BytesIO(raw))


@pytest.mark.parametrize('signal,confirmed',[(b'S',True),(b'',False),(b'U',False),(b'X',False)])
def test_only_explicit_browser_exit_confirmation_can_be_normal_stop(signal,confirmed):
    channel=d.Channel(io.BytesIO(signal),io.BytesIO());channel.monitor()
    assert channel.stop.is_set() and channel.closed.is_set() and channel.confirmed is confirmed


def test_original_entry_owner_gate_precedes_hidden_enrollment_profile_and_ready(tmp_path,monkeypatch):
    (tmp_path/'app/scripts/windows').mkdir(parents=True)
    (tmp_path/'app/scripts/windows/lifecycle.py').write_text(
        "def setup_readiness(): return {'status':'BLOCKED','reason':'OWNER_MUTATION_PAUSED'}\n")
    monkeypatch.setattr(entry,'verified_payload',lambda:(tmp_path,{'source_commit':'a'*40},b'FROZEN'))
    sink=io.BytesIO();channel=d.Channel(io.BytesIO(),sink)
    row={**value(),'action':'new','database_port':55432,'api_port':58761,
         'passwords':{'not-a-real-account':'SYNTHETIC_PRIVATE_MUST_NOT_BE_EXPOSED'}}
    def forbidden(*args):pytest.fail('profile was reached behind original owner gate')
    assert d.run(row,channel,entry_module=entry,profile_factory=forbidden)==2
    assert sink.getvalue()==b'PW1\tREFUSED\tOWNER_MUTATION_PAUSED\n'


def test_precise_revocation_evidence_refusal_reaches_desktop_without_profile_or_install_hint(tmp_path,monkeypatch,capsys):
    from scripts.windows_portable.authenticode_signature import CRTRefused,CRTRevocationUnavailable
    from scripts.windows_portable.controller import ControlFailure
    reason='SYSTEM_CRT_REVOCATION_EVIDENCE_UNAVAILABLE'
    try:
        try:raise CRTRevocationUnavailable()
        except CRTRevocationUnavailable as original:raise CRTRefused() from original
    except CRTRefused as error:control=ControlFailure('ACQUIRE',error,[])
    monkeypatch.setattr(entry,'verified_payload',lambda:(tmp_path,{},b'FROZEN'))
    def invocation(*args,**kw):raise control
    monkeypatch.setattr(entry,'native_invocation',invocation)
    assert entry.main(['--action','reopen','--instance',str(tmp_path)])==2
    output=capsys.readouterr().err
    assert reason in output and '现有离线信息' in output and 'vc-redist' not in output
    class Entry:
        @staticmethod
        def main(*args,**kw):print(reason);return 2
    sink=io.BytesIO();channel=d.Channel(io.BytesIO(),sink)
    assert d.run(value(),channel,entry_module=Entry,profile_factory=lambda *a:pytest.fail('profile after refused entry'))==2
    assert sink.getvalue()==b'PW1\tUNKNOWN\tSYSTEM_CRT_REVOCATION_EVIDENCE_UNAVAILABLE\n'


@pytest.mark.parametrize('signal,normal',[(b'S',True),(b'',False),(b'U',False)])
def test_real_pipe_lifetime_close_confirmation_and_eof_do_not_share_stopped_outcome(signal,normal):
    import os
    read,write=os.pipe();source=os.fdopen(read,'rb',buffering=0)
    class Sink(io.BytesIO):
        def write(self,data):
            result=super().write(data)
            if data.startswith(b'PW1\tRUNNING\t'):
                if signal:os.write(write,signal)
                os.close(write)
            return result
    sink=Sink()
    channel=d.Channel(source,sink);monitor=threading.Thread(target=channel.monitor);monitor.start()
    events=[]
    class Profile:
        path='E:\\Software\\instance\\files\\desktop-profile'
        def verify(self):events.append('PROFILE_VERIFIED')
        def close(self):events.append('PROFILE_RETAINED_CLOSED')
    class Adapter:
        def live_identity(self,token):return ('OWNED_PROTOCOL_TOKEN',)
    app=SimpleNamespace(port=58761,adapter=Adapter(),api=object(),worker=object())
    workspace=SimpleNamespace(application=app,check=lambda:events.append('ORIGINAL_WORKSPACE_CHECK'))
    def factory(w,inv,fresh):
        assert w is workspace and fresh is False
        return Profile()
    class Entry:
        @staticmethod
        def main(args,**kwargs):
            try:kwargs['use_workspace'](workspace,object())
            except RuntimeError:return 2  # Controller's surfaced failure/UNKNOWN seam
            return 0
    try:
        result=d.run(value(),channel,entry_module=Entry,profile_factory=factory)
        monitor.join(timeout=2)
        data=sink.getvalue()
        assert b'RUNNING' in data and b'SYNTHETIC_PRIVATE' not in data
        assert (b'PW1\tSTOPPED\n' in data) is normal
        assert (b'PW1\tUNKNOWN\t' in data) is not normal
        assert result==(0 if normal else 2)
        assert events[-1]=='PROFILE_RETAINED_CLOSED'
    finally:source.close()


def test_desktop_current_source_never_uses_cli_passwords_or_browser_fallback():
    # Source/packaging contract only, not runtime rendering or Windows execution.
    cpp=Path('scripts/windows_desktop/host.cpp').read_text()
    assert 'ShellExecute' not in cpp.replace('// ParkWeave native desktop host. No ShellExecute/browser/installer fallback.','')
    assert 'BrowserProcessExited' in cpp and 'PROC_THREAD_ATTRIBUTE_HANDLE_LIST' in cpp
    settings=Path('scripts/windows_desktop/webview_settings.h').read_text()
    assert 'configureDesktopSettings<ICoreWebView2Settings,ICoreWebView2Settings4>' in cpp
    assert 'put_IsPasswordAutosaveEnabled(FALSE)' in settings and 'put_IsWebMessageEnabled(FALSE)' in settings
    batch=Path('scripts/windows_portable/ParkWeave.cmd').read_text()
    assert 'if "%~1"=="" goto desktop' in batch and '"%~dp0ParkWeave.exe"' in batch


def test_production_settings_function_queries_original_com_identity_and_releases_every_branch(tmp_path):
    """Compile the actual shared production function against distinct COM identities.

    This exercises receiver/reference ownership, not WebView2/Windows execution.
    """
    import shutil,subprocess
    compiler=shutil.which('g++')
    if compiler is None:pytest.skip('portable C++ compiler unavailable')
    code=tmp_path/'settings.cpp'
    code.write_text(r'''
#include <cstdlib>
#include <stdexcept>
constexpr int FALSE=0;
#include "webview_settings.h"
int mode=0,step=0,baseRefs=0,extendedRefs=0,baseReleases=0,extendedReleases=0,sets=0,viewQueries=0;
int setting(int value){if(value!=0||baseRefs!=1)throw std::runtime_error("SETTING");
 ++sets;return ++step==mode?-1:0;}
struct Extended {
 int put_IsPasswordAutosaveEnabled(int v){return setting(v);}
 int put_IsGeneralAutofillEnabled(int v){return setting(v);}
 void Release(){if(extendedRefs!=1)throw std::runtime_error("EXTENDED_RELEASE");--extendedRefs;++extendedReleases;}
} extended;
struct Settings {
 int put_AreHostObjectsAllowed(int v){return setting(v);}
 int put_IsWebMessageEnabled(int v){return setting(v);}
 int put_AreDevToolsEnabled(int v){return setting(v);}
 int put_AreDefaultContextMenusEnabled(int v){return setting(v);}
 int put_AreDefaultScriptDialogsEnabled(int v){return setting(v);}
 int QueryInterface(int iid,void** out){if(iid!=4||baseRefs!=1)throw std::runtime_error("IDENTITY");
  ++step;if(step==mode)return -1;
  if(mode==10){*out=nullptr;return 0;}
  *out=&extended;++extendedRefs;return 0;}
 void Release(){if(baseRefs!=1||extendedRefs)throw std::runtime_error("BASE_RELEASE");--baseRefs;++baseReleases;}
} settings;
struct View {
 int get_Settings(Settings** out){*out=&settings;++baseRefs;return ++step==mode?-1:0;}
 int QueryInterface(int,void**){++viewQueries;return -1;} // Independent view identity rejects Settings4.
} view;
int main(int argc,char** argv){mode=std::atoi(argv[1]);bool failed=false;
 try{configureDesktopSettings<Settings,Extended>(&view,4,[](int hr){if(hr<0)throw std::runtime_error("HRESULT");});}
 catch(...){failed=true;}
 if(failed!=(mode!=0)||viewQueries||baseRefs||extendedRefs||baseReleases!=1)return 2;
 if(extendedReleases!=((mode==0||mode==8||mode==9)?1:0))return 3;
 if(mode==0&&sets!=7)return 4;
 return 0;
}
''')
    binary=tmp_path/'settings-policy'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-I','scripts/windows_desktop',str(code),'-o',str(binary)],check=True,timeout=20)
    for mode in range(11):subprocess.run([str(binary),str(mode)],check=True,timeout=5)


def test_actual_host_interpreter_reaches_original_payload_gate_with_pipe_stream_contract(tmp_path,monkeypatch):
    """Real file/manifest verification; Win32 interpreter facts are emulated.

    The former pythonw host command fails this boundary before OWNER or any
    workspace is reached. No native interpreter, identity or DB is created.
    """
    import re
    from scripts.windows_portable.payload import MANIFEST,file_manifest
    root=tmp_path/'payload';(root/'launcher').mkdir(parents=True)
    (root/'runtime/python').mkdir(parents=True)
    files={'launcher/entry.py':b'# test boundary only\n',
           'runtime/python/python.exe':b'SYNTHETIC_CONSOLE_INTERPRETER_BYTES',
           'runtime/python/pythonw.exe':b'SYNTHETIC_WINDOWED_INTERPRETER_BYTES'}
    for name,raw in files.items():(root/name).write_bytes(raw)
    (root/MANIFEST).write_text(json.dumps(dict(schema='parkweave-windows-portable-candidate/1',
        status='INITIALIZATION_NOT_ENABLED',files=file_manifest(files))))
    monkeypatch.setattr(entry,'__file__',str(root/'launcher/entry.py'))
    facts=SimpleNamespace(platform='win32',maxsize=2**63-1,
        flags=SimpleNamespace(isolated=True),executable='')
    monkeypatch.setattr(entry,'sys',facts)
    cpp=Path('scripts/windows_desktop/host.cpp').read_text()
    selected=re.search(r'std::wstring exe=base\+L"([^"]+)"',cpp).group(1)
    selected=selected.replace('\\\\','/').lstrip('/')
    assert 'CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT' in cpp
    facts.executable=str(root/selected)
    assert entry.verified_payload()[0]==root
    # Retain the original strict interpreter rule; accepting pythonw or a
    # same-name external interpreter is not the fix.
    for wrong in (root/'runtime/python/pythonw.exe',tmp_path/'python.exe'):
        facts.executable=str(wrong)
        with pytest.raises(entry.PayloadRefused,match='PRIVATE_INTERPRETER_REQUIRED'):
            entry.verified_payload()
    facts.executable=str(root/selected)
    (root/'runtime/python/python.exe').write_bytes(b'TAMPERED')
    with pytest.raises(entry.PayloadRefused,match='MANIFEST_ROW'):
        entry.verified_payload()


def test_same_native_namespace_policy_rejects_real_unlisted_bootstrap_modules_and_directories(tmp_path):
    import shutil
    import subprocess
    compiler=shutil.which('g++')
    if compiler is None:pytest.skip('portable C++ compiler unavailable; not a Windows result')
    root=tmp_path/'payload';(root/'vendor').mkdir(parents=True);(root/'launcher').mkdir()
    (root/'vendor/known.py').write_text('# approved fixture\n');(root/'launcher/entry.py').write_text('# approved fixture\n')
    code=tmp_path/'namespace.cpp'
    code.write_text(r'''
#include "namespace_guard.h"
#include <filesystem>
int main(int argc,char** argv){DesktopNames files,dirs;
 for(auto& e:std::filesystem::recursive_directory_iterator(argv[1])){
  auto name=e.path().lexically_relative(argv[1]).generic_wstring();for(auto& c:name)if(c==L'/')c=L'\\';
  if(e.is_directory())dirs.insert(name);else files.insert(name);
 }
 return exactDesktopNamespace(files,dirs,{L"vendor\\known.py",L"launcher\\entry.py"},{L"vendor",L"launcher"})?0:2;
}
''')
    binary=tmp_path/'namespace-policy'
    subprocess.run([compiler,'-std=c++17','-I','scripts/windows_desktop',str(code),'-o',str(binary)],check=True,timeout=20)
    def check():return subprocess.run([str(binary),str(root)],timeout=5).returncode
    assert check()==0
    shadow=root/'vendor/entry.py';shadow.write_text('# unlisted shadow, never executed\n')
    assert check()==2;shadow.unlink()
    extra=root/'vendor/unlisted';extra.mkdir();assert check()==2;extra.rmdir()
    (root/'launcher/entry.py').rename(root/'launcher/Entry.py');assert check()==2
