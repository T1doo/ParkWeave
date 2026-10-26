// Original shipped controller + DOM stand-in. Actual responses come from the
// parent's exact localhost HTTP transport. No real token enters this process.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),readline=require('readline'),crypto=require('crypto');
let configured=false,firstResolve,resume,nonce=0;const pending=new Map(),first=new Promise(r=>firstResolve=r);
const input=readline.createInterface({input:process.stdin});
input.on('line',line=>{
 try{assert(Buffer.byteLength(line)<=1024*1024);const value=JSON.parse(line);
  if(!configured){configured=true;firstResolve(value);}else if(value.type==='REVOKED'){assert(resume);resume();resume=null;}
  else{const target=pending.get(value.id);assert(target);pending.delete(value.id);target(value);}
 }catch{console.error('CLIENT_FRAME_FAILED');process.exit(1);}
});
function send(value){process.stdout.write(JSON.stringify(value)+'\n');}
async function fetchAPI(path,options={}){assert((options.method||'GET')==='GET');const id=++nonce;const answer=new Promise(r=>pending.set(id,r));send({type:'request',id,path,options});const r=await answer;return {status:r.status,ok:r.status>=200&&r.status<300,json:async()=>r.body};}
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.value='';this.textContent='';this.disabled=false;this.hidden=false;this.checked=false;this.href='';}
 append(e){this.children.push(e);if(this.tagName==='select'&&!this.value)this.value=e.value;}
 replaceChildren(...values){this.children=values;this.value='';}
 get selectedOptions(){return this.children.filter(x=>x.value===this.value);}
}
(async()=>{
 const params=await first;assert(Object.keys(params).sort().join(',')==='instance,page,page_sha256');
 const bytes=fs.readFileSync(params.page);assert(crypto.createHash('sha256').update(bytes).digest('hex')===params.page_sha256);
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id==='target'?'select':'div'));return elements.get(id);};
 const choices=['KEEP_CURRENT','REQUEST_RECHECK','ACK_COMPATIBLE'].map(choice=>{const e=new Element('button');e.dataset.choice=choice;return e;});
 const context=vm.createContext({JSON,Error,URLSearchParams,encodeURIComponent,TextEncoder,Uint8Array,crypto:crypto.webcrypto,document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:()=>choices},fetch:fetchAPI});
 const script=bytes.toString('utf8').match(/<script>([\s\S]*?)<\/script>/);assert(script);vm.runInContext(script[1],context);
 get('token').value='SYNTHETIC_HTTP_SESSION';get('token').oninput();get('instance').value=params.instance;get('instance').oninput();
 await get('catalog').onclick();assert(get('target').children.length===1);await get('check').onclick();
 assert(vm.runInContext('inspection!==null&&pending===null&&!busy',context));assert(get('result').textContent.length>0);assert(get('apply').disabled);
 const revoked=new Promise(r=>resume=r);send({type:'CHECKED'});await revoked;
 await get('check').onclick();assert(vm.runInContext('inspection===null&&pending===null&&!busy',context));
 assert(get('result').textContent==='');assert(get('receipt').textContent==='');assert(get('application').textContent==='');assert(get('target').children.length===0);assert(get('apply').disabled);assert(get('error').textContent.includes('无权'));
 process.stdout.write(JSON.stringify({type:'DONE'})+'\n',()=>process.exit(0));
})().catch(()=>{console.error('CLIENT_FAILED');process.exit(1);});
