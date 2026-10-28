"""Client transport failure fences; no browser acceptance claim."""
from pathlib import Path
import subprocess
import shutil
import pytest


def test_body_failure_and_identity_change_keep_original_submission_fenced():
    if not shutil.which('node'):
        pytest.skip('Node required for client transport contract checks')
    page = Path('src/parkweave/local_preparation_web.html').read_text()
    api = page[page.index('async function api('):page.index('\nasync function perform')]
    fingerprint = page[page.index('function canonical('):page.index("$('recover').onclick=")]
    check = r'''
const assert=require('node:assert/strict'), crypto=require('node:crypto').webcrypto;
let epoch=1,bearer='PUBLIC_TEST_BEARER',actorScope={id:'a',park_id:'p',org_id:'o',role:'enterprise_operator'},unknown=null;
const original={...actorScope};
const path='/api/preparations/00000000-0000-0000-0000-000000000001/commands';
const body={action:'ADD_EVIDENCE',expected_revision:1,slot:'need_summary',text:' SYNTHETIC request ',source_kind:'DOCUMENT_EXCERPT',source_label:' SYNTHETIC v1 '};
let calls=0;
let fetch=async()=>{calls++;return {ok:true,status:200,json:async()=>{throw new Error('body stream interrupted')}}};
(async()=>{
 await assert.rejects(api(path,body,'original-key'));
 assert.equal(calls,1);assert.equal(unknown.key,'original-key');assert.deepEqual(unknown.actor,original);
 assert.equal(unknown.fingerprint,await evidenceFingerprint(path,body));
 unknown=null;calls=0;
 const digest=evidenceFingerprint;
 evidenceFingerprint=async(...args)=>{const result=await digest(...args);epoch++;bearer='CHANGED_PUBLIC_TEST_IDENTITY';return result};
 await assert.rejects(api(path,body,'never-send'));
 assert.equal(calls,0);assert.equal(unknown,null);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
'''
    subprocess.run(['node', '-e', api + '\n' + fingerprint + '\n' + check], check=True,
                   capture_output=True, text=True)
