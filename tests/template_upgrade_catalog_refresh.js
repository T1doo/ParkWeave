// Explicit offline GET/POST responses, whole shipped script; not HTTP/browser.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const source=fs.readFileSync(process.argv[2]||'src/parkweave/template_upgrade_web.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
class Element {
 constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.value='';this.textContent='';this.disabled=false;this.hidden=false;this.checked=false;this.href='';}
 append(e){this.children.push(e);if(this.tagName==='select'&&!this.value)this.value=e.value;}
 replaceChildren(...values){this.children=values;this.textContent='';this.value='';}
 get selectedOptions(){return this.children.filter(e=>e.value===this.value);}
}
function page(){
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id==='target'?'select':'div'));return elements.get(id);};
 const choices=['KEEP_CURRENT','REQUEST_RECHECK','ACK_COMPATIBLE'].map(choice=>Object.assign(new Element('button'),{dataset:{choice}}));
 const calls=[],responses=[];
 const context=vm.createContext({JSON,Error,URLSearchParams,encodeURIComponent,TextEncoder,Uint8Array,crypto:crypto.webcrypto,document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:()=>choices},fetch:async(path,options)=>{calls.push({path,method:options.method});assert(responses.length,'unexpected offline request');const answer=responses.shift();return {status:answer.status||200,ok:(answer.status||200)<400,json:async()=>answer.body};}});
 vm.runInContext(source,context);get('token').value='SYNTHETIC_PLACEHOLDER';get('token').oninput();get('instance').value='synthetic-instance';get('instance').oninput();
 return {get,choices,calls,responses,context};
}
const catalog=id=>({body:{templates:[{name:'Synthetic target',release_id:id,release_sha256:'a'.repeat(64)}]}});
const inspection={check:{classification:'NEEDS_RECHECK',allowed_choices:['KEEP_CURRENT'],original_content_version:1,target_content_version:2,original_source_revision:'1',target_source_revision:'2',original_release_id:'SYNTHETIC_R1',target_release_id:'SYNTHETIC_R2',changes:['SYNTHETIC_OLD_CHECK']},revision:0,application:{eligible:false,effective_release_id:'SYNTHETIC_R1',blockers:[],affected:[],preserved:[]}};
async function checked(){const p=page();p.responses.push(catalog('SYNTHETIC_R2'));await p.get('catalog').onclick();p.responses.push({body:inspection});await p.get('check').onclick();assert(p.get('result').textContent.includes('SYNTHETIC_OLD_CHECK'));return p;}
(async()=>{
 const p=await checked();p.get('apply-confirm').checked=true;p.get('apply-reason').value='SYNTHETIC prior target reason';p.get('apply-receipt').textContent='SYNTHETIC prior target receipt';p.get('original-case').hidden=false;p.get('original-case').href='/?template_instance=synthetic-instance';
 p.responses.push(catalog('SYNTHETIC_R3'));await p.get('catalog').onclick();assert.equal(p.get('target').value,'SYNTHETIC_R3');
 for(const id of ['result','receipt','application','apply-receipt'])assert.equal(p.get(id).textContent,'','old '+id+' survived successful target refresh');
 assert.equal(p.get('apply-reason').value,'');assert.equal(p.get('apply-confirm').checked,false);assert.equal(p.get('original-case').hidden,true);assert.equal(p.get('original-case').href,'');assert(p.get('apply').disabled);assert(vm.runInContext('inspection===null&&pending===null&&!busy',p.context));assert(p.calls.every(c=>c.method==='GET'));assert.equal(p.calls.length,3);
 console.log('PASS refreshed target clears previous check and confirmation display');
 const q=await checked();q.get('reason').value='SYNTHETIC choice';q.responses.push({status:500,body:{detail:'SYNTHETIC unknown'}});await q.choices[0].onclick();assert(vm.runInContext('pending!==null',q.context));const key=q.get('key').value,before=q.calls.length;
 await q.get('catalog').onclick();assert.equal(q.calls.length,before);assert.equal(q.get('key').value,key);assert(vm.runInContext('pending.key===document.getElementById("key").value',q.context));assert(q.get('catalog').disabled);
 console.log('PASS unknown choice blocks refresh and preserves original key');
 const r=await checked();const old=r.get('result').textContent;r.responses.push({status:503,body:{detail:'SYNTHETIC unavailable'}});await r.get('catalog').onclick();assert.equal(r.get('target').value,'SYNTHETIC_R2');assert.equal(r.get('result').textContent,old);assert(r.get('error').textContent.length>0);assert(vm.runInContext('inspection!==null&&!busy',r.context));
 console.log('PASS failed refresh retains matching target and exposes failure');
 const empty=await checked();empty.responses.push({body:{templates:[]}});await empty.get('catalog').onclick();assert.equal(empty.get('target').value,'');assert.equal(empty.get('result').textContent,'');assert.equal(empty.get('receipt').textContent,'');assert(empty.get('check').disabled);assert(vm.runInContext('inspection===null&&pending===null&&!busy',empty.context));
 console.log('PASS empty successful catalog clears prior inspection and disables check');
 const late=await checked();late.responses.push(catalog('SYNTHETIC_OLD_RESPONSE'));
 // Controlled fault exactly after the original call() validated its response,
 // before its caller resumes. This seam is not a real browser timing result.
 late.context.handoffHook=()=>{
  late.get('token').value='SYNTHETIC_NEW_IDENTITY';late.get('token').oninput();late.get('instance').value='synthetic-new-instance';late.get('instance').oninput();const option=new Element('option');option.value='SYNTHETIC_NEW_TARGET';late.get('target').append(option);late.get('result').textContent='SYNTHETIC_NEW_VIEW';late.get('key').value='SYNTHETIC_NEW_UNKNOWN_KEY';vm.runInContext("pending={kind:'choice',key:'SYNTHETIC_NEW_UNKNOWN_KEY'};buttons()",late.context);
 };vm.runInContext("const originalCallForHandoff=call;call=async(...args)=>{const value=await originalCallForHandoff(...args);if(args[1]==='/api/template-consumer/catalog')handoffHook();return value;};",late.context);await late.get('catalog').onclick();assert.equal(late.get('target').value,'SYNTHETIC_NEW_TARGET');assert.equal(late.get('result').textContent,'SYNTHETIC_NEW_VIEW');assert.equal(late.get('key').value,'SYNTHETIC_NEW_UNKNOWN_KEY');assert(vm.runInContext("pending.key==='SYNTHETIC_NEW_UNKNOWN_KEY'",late.context));assert(late.get('catalog').disabled);
 console.log('PASS stale response at promise handoff preserves new identity unknown state');
})().catch(e=>{console.error(e);process.exitCode=1;});
