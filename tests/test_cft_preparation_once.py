"""Small synthetic archives only, no download/process/browser/credential action."""
from pathlib import Path
import json
import stat
import time
import zipfile
import pytest
from scripts import cft_preparation_once as m


def elf():
    raw=bytearray(64);raw[:7]=b'\x7fELF\x02\x01\x01';raw[16:18]=(3).to_bytes(2,'little');raw[18:20]=(62).to_bytes(2,'little');return bytes(raw)+b'SYNTHETIC_NO_EXECUTION'


def archive(tmp_path,extra=(),mode=0o100755):
    path=tmp_path/'original.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data,bits in [('chrome-linux64/',b'',0o40755),('chrome-linux64/chrome',elf(),mode),('chrome-linux64/ABOUT',b'SYNTHETIC NOTICE',0o100644),*extra]:
            info=zipfile.ZipInfo(name);info.create_system=3;info.external_attr=bits<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    return path


def test_bounded_unpack_and_identity_modes_no_execution(tmp_path):
    archive(tmp_path);report={}
    m.unpack(tmp_path,time.monotonic()+10,report)
    assert report['status']=='BYTES_LAYOUT_VERIFIED_REVIEW_REQUIRED' and report['launch_authorized'] is False
    assert report['entries']==3 and report['actual_unpacked']==report['declared_unpacked']
    assert stat.S_IMODE((tmp_path/'chrome-linux64/chrome').stat().st_mode)==0o700
    assert report['elf_sha256']==m.sha256(elf()).hexdigest()
    assert report['license_files'][0]['path']=='chrome-linux64/ABOUT'


@pytest.mark.parametrize('extra,mode',[
    ([('chrome-linux64/../escape',b'x',0o100644)],0o100755),
    ([('chrome-linux64/link',b'x',0o120777)],0o100755),
    ([('chrome-linux64/ABOUT',b'x',0o100644)],0o100755),
    ([],0o100777),([],0o104755),
])
def test_unsafe_archive_rejected_before_extraction(tmp_path,extra,mode):
    path=archive(tmp_path,extra,mode)
    with pytest.raises(m.Closed):m.entries(path)
    assert not (tmp_path/'chrome-linux64').exists()


def test_size_and_central_directory_bounds_before_unzip(tmp_path,monkeypatch):
    path=archive(tmp_path);monkeypatch.setattr(m,'UNPACK',2)
    with pytest.raises(m.Closed):m.entries(path)
    raw=bytearray(path.read_bytes());index=raw.rfind(b'PK\x05\x06');raw[index+12:index+16]=(5*m.MiB).to_bytes(4,'little');path.write_bytes(raw)
    with pytest.raises(m.Closed):m.entries(path)


def test_fixed_download_integrity_and_no_redirect_or_extra_request(tmp_path,monkeypatch):
    import io
    payload=b'SYNTHETIC_ARCHIVE_ONLY';size=len(payload)
    monkeypatch.setattr(m,'SIZE',size);monkeypatch.setattr(m,'MD5',m.base64.b64encode(m.md5(payload,usedforsecurity=False).digest()).decode())
    class Stream(io.BytesIO):
        def __init__(self,raw,headers={}):super().__init__(raw);self.headers=headers;self.fp=type('FP',(),{'raw':type('Raw',(),{'_sock':type('Sock',(),{'settimeout':lambda *a:None})()})()})()
        def read1(self,size):return self.read(size)
    calls=[]
    def response(url,deadline):
        calls.append(url)
        if url==m.META:return Stream(json.dumps({'name':m.OBJECT,'size':str(size),'md5Hash':m.MD5,'crc32c':m.CRC32C,'generation':m.GENERATION}).encode())
        assert url==m.MEDIA
        return Stream(payload,{'x-goog-generation':m.GENERATION,'Content-Length':str(size)})
    monkeypatch.setattr(m,'response',response);report={}
    m.get_fixed_archive(tmp_path,time.monotonic()+10,report)
    assert calls==[m.META,m.MEDIA] and report['archive_sha256']==m.sha256(payload).hexdigest() and report['md5_verified']
    assert report['crc32c_recomputed'] is False and report['publisher_sha256_available'] is False


def test_metadata_mismatch_never_fetches_binary(tmp_path,monkeypatch):
    import io
    calls=[]
    monkeypatch.setattr(m,'response',lambda url,deadline:calls.append(url) or io.BytesIO(b'{}'))
    with pytest.raises(m.Closed):m.get_fixed_archive(tmp_path,time.monotonic()+10,{})
    assert calls==[m.META] and not list(tmp_path.iterdir())


def test_disk_threshold_and_report_bound(tmp_path,monkeypatch):
    (tmp_path/'owned').write_bytes(b'12345');monkeypatch.setattr(m,'CONTENT',4);report={}
    with pytest.raises(m.Closed):m.disk(tmp_path,time.monotonic()+10,report)
    assert report['peak_logical_bytes']==5
    with pytest.raises(m.Closed):m.save(tmp_path/'result.json',{'SYNTHETIC':'x'*m.REPORT})
    assert not (tmp_path/'result.json').exists()


def test_cleanup_refuses_replaced_or_unknown_root_without_deleting(tmp_path,monkeypatch):
    import os
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path));path=tmp_path/('cft-private-'+'a'*32);path.mkdir(mode=0o700)
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY);st=os.fstat(fd)
    try:
        (path/'link').symlink_to(tmp_path)
        with pytest.raises(m.Closed):m.remove(path,fd,(st.st_dev,st.st_ino),time.monotonic()+10)
        assert path.exists() and (path/'link').is_symlink()
    finally:os.close(fd)


def test_fixed_reason_codes_never_serialize_foreign_exception_text():
    import ast
    tree=ast.parse(Path(m.__file__).read_text())
    for call in ast.walk(tree):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='Closed':
            assert len(call.args)==1 and isinstance(call.args[0],ast.Constant) and isinstance(call.args[0].value,str)
    assert 'SYNTHETIC_SECRET' not in json.dumps(m.fault(ValueError('SYNTHETIC_SECRET')))
    assert m.fault(m.Closed('archive path'))['reason_code']=='ARCHIVE_PATH'
    assert m.valid_worker({'status':'BYTES_LAYOUT_VERIFIED_REVIEW_REQUIRED'},'a'*40) is False


def test_zip_close_failure_does_not_replace_read_failure(tmp_path,monkeypatch):
    archive(tmp_path);z,items,total=m.entries(tmp_path/'original.zip')
    class BrokenZip:
        def open(self,*args):raise ValueError('SYNTHETIC_PRIMARY')
        def close(self):raise OSError('SYNTHETIC_CLEANUP')
    monkeypatch.setattr(m,'entries',lambda path:(BrokenZip(),items,total))
    try:
        with pytest.raises(ValueError) as e:m.unpack(tmp_path,time.monotonic()+10,{})
        assert e.value.archive_close_error['error_type']=='OSError'
    finally:z.close()


@pytest.mark.parametrize('save_fails',[False,True])
def test_worker_close_and_save_failures_preserve_original_fault(tmp_path,monkeypatch,capsys,save_fails):
    import io,os
    from types import SimpleNamespace
    original_open=os.open;original_close=os.close;opened=[];saved=[]
    def open_fd(*args,**kw):
        fd=original_open(*args,**kw);opened.append(fd);return fd
    monkeypatch.setattr(m.os,'open',open_fd)
    def close_fd(fd):raise OSError('SYNTHETIC_CLOSE')
    monkeypatch.setattr(m.os,'close',close_fd)
    monkeypatch.setattr(m,'gate',lambda *a:None)
    monkeypatch.setattr(m,'root_verify',lambda *a:None)
    monkeypatch.setattr(m,'regular',lambda *a:b'SYNTHETIC_FIXED_SOURCE')
    monkeypatch.setattr(m,'git',lambda *a:b'SYNTHETIC_FIXED_SOURCE')
    monkeypatch.setenv('GITHUB_WORKSPACE',str(tmp_path))
    monkeypatch.setattr(m.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(json.dumps(dict(parent_pid=os.getppid(),worker_pid=os.getpid(),started=100)).encode()+b'\n')))
    activation=SimpleNamespace(OnceClaim=SimpleNamespace(restore=lambda *a:SimpleNamespace(value={'started':100})))
    tree=SimpleNamespace(identity=lambda pid:{'start_ticks':1})
    monkeypatch.setattr(m,'helper',lambda source,name,started:activation if name=='template_http_activation' else tree)
    def download(path,deadline,report):report['phase']='FIXED_OFFICIAL_DOWNLOAD';raise ValueError('SYNTHETIC_DOWNLOAD')
    monkeypatch.setattr(m,'get_fixed_archive',download)
    def save(path,report):
        saved.append(dict(report))
        if save_fails:raise PermissionError('SYNTHETIC_SAVE')
    monkeypatch.setattr(m,'save',save)
    args=SimpleNamespace(repo=str(tmp_path),source='a'*40,claim='synthetic',claim_identity=[1,2],claim_file_identity=[3,4],worker=str(tmp_path),identity=[1,2])
    try:
        assert m.worker(args)==1
        assert len(opened)==1 and saved[0]['error_type']=='ValueError' and saved[0]['root_close_error']['error_type']=='OSError'
        if save_fails:
            report=json.loads(capsys.readouterr().out)
            assert m.safe_failure(report) and report['primary']['error_type']=='ValueError' and report['publication_error']['error_type']=='PermissionError'
    finally:
        for fd in opened:original_close(fd)


def test_parent_final_report_failure_is_explicit_and_keeps_primary(monkeypatch,capsys,tmp_path):
    def fail(*a):raise OSError('SYNTHETIC_WRITE_SECRET')
    monkeypatch.setattr(m,'save',fail)
    assert m.finish(tmp_path,{'status':'FAIL','scope':'PREPARATION_ONLY','phase':'OWNED_WORKER','error_type':'ValueError','reason_code':'UNCLASSIFIED_FAILURE'})==1
    value=json.loads(capsys.readouterr().out)
    assert value['stage']=='PARENT_FINAL_REPORT' and value['primary']['error_type']=='ValueError' and value['publication_error']['error_type']=='OSError'
    assert 'SYNTHETIC' not in json.dumps(value)


def test_zip64_metadata_and_local_forced_zip64_rejected(tmp_path):
    archive(tmp_path)
    with pytest.raises(m.Closed):m.reject_zip64(b'\x01\x00\x00\x00')
    path=tmp_path/'forced.zip'
    with zipfile.ZipFile(path,'w') as z:
        item=zipfile.ZipInfo('chrome-linux64/chrome');item.create_system=3;item.external_attr=0o100755<<16
        with z.open(item,'w',force_zip64=True) as out:out.write(elf())
    with pytest.raises(m.Closed):m.entries(path)


def test_owned_cleanup_requires_original_identity_then_removes_only_own_tree(tmp_path,monkeypatch):
    import os
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path));path=tmp_path/('cft-private-'+'b'*32);path.mkdir(mode=0o700)
    (path/'child').mkdir(mode=0o700);(path/'child/file').write_bytes(b'SYNTHETIC_ONLY');foreign=tmp_path/'unrelated';foreign.write_bytes(b'KEEP')
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY);st=os.fstat(fd)
    try:
        with pytest.raises(m.Closed):m.remove(path,fd,(st.st_dev,st.st_ino+1),time.monotonic()+10)
        assert path.exists() and foreign.read_bytes()==b'KEEP'
        m.remove(path,fd,(st.st_dev,st.st_ino),time.monotonic()+10)
        assert not path.exists() and foreign.read_bytes()==b'KEEP'
    finally:os.close(fd)
