// Entire shipped script, real loopback HTTP, unfinished error bodies; mechanical DOM.
// No application database, browser, credentials, or external service is used.
const fs=require('node:fs'),vm=require('node:vm'),http=require('node:http');
const assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2]||'src/parkweave/web.html','utf8');
const source=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
// Browser mechanics follow the existing whole-page CaseStep test support.
class Element{
 constructor(tag='div'){
  this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this.value='';
  this.hidden=true;this.disabled=false;this.checked=false;this.listeners={};
  const classes=new Set();this.classList={add:(...xs)=>xs.forEach(x=>classes.add(x)),
   remove:(...xs)=>xs.forEach(x=>classes.delete(x)),contains:x=>classes.has(x),
   toggle:(x,force)=>{const on=force===undefined?!classes.has(x):!!force;if(on)classes.add(x);else classes.delete(x);return on;}};
  const named={};this.elements=new Proxy([],{get:(a,key)=>key in a?a[key]:(named[key]??=new Element('input'))});
 }
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;this.textContent='';}
 get options(){return this.children.filter(e=>e.tagName==='option');}
 get selectedOptions(){return this.options.filter(e=>e.value===this.value);}
 get firstChild(){return this.children[0];}get firstElementChild(){return this.children[0];}
 addEventListener(name,handler){(this.listeners[name]??=[]).push(handler);}
 reset(){}setAttribute(){}removeAttribute(){}closest(){return null;}querySelectorAll(){return [];}
 scrollIntoView(){}focus(){}select(){}remove(){}click(){return this.onclick?.();}
}
function page(base){
 const elements=new Map(),storage={};
 for(const match of html.split('<script')[0].matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)){
  const attrs=match[2],id=attrs.match(/\bid=["']([^"']+)["']/)?.[1];
  if(!id&&!/\bdata-/.test(attrs))continue;
  const e=new Element(match[1].toLowerCase());e.id=id||'anonymous-'+elements.size;
  for(const d of attrs.matchAll(/\bdata-([\w-]+)=["']([^"']*)["']/g))e.dataset[d[1].replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=d[2];
  e.hidden=/\bhidden\b/.test(attrs);e.disabled=/\bdisabled\b/.test(attrs);elements.set(e.id,e);
 }
 const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const walk=e=>[e,...e.children.filter(x=>typeof x==='object').flatMap(walk)];
 const query=selector=>[...elements.values()].flatMap(walk).filter(e=>selector.split(',').some(s=>{
  if(['button','form'].includes(s))return e.tagName===s;
  const m=s.match(/^\[data-([\w-]+)\]$/);return m&&Object.hasOwn(e.dataset,m[1].replace(/-([a-z])/g,(_,c)=>c.toUpperCase()));
 }));
 const localStorage=new Proxy({getItem:k=>storage[k]??null,setItem:(k,v)=>storage[k]=v,removeItem:k=>delete storage[k]},
  {ownKeys:()=>Object.keys(storage),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});
 const context=vm.createContext({console,Date,JSON,Map,Set,WeakMap,Number,String,Error,TextEncoder,Blob,URL,URLSearchParams,encodeURIComponent,
  crypto:require('node:crypto').webcrypto,localStorage,setTimeout:()=>1,clearTimeout(){},
  document:{getElementById:$,createElement:t=>new Element(t),querySelectorAll:query,body:new Element('body'),addEventListener(){},execCommand:()=>false},
  window:{addEventListener(){}},fetch:(path,options)=>fetch(base+path,options)});
 vm.runInContext(source,context,{timeout:5000});$('token').value='SYNTHETIC_HTTP_ONLY';return context;
}
const notice={event_id:'A',preparation_id:'P-A',dispatch_id:'D-A',revision:1,
 action:'OFFER',delivered_at:'SYNTHETIC',historical:false,open_requested_at:'SYNTHETIC',read_at:null};
const results=[];
async function check(status){
 const requests=[],unfinished=[];
 const server=http.createServer((req,res)=>{
  requests.push({path:req.url,method:req.method});req.resume();
  if(req.method==='POST'){
   res.writeHead(status,{'Content-Type':'application/json','Content-Length':'1024'});
   res.flushHeaders();unfinished.push(res); // Intentionally never send the body.
  }else if(req.url==='/api/dispatch-notices/A'){
   res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({notice}));
  }else{res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 try{
  const context=page(base);
  await vm.runInContext("loadNotice('A').catch(noticeError)",context,{timeout:5000});
  vm.runInContext("preparationView={private:true};dispatchView={private:true};receiptView={private:true};",context);
  let timer;
  try{await Promise.race([
   vm.runInContext("$('notice-read').onclick()",context,{timeout:5000}),
   new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('refusal waited for unfinished body')),2000);}),
  ]);}finally{clearTimeout(timer);}
  assert.equal(unfinished.length,1);assert.equal(unfinished[0].writableEnded,false);
  assert.equal(vm.runInContext("noticeView===null&&noticeContext===null&&noticeId===null&&$('notice-detail').hidden&&preparationView===null&&dispatchView===null&&receiptView===null",context),true);
  assert.match(vm.runInContext("$('notice-error').textContent",context),/刷新/);
  const count=requests.length;
  await vm.runInContext("noticeCommand('MARK_READ').catch(noticeError)",context);
  assert.equal(requests.length,count);
  assert.deepEqual(requests,[{path:'/api/dispatch-notices/A',method:'GET'},
   {path:'/api/dispatch-notices/A/commands',method:'POST'}]);
  results.push({status,result:'PASS',requests:requests.length,error_body_finished:false,
   scope:'WHOLE_PAGE_JS_REAL_LOOPBACK_HTTP_MECHANICAL_DOM'});
 }finally{
  const closed=new Promise(resolve=>server.close(resolve));server.closeAllConnections();await closed;
 }
}
(async()=>{for(const status of [401,403])await check(status);process.stdout.write(JSON.stringify(results)+'\n');})()
 .catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
