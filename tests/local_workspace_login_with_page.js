/* Whole original page + login adapter, offline DOM mechanism only. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const helper=fs.readFileSync('tests/ordinary_case_step_real_html.js','utf8');
const fragment=helper.slice(helper.indexOf('const html ='),helper.indexOf('(async()=>'));
const {page,Element}=new Function('require','fs','vm','assert','control',fragment+';return {page,Element};')(require,fs,vm,assert,()=>{throw Error('no external control');});
Element.prototype.dispatchEvent=function(e){this['on'+e.type]?.(e);for(const handler of this.listeners[e.type]||[])handler(e);return true;};
(async()=>{
 const storage={},p=page({token:''},storage,[],{}),requests=[];
 p.context.Event=class{constructor(type){this.type=type;}};
 p.context.navigator={locks:{request:async(key,opt,fn)=>fn()}};
 p.context.location={assign:()=>{throw Error('no navigation expected');}};
 p.context.fetch=async(path,options)=>{requests.push({path,options});assert.equal(path,'/api/local/session');return {ok:true,status:200,json:async()=>({bearer:'PUBLIC_SYNTHETIC_TEST',installation_id:'a'.repeat(64),actor:{id:'PUBLIC-OWNER',park_id:'PUBLIC-PARK',org_id:'PUBLIC-ORG',role:'enterprise_operator'}})};};
 vm.runInContext(fs.readFileSync('src/parkweave/local_command_pending.js','utf8'),p.context);
 vm.runInContext(fs.readFileSync('src/parkweave/local_workspace_login.js','utf8'),p.context);
 p.$('run').value='PRIOR_PRIVATE_VIEW';p.$('result').textContent='PRIOR_PRIVATE_RESULT';
 p.$('local-workspace-account').value='enterprise';p.$('local-workspace-password').value='PUBLIC_TEST_PASSWORD';
 await p.$('local-workspace-login').onsubmit({preventDefault(){}});
 assert.equal(p.$('token').value,'PUBLIC_SYNTHETIC_TEST',p.$('local-workspace-status').textContent);
 assert.equal(p.$('run').value,'');assert.equal(p.$('result').textContent,'');
 p.run("prepCommandPending={key:'public-existing-original-key',stage:'UNKNOWN'}");
 await p.$('local-workspace-logout').click();assert.equal(p.$('token').value,'PUBLIC_SYNTHETIC_TEST');assert(p.run('prepCommandPending')!==null);
 p.run('prepCommandPending=null');await p.$('local-workspace-logout').click();assert.equal(p.$('token').value,'');assert.equal(p.context.document.body.dataset.localWorkspace,'locked');
 assert.equal(requests.length,1);assert.deepEqual(Object.keys(storage),[]);
 console.log('PASS original whole page input cleanup + UNKNOWN logout guard; no business requests');
})().catch(e=>{console.error(e.stack);process.exit(1);});
