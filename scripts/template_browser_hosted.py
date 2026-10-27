"""Single run49 hosted bootstrap. Existing run48 assets/terms, no new runtime.

Dependency/font staging is outside the separate360s integration clock and
inside the existing3min bootstrap /10min job. This never activates a contract.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from scripts import template_http_activation as activation
from scripts import template_browser_client as client
from scripts.fictional_park_font_once import ASSETS,COMMIT,DIRECTORY,stage_asset,verified_font

ROOT=Path(__file__).resolve().parents[1]
NUMBER='49'
REF='refs/heads/'+activation.BRANCH


def gate(environment):
    expected={'GITHUB_REPOSITORY':'T1doo/ParkWeave','GITHUB_REF':REF,
              'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1',
              'GITHUB_RUN_NUMBER':NUMBER,'RUNNER_ENVIRONMENT':'github-hosted',
              'RUNNER_OS':'Linux','PW_PUBLIC':'true'}
    if any(environment.get(k)!=v for k,v in expected.items()):raise activation.Closed('single public hosted Linux invocation required')
    if any(k.startswith('PARKWEAVE_') for k in environment):raise activation.Closed('inherited business configuration refused')
    source=environment.get('GITHUB_SHA','')
    if re.fullmatch('[a-f0-9]{40}',source) is None:raise activation.Closed('exact source required')
    raw=json.loads(activation.regular_bytes(ROOT/activation.PROFILES['BROWSER'],2048)[0])
    approval=activation.load(raw.get('invocation'),'BROWSER')
    activation.verify_source(source,approval,time.monotonic())
    return source,approval.invocation


def prepare(environment):
    source,invocation=gate(environment)
    # Standard runner-installed Chrome, never Playwright browser installation.
    st=client.CHROME.lstat()
    if client.CHROME.is_symlink() or not client.CHROME.is_file() or st.st_uid not in (0,os.geteuid()) or st.st_mode&0o022 or not st.st_mode&0o111:raise activation.Closed('standard runner Chrome required')
    if DIRECTORY!=ROOT/client.FONT_RELATIVE:raise activation.Closed('fixed approved cache mismatch')
    DIRECTORY.mkdir(mode=0o700,exist_ok=False)
    assets={};started=time.monotonic()
    for asset in ASSETS:assets[asset[0]]=stage_asset(asset,DIRECTORY,started+45)
    (DIRECTORY/'font-source.json').write_text(json.dumps({'commit':COMMIT,'license':'SIL Open Font License 1.1','assets':assets})+'\n')
    verified_font(required=True)
    client.preflight(ROOT,None)
    # Existing parent path required by the reviewed evidence root; never shared
    # DB data, and never choose another path when an existing object mismatches.
    scratch=ROOT.parent/'scratch'
    if scratch.exists() or scratch.is_symlink():raise activation.Closed('fresh hosted evidence parent required')
    scratch.mkdir(mode=0o700,exist_ok=False)
    print(json.dumps({'status':'HOSTED_PREPARED_NOT_EXECUTED','source':source,'run':NUMBER,'font':assets,'license':'SIL Open Font License 1.1'}),flush=True)


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    os.umask(0o077)
    try:
        if argv==['prepare']:prepare(os.environ);return 0
        if argv==['execute']:
            source,invocation=gate(os.environ)
            from scripts.template_upgrade_http_once import main as integration
            return integration(['--source',source,'--invocation',invocation],mode='BROWSER')
        raise activation.Closed('fixed hosted action required')
    except BaseException as error:
        print(json.dumps({'status':'FAIL','stage':'HOSTED_ADMISSION_OR_PREPARATION','error_type':type(error).__name__}),flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
