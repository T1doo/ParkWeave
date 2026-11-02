// Shipped HTML semantics only. No animation frames, layout, browser or pixel claim.
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function main(){
 const results=[],failures=[];
 async function check(name,run){try{await run();results.push(name);}catch(error){failures.push({name,error:error.message});}}
 for(const name of ['web.html','local_preparation_web.html']){
  const ref=process.env.PARKWEAVE_TEST_REF;if(ref)assert(/^[a-f0-9]{40}$/.test(ref));
  const html=ref?require('node:child_process').execFileSync('git',['show',ref+':src/parkweave/'+name],{encoding:'utf8',maxBuffer:8*1024*1024}):fs.readFileSync('src/parkweave/'+name,'utf8');
  const dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only'}),w=dom.window,d=w.document,queries=[],errors=[],requests=[];
  let hidden=false,cancelled=0,enumerated=0;const cancelledAfterClose=[];
  Object.defineProperty(d,'hidden',{get:()=>hidden});d.getAnimations=()=>{enumerated++;cancelledAfterClose.push(d.getElementById('park-material-preview')?.hidden);return [{cancel(){cancelled++;}}];};
  w.matchMedia=query=>{const listeners=[],media={matches:query==='(max-width:768px)',media:query,addEventListener(type,fn){listeners.push(fn);},change(value){this.matches=value;for(const fn of listeners)fn({matches:value});}};queries.push(media);return media;};
  w.HTMLElement.prototype.scrollIntoView=function(){};w.fetch=(...args)=>{requests.push(args);throw Error('Unexpected request');};w.addEventListener('error',event=>errors.push(String(event.error)));
  w.eval(html.match(/<script>([\s\S]*?)<\/script>/)[1]);d.dispatchEvent(new w.Event('DOMContentLoaded'));await tick();
  const get=id=>d.getElementById(id),compact=name!=='web.html',main=d.querySelector('main'),motion=queries.find(query=>query.media.includes('prefers-reduced-motion'));
  await check(name+': hidden/pagehide cancel active effects; visible/pageshow never replay',()=>{
   d.dispatchEvent(new w.Event('visibilitychange'));assert.equal(cancelled,0);
   hidden=true;d.dispatchEvent(new w.Event('visibilitychange'));assert.equal(cancelled,1);
   hidden=false;d.dispatchEvent(new w.Event('visibilitychange'));w.dispatchEvent(new w.Event('pageshow'));assert.equal(cancelled,1);
   w.dispatchEvent(new w.Event('pagehide'));assert.equal(cancelled,2);assert.equal(enumerated,2);
  });
  hidden=false;
  const steps=d.createElement('div');steps.className='steps';steps.innerHTML='<span class="current">SYNTHETIC 当前阶段</span><span>SYNTHETIC 等待阶段</span>';main.append(steps);await tick();await tick();
  const toggle=steps.previousElementSibling;assert(toggle.classList.contains('design-stage-toggle'));
  toggle.click();
  await check(name+': only explicit narrow-stage expansion opts into feedback',()=>{assert(steps.classList.contains('design-stage-reveal'));assert.equal(toggle.getAttribute('aria-expanded'),'true');assert.equal(steps.querySelector('.design-stage-visible').textContent,'SYNTHETIC 当前阶段');});
  await check(name+': reduced motion cancels effects and clears pending stage feedback',()=>{
   const before=cancelled;assert(motion);motion.change(true);assert.equal(cancelled,before+1);assert(!steps.classList.contains('design-stage-reveal'));
   motion.change(false);assert.equal(cancelled,before+1);assert(!steps.classList.contains('design-stage-reveal'));
   toggle.click();toggle.click();assert(steps.classList.contains('design-stage-reveal'));
   hidden=true;d.dispatchEvent(new w.Event('visibilitychange'));assert(!steps.classList.contains('design-stage-reveal'));hidden=false;
  });
  hidden=false;
  const list=get(compact?'materials':'prep-materials');for(let node=list;node;node=node.parentElement)node.hidden=false;
  const row=d.createElement('article');row.className=compact?'material':'';row.innerHTML='<strong>SYNTHETIC 材料 v1</strong><p>SYNTHETIC 授权正文</p>';list.replaceChildren(row);await tick();await tick();
  const preview=get('park-material-preview'),trigger=row.querySelector('.design-preview-trigger');assert(trigger);trigger.click();
  await check(name+': exit enhancement never delays private cleanup or layer isolation',()=>{
   assert.equal(preview.inert,false);assert.equal(preview.hasAttribute('aria-hidden'),false);assert.equal(preview.hidden,false);
   preview.querySelector('button').click();assert.equal(preview.hidden,true);assert.equal(preview.inert,true);assert.equal(preview.getAttribute('aria-hidden'),'true');assert.equal(preview.querySelector('pre').textContent,'');assert.equal(preview.querySelector('h2').textContent,'');
   trigger.click();assert.equal(preview.inert,false);assert.equal(preview.hasAttribute('aria-hidden'),false);
   w.dispatchEvent(new w.Event('pagehide'));assert.equal(preview.hidden,true);assert.equal(cancelledAfterClose.at(-1),true,'cancel effects after closing handlers have run');
  });
  if(!compact){
   get('service-case-plan-detail').hidden=false;get('service-plan-summary').textContent='SYNTHETIC 已读计划';await tick();
   const review=d.querySelector('.design-plan-review'),open=[...get('service-case-plan-detail').querySelectorAll('button')].find(button=>button.textContent==='核对当前已读方案');open.click();
   await check(name+': grouped review becomes inaccessible and empty synchronously on source change',()=>{
    assert.equal(review.hidden,false);assert.equal(review.inert,false);assert.equal(review.hasAttribute('aria-hidden'),false);
    get('token').dispatchEvent(new w.Event('input',{bubbles:true}));assert.equal(review.hidden,true);assert.equal(review.inert,true);assert.equal(review.getAttribute('aria-hidden'),'true');assert.equal(review.textContent,'');
   });
  }
  assert.equal(requests.length,0);assert.deepEqual(errors,[]);await tick();dom.window.close();
 }
 console.log(JSON.stringify({kind:'jsdom-only',results,failures,network_requests:0,browser_runs:0,pixel_engine:false},null,2));assert.equal(failures.length,0);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
