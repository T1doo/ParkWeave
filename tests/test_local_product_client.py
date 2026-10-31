"""Client transport failure fences; no browser acceptance claim."""
from pathlib import Path
import subprocess
import shutil
import pytest


def test_body_failure_and_identity_change_keep_original_submission_fenced():
    if not shutil.which('node'):
        pytest.skip('Node required for client transport contract checks')
    page = Path('src/parkweave/local_preparation_web.html').read_text()
    api = page[page.index('async function secretDigest('):page.index('\nasync function perform')]
    fingerprint = page[page.index('function canonical('):page.index("$('recover').onclick=")]
    check = r'''
const assert=require('node:assert/strict'), crypto=require('node:crypto').webcrypto;
const ParkWeavePending=require(process.cwd()+'/src/parkweave/local_command_pending.js');
let queued=Promise.resolve();const locks={request:(key,options,fn)=>{const next=queued.then(fn);queued=next.catch(()=>{});return next}};
const disk=new Map(),storage={getItem:k=>disk.get(k)??null,setItem:(k,v)=>disk.set(k,v),removeItem:k=>disk.delete(k)};
let credentialHash='b'.repeat(64),pendingJournal;
let epoch=1,bearer='PUBLIC_TEST_BEARER',actorScope={id:'a',park_id:'p',org_id:'o',role:'enterprise_operator'},unknown=null;
const original={...actorScope};pendingJournal=ParkWeavePending.journal(storage,'a'.repeat(64),actorScope,credentialHash,locks);
const path='/api/preparations/00000000-0000-0000-0000-000000000001/commands';
const body={action:'ADD_EVIDENCE',expected_revision:1,slot:'need_summary',text:' SYNTHETIC request ',source_kind:'DOCUMENT_EXCERPT',source_label:' SYNTHETIC v1 '};
let calls=0;
let fetch=async()=>{calls++;return {ok:true,status:200,json:async()=>{throw new Error('body stream interrupted')}}};
(async()=>{
 await assert.rejects(api(path,body,'00000000-0000-0000-0000-000000000002'));
 assert.equal(calls,1);assert.equal(unknown.request_key,'00000000-0000-0000-0000-000000000002');assert.deepEqual(unknown.actor,original);
 assert.equal(unknown.fingerprint,await evidenceFingerprint(path,body));
 const saved=unknown;
 const reopened=ParkWeavePending.journal(storage,'a'.repeat(64),actorScope,credentialHash,locks);
 assert.deepEqual(reopened.read(),saved);
 assert.equal(ParkWeavePending.journal(storage,'a'.repeat(64),{...actorScope,id:'other'},credentialHash,locks).read(),null);
 assert(![...disk.values()].join('').includes('SYNTHETIC request'));
 assert(![...disk.values()].join('').includes('PUBLIC_TEST_BEARER'));
 await assert.rejects(api(path,body,'00000000-0000-0000-0000-000000000003'));
 assert.equal(calls,1);
 await pendingJournal.settle(saved);unknown=null;calls=0;
 const digest=evidenceFingerprint;
 evidenceFingerprint=async(...args)=>{const result=await digest(...args);epoch++;bearer='CHANGED_PUBLIC_TEST_IDENTITY';return result};
 await assert.rejects(api(path,body,'never-send'));
 assert.equal(calls,0);assert.equal(unknown,null);
 const other=ParkWeavePending.journal(storage,'a'.repeat(64),actorScope,credentialHash,locks);
 const first=pendingJournal.prepare(path,'00000000-0000-0000-0000-000000000004','ADD_EVIDENCE',1,'c'.repeat(64),()=>{});
 const second=other.prepare(path,'00000000-0000-0000-0000-000000000005','ADD_EVIDENCE',1,'d'.repeat(64),()=>{});
 const raced=await Promise.allSettled([first,second]);
 assert.equal(raced.filter(x=>x.status==='fulfilled').length,1);
 assert.equal(pendingJournal.read().request_key,'00000000-0000-0000-0000-000000000004');
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
'''
    subprocess.run(['node', '-e', api + '\n' + fingerprint + '\n' + check], check=True,
                   capture_output=True, text=True)
