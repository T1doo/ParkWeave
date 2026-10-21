"""Only synthetic byte streams/temporary fixtures; no real font or network."""
from copy import deepcopy
from hashlib import sha1,sha256
import io,json,os
from pathlib import Path
import subprocess,tempfile,time
from unittest.mock import patch
from types import SimpleNamespace
from scripts import fictional_park_font_once as font
from scripts import fictional_park_restart_browser_once as recovery

ROOT=Path(__file__).parent
DATA=b'UNIT_FONT_BYTES_NOT_A_REAL_FONT'
NOTICE=b'UNIT_LICENSE_BYTES_NOT_A_REAL_LICENSE'
def spec(name,relative,data):return (name,relative,len(data),sha1(f'blob {len(data)}\0'.encode()+data).hexdigest())
SPECS=(spec('LICENSE','Sans/LICENSE',NOTICE),spec('NotoSansCJKsc-Regular.otf','Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',DATA))
results=[]
class Response(io.BytesIO):
    def __init__(self,data,url):
        super().__init__(data);self.url=url;self.timeouts=[]
        self.fp=SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=self.timeouts.append)))
    def isclosed(self):return self.closed
    def read1(self,size):return super().read(min(size,7))
    def geturl(self):return self.url
class Opener:
    def __init__(self,data,redirect=False):self.data=data;self.redirect=redirect
    def open(self,url,timeout):
        assert 0<timeout<=15 and font.COMMIT in url and url.startswith('https://raw.githubusercontent.com/notofonts/noto-cjk/')
        return Response(self.data,'https://invalid.example/' if self.redirect else url)

directory=Path(tempfile.mkdtemp(prefix='approved-',dir=ROOT))
assets={}
for entry,data in zip(SPECS,(NOTICE,DATA)):
    with patch.object(font.urllib.request,'build_opener',return_value=Opener(data)):
        assets[entry[0]]=font.stage_asset(entry,directory,time.monotonic()+45)
receipt=dict(commit=font.COMMIT,license='SIL Open Font License 1.1',assets=assets)
(directory/'font-source.json').write_text(json.dumps(receipt))
with patch.object(font,'DIRECTORY',directory),patch.object(font,'ASSETS',SPECS):
    approved=font.verified_font(required=True)
assert assets[SPECS[1][0]]['sha256']==sha256(DATA).hexdigest()
results.append(dict(name='two_exact_assets_size_git_blob_SHA256_and_receipt_reverified',result='PASS',synthetic=True))

for name,data,redirect in [('oversize',DATA+b'x',False),('wrong_blob',b'X'+DATA[1:],False),('short',DATA[:-1],False),('redirect',DATA,True)]:
    target=Path(tempfile.mkdtemp(prefix=name+'-',dir=ROOT))
    try:
        with patch.object(font.urllib.request,'build_opener',return_value=Opener(data,redirect)):
            font.stage_asset(SPECS[1],target,time.monotonic()+45)
    except AssertionError:pass
    else:raise AssertionError(name+' accepted')
    assert not (target/SPECS[1][0]).exists()
assert font.NoRedirect().redirect_request(None,None,302,'',{},'https://invalid.example/') is None
results.append(dict(name='size_short_oversize_blob_and_redirect_refused_before_asset_acceptance',result='PASS',subcases=4))

for change in ['extra','changed_receipt','changed_font','font_symlink','receipt_symlink']:
    target=Path(tempfile.mkdtemp(prefix=change+'-',dir=ROOT))
    for name,data in [(SPECS[0][0],NOTICE),(SPECS[1][0],DATA),('font-source.json',json.dumps(receipt).encode())]:(target/name).write_bytes(data)
    if change=='extra':(target/'other.otf').write_bytes(b'UNAPPROVED')
    elif change=='changed_receipt':
        changed=deepcopy(receipt);changed['assets'][SPECS[1][0]]['sha256']='0'*64;(target/'font-source.json').write_text(json.dumps(changed))
    elif change=='changed_font':(target/SPECS[1][0]).write_bytes(b'X'+DATA[1:])
    elif change=='font_symlink':
        (target/SPECS[1][0]).unlink();(target/SPECS[1][0]).symlink_to(directory/SPECS[1][0])
    else:
        (target/'font-source.json').unlink();(target/'font-source.json').symlink_to(directory/'font-source.json')
    try:
        with patch.object(font,'DIRECTORY',target),patch.object(font,'ASSETS',SPECS):font.verified_font(required=True)
    except AssertionError:pass
    else:raise AssertionError(change+' accepted')
results.append(dict(name='extra_directory_font_receipt_tamper_binary_tamper_and_both_symlinks_refused',result='PASS',subcases=5))


# Shared deadline: no request after expiry; open/read get actual remaining time.
target=Path(tempfile.mkdtemp(prefix='deadline-',dir=ROOT))
with patch.object(font.time,'monotonic',return_value=46),patch.object(font.urllib.request,'build_opener') as opener:
    try:font.stage_asset(SPECS[1],target,45)
    except TimeoutError:pass
    else:raise AssertionError('expired open accepted')
    opener.return_value.open.assert_not_called()
response=Response(DATA,'https://raw.githubusercontent.com/notofonts/noto-cjk/'+font.COMMIT+'/'+SPECS[1][1])
with patch.object(font.time,'monotonic',return_value=43),patch.object(font.urllib.request,'build_opener') as opener:
    opener.return_value.open.return_value=response
    font.stage_asset(SPECS[1],target,45)
    assert opener.return_value.open.call_args.kwargs['timeout']==2
assert response.timeouts and all(t==2 for t in response.timeouts)
results.append(dict(name='expired_open_forbidden_and_open_each_read_use_remaining_shared_deadline',result='PASS'))

# Hash completion crossing the shared deadline must not accept/rename the file.
target=Path(tempfile.mkdtemp(prefix='late-hash-',dir=ROOT));clock=[0]
original_inspect=font.inspect
def late_inspect(*args):
    result=original_inspect(*args);clock[0]=46;return result
with patch.object(font.time,'monotonic',side_effect=lambda:clock[0]),patch.object(font,'inspect',side_effect=late_inspect),patch.object(font.urllib.request,'build_opener',return_value=Opener(DATA)):
    try:font.stage_asset(SPECS[1],target,45)
    except TimeoutError:pass
    else:raise AssertionError('late hash accepted')
assert not (target/SPECS[1][0]).exists()
results.append(dict(name='hash_crossing_deadline_refused_before_asset_acceptance',result='PASS'))

points={ord('中'),ord('，')};private=directory/SPECS[1][0]
row='\t'.join([str(private),'0','Noto Sans CJK SC','NotoSansCJKsc-Regular','4e2d ff0c'])+'\n'
assert recovery.font_candidates(row,points)[0]['eligible'] is False
assert recovery.font_candidates(row,points,approved)[0]['source']=='EXACT_APPROVED_OFFICIAL_FONT'
other=directory/'another.otf';other.write_bytes(DATA)
for raw in [row.replace(str(private),str(other)),row.replace('\t0\t','\t1\t'),row.replace('NotoSansCJKsc-Regular','OtherPS')]:
    assert recovery.font_candidates(raw,points,approved)[0]['eligible'] is False
other.unlink()
results.append(dict(name='only_exact_verified_private_file_face0_and_PS_allowed_not_directory',result='PASS'))

report={};target=ROOT/('fontconfig-'+next(tempfile._get_candidate_names()));calls=[]
allpoints=recovery.ui_codepoints(''.join((recovery.original.ROOT/p).read_text() for p in ['src/parkweave/web.html','src/parkweave/park_demo_web.html']))
raw='\t'.join([str(private),'0','Noto Sans CJK SC','NotoSansCJKsc-Regular',' '.join(f'{p:x}' for p in sorted(allpoints))])+'\n'
def command(argv,**kw):
    calls.append((argv,kw['env']))
    config=Path(kw['env']['FONTCONFIG_FILE'])
    assert '<dir>'+str(directory)+'</dir>' in config.read_text()
    assert kw['timeout']==3
    return subprocess.CompletedProcess(argv,0,stdout=raw.encode(),stderr=b'')
with patch.object(font,'verified_font',return_value=approved),patch.object(recovery.subprocess,'run',side_effect=command):
    env=recovery.installed_font_environment(dict(os.environ),target,report)
assert len(calls)==3 and all(c[1]['FONTCONFIG_FILE']==env['FONTCONFIG_FILE'] for c in calls)
selected=report['installed_CJK_font'];assert selected['status']=='INSTALLED_CHARSET_COVERS_UI' and len(selected['required_codepoints'])==683
assert selected['approved_font_staged_before_browser'] and not selected['rendering_observed']
results.append(dict(name='same_private_fontconfig_inventory_two_resolved_chains_full683_fixture',result='PASS'))

fresh=ROOT/'MUST_NOT_BE_CREATED_BY_LOCAL_HOST'
with patch.object(font,'DIRECTORY',fresh),patch.object(font.urllib.request,'build_opener',side_effect=AssertionError('NETWORK_MUST_NOT_RUN')):
    code=font.main()
assert code==1 and not fresh.exists()
results.append(dict(name='local_CLI_host_gate_refuses_before_directory_or_network',result='PASS'))

source=Path(recovery.__file__).read_text();baseline=subprocess.check_output(['git','show','ac81321e579e5ea9b5a4a8063f5bcbe55af66e03:scripts/fictional_park_restart_browser_once.py'],text=True)
assert source[source.index('def readonly_store('):source.index("if __name__ == '__main__':")]==baseline[baseline.index('def readonly_store('):baseline.index("if __name__ == '__main__':")]
results.append(dict(name='business_recovery_assertions_byte_identical',result='PASS'))
output=dict(results=results,network_calls=0,font_binary_downloaded=False,services_started=False,browser_started=False,CI_started=False,
    source_hashes={str(p.relative_to(recovery.original.ROOT)):sha256(p.read_bytes()).hexdigest() for p in [Path(font.__file__),Path(recovery.__file__)]},
    note='All accepted download/approved-face/CDP inputs in this procedure are explicit synthetic byte fixtures, not real fonts or rendered evidence')
(ROOT/'stage-checks.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
