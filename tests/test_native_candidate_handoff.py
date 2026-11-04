"""Actual ZIP extraction/negative source admission only; no Windows evidence."""
from hashlib import sha256
import io
import json
from pathlib import Path
import time
from types import SimpleNamespace
import zipfile

import pytest

from scripts.windows_ci import native_candidate_build as builder,native_business_window as window
from scripts.windows_portable import native_trial_authority as a,payload
from scripts.windows_portable.native_dpapi_peer import LocalServiceDPAPIPeer


def test_null_builder_record_refuses_before_temp_git_network(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(builder.subprocess,'check_output',lambda *args,**kw:pytest.fail('Git before admission'))
    monkeypatch.setattr(builder.urllib.request,'urlopen',lambda *args,**kw:pytest.fail('network before admission'))
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path))
    assert builder.main()==2 and list(tmp_path.iterdir())==[]
    assert 'WindowRefused' in capsys.readouterr().out


def test_unbound_peer_refuses_before_dll_or_thread(monkeypatch):
    import ctypes as C
    monkeypatch.setattr(C,'WinDLL',lambda *args,**kw:pytest.fail('native before admission'),raising=False)
    with pytest.raises(a.TrialRefused):LocalServiceDPAPIPeer(None,b'not a real cipher',b'e'*32,time.monotonic()+1)


def test_peer_requeries_actual_effective_token_instead_of_old_token_object():
    peer=object.__new__(LocalServiceDPAPIPeer);peer._time=lambda:None;peer.current_thread=lambda:999
    handles=iter((11,12));peer.open_thread=object();calls=[]
    def opened(fn,*args):calls.append(args);return next(handles)
    peer._output=opened
    peer._snapshot=lambda h:((1,b'B' if h==11 else b'A'),(8,2))
    identity=((1,b'B'),(8,1))
    assert dict(peer._effective(identity))[1]==b'B'
    with pytest.raises(a.TrialRefused):peer._effective(identity)
    assert calls==[(999,8,True),(999,8,True)]


def zip_fixture(*,symlink=False,extra=False):
    files={'app/example.txt':b'public synthetic fixture'}
    manifest=dict(schema=payload.SCHEMA,status='INITIALIZATION_NOT_ENABLED',source_commit='a'*40,
        usable_product=False,files=payload.file_manifest(files))
    raw=json.dumps(manifest).encode();data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as stream:
        for name,value in {**files,payload.MANIFEST:raw}.items():
            info=zipfile.ZipInfo(name);info.external_attr=(0o120777 if symlink and name in files else 0o100644)<<16
            stream.writestr(info,value)
        if extra:stream.writestr('../escape',b'bad')
    return data.getvalue(),raw


@pytest.mark.parametrize('symlink,extra',[(False,False),(True,False),(False,True)])
def test_source_admitted_archive_still_requires_exact_safe_exclusive_extraction(monkeypatch,tmp_path,symlink,extra):
    archive,raw=zip_fixture(symlink=symlink,extra=extra);destination=tmp_path/'payload'
    approval=SimpleNamespace(manifest_sha256=sha256(raw).hexdigest(),reviewed_parent='a'*40)
    context=window.current_context()
    monkeypatch.setattr(window,'_verify_archive_inputs',lambda *args:(approval,(),destination,archive,time.monotonic()+2,context))
    if symlink or extra:
        with pytest.raises(window.WindowRefused):window.extract_approved_archive(object(),destination,tmp_path/'candidate.zip')
        assert not destination.exists() and not (tmp_path/'escape').exists()
    else:
        window.extract_approved_archive(object(),destination,tmp_path/'candidate.zip')
        assert payload.verify_directory(destination)['source_commit']=='a'*40
        with pytest.raises(window.WindowRefused):window.extract_approved_archive(object(),destination,tmp_path/'candidate.zip')
