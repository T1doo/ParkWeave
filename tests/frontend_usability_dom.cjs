// Whole shipped pages, jsdom semantics only: no browser/layout/pixel claim.
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function page(name){
 const ref=process.env.PARKWEAVE_TEST_REF;if(ref)assert(/^[a-f0-9]{40}$/.test(ref));const html=ref?require('node:child_process').execFileSync('git',['show',ref+':src/parkweave/'+name],{encoding:'utf8',maxBuffer:8*1024*1024}):fs.readFileSync('src/parkweave/'+name,'utf8'),dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only'}),w=dom.window,d=w.document,queries=[],errors=[],requests=[];
 w.matchMedia=query=>{const listeners=[];const media={matches:false,media:query,addEventListener(type,listener){listeners.push(listener);},change(value){this.matches=value;for(const listener of listeners)listener({matches:value});}};queries.push(media);return media;};
 w.HTMLElement.prototype.scrollIntoView=function(){};w.fetch=(...args)=>{requests.push(args);throw Error('Unexpected network request');};w.addEventListener('error',event=>errors.push(String(event.error)));
 const compact=name!=='web.html',probe=compact?`window.probe={snapshot:value=>{current=value;selected=value.preparation.id;role='enterprise_operator';}};`:`window.probe={snapshot:value=>{preparationView=value;preparationId=value.preparation.id;}};`;
 w.eval(html.match(/<script>([\s\S]*?)<\/script>/)[1]+'\n'+probe);d.dispatchEvent(new w.Event('DOMContentLoaded'));await tick();const get=id=>d.getElementById(id);
 const snapshot={preparation:{id:'SYNTHETIC_CURRENT',case_id:'SYNTHETIC_CASE',state:'IN_PREPARATION'},current_materials:[{slot:'need_summary',version:1,text:'SYNTHETIC 当前授权材料',source_kind:'USER_STATEMENT',source_label:'合成本人说明',authenticity:'UNVERIFIED'}]};w.probe.snapshot(snapshot);
 if(compact){get('workspace').hidden=false;get('detail-card').hidden=false;get('detail').hidden=false;get('evidence-form').hidden=false;}else get('prep-detail').hidden=false;
 const list=get(compact?'materials':'prep-materials'),row=d.createElement('article');row.className=compact?'material':'';row.append(d.createElement('strong'),d.createElement('p'));row.lastChild.textContent=snapshot.current_materials[0].text;list.replaceChildren(row);await tick();await tick();
 return {dom,w,d,get,list,row,queries,compact,requests,errors,fire:(node,type)=>node.dispatchEvent(new w.Event(type,{bubbles:true}))};
}
async function main(){
 const results=[],failures=[];
 async function scenario(name,run){try{await run();results.push({scenario:name,status:'PASS'});}catch(error){failures.push({scenario:name,error:error.message});}}
 for(const name of ['web.html','local_preparation_web.html']){
  let p=await page(name),{get,w,d}=p,preview=get('park-material-preview');
  const trigger=()=>p.list.querySelector('.design-preview-trigger');trigger().click();const close=preview.querySelector('button');assert.equal(d.activeElement,close);
  const breakpoint=p.queries.find(query=>query.media.includes('1759'));const field=get(p.compact?'material-text':'prep-text');field.disabled=false;field.focus();assert.equal(d.activeElement,field);breakpoint.change(true);
  await scenario(name+': wide to single reader moves focus into the reader',()=>{assert.equal(get('park-main')?.inert??d.querySelector('main').inert,true);assert(preview.contains(d.activeElement));});
  // Content replacement removes the original trigger; the existing filter is the return target.
  close.focus();const replacement=d.createElement('article');replacement.className=p.compact?'material':'';replacement.append(d.createElement('strong'),d.createElement('p'));replacement.lastChild.textContent='SYNTHETIC 新版本材料';p.list.replaceChildren(replacement);await tick();await tick();
  await scenario(name+': stale reader closes and returns to visible material filter',()=>{assert.equal(preview.hidden,true);assert.equal(d.activeElement,get('park-material-filter'));assert(d.querySelector('.design-preview-notice').textContent.includes('变化'));});
  breakpoint.change(false);trigger().click();field.focus();p.list.querySelector('p').textContent='SYNTHETIC 再次更新';await tick();await tick();
  await scenario(name+': background editor focus survives a stale non-modal reader',()=>{assert.equal(preview.hidden,true);assert.equal(d.activeElement,field);});
  trigger().click();p.list.replaceChildren();await tick();await tick();
  await scenario(name+': empty material list returns reader focus to its status',()=>{assert.equal(preview.hidden,true);assert.equal(d.activeElement,d.querySelector('.design-preview-notice'));assert(d.activeElement.textContent);assert.equal(preview.querySelector('pre').textContent,'');});
  // Native validation focus was queued before a reset/identity clear; it must not steal credential focus.
  const goal=get(p.compact?'material-text':'prep-goal');goal.disabled=false;goal.value='';goal.required=true;goal.dispatchEvent(new w.Event('invalid'));const token=get(p.compact?'role':'token');token.focus();p.fire(token,'input');await tick();
  await scenario(name+': cleared validation cannot steal credential focus',()=>assert.equal(d.activeElement,token));
  await tick();await tick();p.dom.window.close();
  p=await page(name);({get,w,d}=p);const draft=get(p.compact?'material-text':'prep-goal');draft.disabled=false;draft.focus();draft.value='尚未提交的中文输入';p.fire(draft,'input');const target=p.compact?get('nav-workspace'):d.querySelector('[data-tab=resource]');target.click();const dialog=d.querySelector('.design-confirm-dialog');assert.equal(dialog.open,true);
  await scenario(name+': confirmation exposes the actual explanation',()=>{const id=dialog.getAttribute('aria-describedby');assert(id);assert(d.getElementById(id)?.textContent.includes('本页有已编辑的输入'));});
  dialog.querySelector('button').click();const currentToken=get(p.compact?'role':'token');currentToken.focus();p.fire(currentToken,'input');await tick();
  await scenario(name+': closed confirmation never reuses its old focus target',()=>assert.equal(d.activeElement,currentToken));
  if(!p.compact){get('resource').hidden=false;const hold={id:'SYNTHETIC_PRIVATE_HOLD',resource_name:'合成私有设备',purpose:'合成用途',state:'HELD',resource_id:'SYNTHETIC_RESOURCE',resource_revision:1,quantity:1,starts_at:'2026-11-03T09:00:00Z',ends_at:'2026-11-03T10:00:00Z',expires_at:'2026-11-03T08:00:00Z'};w.renderResourceHold(hold,get('resource-current'));const release=get('resource-current').querySelector('[data-resource-action=release]');let sent=0;release.onclick=()=>sent++;release.click();assert(dialog.open);assert(dialog.textContent.includes(hold.id));w.resourceError({status:403,message:'SYNTHETIC permission revoked'});await tick();await tick();
   await scenario(name+': disappearing confirmation object cancels and clears its private copy',()=>{assert.equal(dialog.open,false);assert(!dialog.textContent.includes(hold.id));dialog.querySelector('button:last-child').click();assert.equal(sent,0);});
  }
  await scenario(name+': all scenarios preserve no-request boundary',()=>{assert.equal(p.requests.length,0);assert.deepEqual(p.errors,[]);});
  await tick();await tick();p.dom.window.close();
 }
 console.log(JSON.stringify({kind:'jsdom-only',results,failures,browser_runs:0,pixel_engine:false},null,2));assert.equal(failures.length,0,'usability scenarios failed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
