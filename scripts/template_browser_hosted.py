"""Single run49 hosted bootstrap. Existing run48 assets/terms, no new runtime.

Dependency/font staging is outside the separate360s integration clock and
inside the existing3min bootstrap /10min job. This never activates a contract.
"""
import json
import os
from pathlib import Path
import re
import sys
import time

from scripts import template_http_activation as activation
from scripts import template_browser_client as client
from scripts.fictional_park_font_once import ASSETS,COMMIT,DIRECTORY,stage_asset,verified_font

ROOT=Path(__file__).resolve().parents[1]
NUMBER='49'
REF='refs/heads/'+activation.BRANCH
# Whitelist maps reviewed literal failures only, not arbitrary exception text.
REASONS={text:'REJECT_'+str(index) for index,text in enumerate((
    'single public hosted Linux invocation required','inherited business configuration refused',
    'exact source required','activation shape','window closed','activation binding',
    'admission must cover360s and expire within one hour','activation changed or expired',
    'execution source changed','fixed development branch required','dirty source',
    'reviewed direct parent required','activation may change only its contract','activation not committed exactly',
    'bounded ordinary file required','file changed during read','file name changed during read',
    'standard runner Chrome required','fixed approved cache mismatch','fresh hosted evidence parent required',
    'existing Playwright required','existing standard Chrome required','fixed existing approved font cache required',
    'existing fontconfig required','approved font or license drift','bounded ordinary asset required','asset drift',
),start=1)}


def gate(environment,report=None):
    report={} if report is None else report
    report['stage']='HOST_GATE'
    expected={'GITHUB_REPOSITORY':'T1doo/ParkWeave','GITHUB_REF':REF,
              'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1',
              'GITHUB_RUN_NUMBER':NUMBER,'RUNNER_ENVIRONMENT':'github-hosted',
              'RUNNER_OS':'Linux','PW_PUBLIC':'true'}
    report['host_checks']={k:environment.get(k)==v for k,v in expected.items()}
    if not all(report['host_checks'].values()):raise activation.Closed('single public hosted Linux invocation required')
    report['host_admitted']=True
    if any(k.startswith('PARKWEAVE_') for k in environment):raise activation.Closed('inherited business configuration refused')
    source=environment.get('GITHUB_SHA','')
    if re.fullmatch('[a-f0-9]{40}',source) is None:raise activation.Closed('exact source required')
    report['stage']='SOURCE_GATE'
    raw=json.loads(activation.regular_bytes(ROOT/activation.PROFILES['BROWSER'],2048)[0])
    approval=activation.load(raw.get('invocation'),'BROWSER')
    activation.verify_source(source,approval,time.monotonic())
    report['source']=source
    return source,approval.invocation


def prepare(environment,report=None):
    report={} if report is None else report
    source,invocation=gate(environment,report)
    # Standard runner-installed Chrome, never Playwright browser installation.
    report['stage']='STANDARD_CHROME_PREFLIGHT'
    st=client.CHROME.lstat()
    report['chrome_checks']={'symlink':client.CHROME.is_symlink(),'regular':client.CHROME.is_file(),'trusted_owner':st.st_uid in (0,os.geteuid()),'not_group_or_other_writable':not bool(st.st_mode&0o022),'executable':bool(st.st_mode&0o111)}
    if client.CHROME.is_symlink() or not client.CHROME.is_file() or st.st_uid not in (0,os.geteuid()) or st.st_mode&0o022 or not st.st_mode&0o111:raise activation.Closed('standard runner Chrome required')
    report['stage']='FIXED_FONT_CACHE'
    if DIRECTORY!=ROOT/client.FONT_RELATIVE:raise activation.Closed('fixed approved cache mismatch')
    DIRECTORY.mkdir(mode=0o700,exist_ok=False)
    assets={};started=time.monotonic()
    for asset in ASSETS:
        report['stage']='APPROVED_FONT_LICENSE' if asset[0]=='LICENSE' else 'APPROVED_FONT_BINARY'
        assets[asset[0]]=stage_asset(asset,DIRECTORY,started+45)
    (DIRECTORY/'font-source.json').write_text(json.dumps({'commit':COMMIT,'license':'SIL Open Font License 1.1','assets':assets})+'\n')
    report['stage']='FIXED_FONT_RECEIPT'
    verified_font(required=True)
    report['assets']=assets
    report['stage']='BROWSER_CLIENT_PREFLIGHT'
    client.preflight(ROOT,None)
    # Existing parent path required by the reviewed evidence root; never shared
    # DB data, and never choose another path when an existing object mismatches.
    report['stage']='FRESH_EVIDENCE_PARENT'
    scratch=ROOT.parent/'scratch'
    report['scratch_checks']={'exists':scratch.exists(),'symlink':scratch.is_symlink()}
    if scratch.exists() or scratch.is_symlink():raise activation.Closed('fresh hosted evidence parent required')
    scratch.mkdir(mode=0o700,exist_ok=False)
    report.update(status='HOSTED_PREPARED_NOT_EXECUTED',stage='HOSTED_PREPARED',run=NUMBER,license='SIL Open Font License 1.1')


def save_preparation(report,environment):
    # Public fixed booleans/hashes/stage only, never arbitrary exception text.
    parent=Path(environment['RUNNER_TEMP'])
    st=parent.lstat()
    if parent.resolve()!=parent or not parent.is_dir() or st.st_uid!=os.geteuid():raise activation.Closed('owned runner temp required')
    directory=parent/'template-browser-hosted-evidence';directory.mkdir(mode=0o700,exist_ok=False)
    raw=(json.dumps(report,sort_keys=True)+'\n').encode()
    if len(raw)>16384:raise activation.Closed('preparation record limit')
    with (directory/'hosted-preparation.json').open('xb') as stream:stream.write(raw)


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    os.umask(0o077)
    report={'status':'NOT_EXECUTED','stage':'HOST_GATE','host_admitted':False}
    if argv==['execute']:
        try:
            source,invocation=gate(os.environ)
            from scripts.template_upgrade_http_once import main as integration
            return integration(['--source',source,'--invocation',invocation],mode='BROWSER')
        except BaseException as error:
            print(json.dumps({'status':'FAIL','stage':'HOSTED_EXECUTE_ADMISSION','error_type':type(error).__name__}),flush=True);return 1
    try:
        if argv!=['prepare']:raise activation.Closed('fixed hosted action required')
        prepare(os.environ,report)
    except BaseException as error:
        report.update(status='FAIL',error_type=type(error).__name__,reason_code=REASONS.get(str(error),'UNCLASSIFIED_FAILURE'),errno=getattr(error,'errno',None) if isinstance(getattr(error,'errno',None),int) else None)
    if report['host_admitted']:
        try:save_preparation(report,os.environ)
        except BaseException as error:report.update(status='FAIL',diagnostic_write_error=type(error).__name__)
    print(json.dumps(report),flush=True)
    return 0 if report['status']=='HOSTED_PREPARED_NOT_EXECUTED' else 1


if __name__=='__main__':raise SystemExit(main())
