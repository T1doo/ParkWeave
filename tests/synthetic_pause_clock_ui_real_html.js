// Reuse the original complete-HTML mechanical DOM/HTTP driver, not its scenarios.
const fs = require('fs');
const original = fs.readFileSync('tests/ordinary_case_step_real_html.js','utf8');
const harness = original.slice(0,original.indexOf('(async()=>{'));
const scenario = String.raw`
(async()=>{
 const config=await initialized,calls=[],storage={},transport={};diagnostics={calls};
 const p=page({...config,token:config.reviewer},storage,calls,transport),$=p.$;
 async function open(q,role='park_specialist'){
  q.$('existing-preparation-id').value=config.id;await q.$('existing-preparation-form').onsubmit({preventDefault(){}});check(q.run('preparationView')?.preparation.id===config.id,'actual existing-record form opens exact current authorized preparation');
  const before=calls.length;await q.$('handling-deadline-read').click();
  check(!calls.slice(before).some(c=>c.path.endsWith('/synthetic-pause-clock')),'original read does not discover capability automatically');
  if(config.mode!=='no-cap')await q.$('synthetic-pause-open').click();
 }
 if(config.mode==='no-cap'){
  await open(p);check($('synthetic-pause-open').hidden&&$('synthetic-pause-panel').hidden&&$('synthetic-pause-form').hidden,'ordinary reviewer and readonly source have no pause UI');
 }else{
  if(['missing-calendar','wrong-case','wrong-revision','wrong-actor'].includes(config.mode)){
   const real=p.run('fetch');p.context.fetch=async(path,options)=>{const response=await real(path,options);if(path.endsWith('/synthetic-pause-clock')){const x=await response.json();if(config.mode==='missing-calendar')delete x.calendar_ref;else if(config.mode==='wrong-case')x.case_id='00000000-0000-4000-8000-000000009999';else if(config.mode==='wrong-revision')x.preparation_revision++;else x.actor_id='ordinary-reviewer-is-not-authority';return {ok:true,status:200,json:async()=>x};}return response;};
   await open(p);check($('synthetic-pause-panel').hidden&&$('synthetic-pause-form').hidden&&p.run('pauseClockView')===null,'malformed current scope/source never enables UI');
  }else{
   await open(p);check(!$('synthetic-pause-panel').hidden&&!$('synthetic-pause-form').hidden,'exact existing fixture exposes controls');
   check(html.includes('不是现实园区SLA'),'explicit synthetic scope shipped in original HTML');
   const before=calls.length;await $('synthetic-pause-start').click();check(calls.length===before,'missing confirmation/note sends no request');
   $('synthetic-pause-note').value='SYNTHETIC UI <img src=x onerror=bad> explicit wait';$('synthetic-pause-confirm').checked=true;
   if(config.mode==='not-observed'){
    const real=p.run('fetch');let dropped=false;p.context.fetch=async(path,options)=>{if(!dropped&&options?.method==='POST'&&path.endsWith('/synthetic-pause-clock')){dropped=true;throw Error('OWNED_UI_FAULT_BEFORE_SEND');}return real(path,options);};
   }
   if(['lost-cold','advanced-history'].includes(config.mode))transport.dropPath='/synthetic-pause-clock';
   if(config.mode.startsWith('late-')){
    let held;const seen=new Promise(resolve=>held=resolve);transport.held=held;transport.release=new Promise(resolve=>transport.resume=resolve);
    if(config.mode==='late-denied')transport.fetchReject=c=>c.method==='POST'&&c.path.endsWith('/synthetic-pause-clock');
    else transport.hold=c=>c.method==='POST'&&c.path.endsWith('/synthetic-pause-clock');
    const writing=$('synthetic-pause-start').click();await seen;
    // A->B->A reauthentication must invalidate the old context even if IDs match.
    if(config.mode==='late-case'){await p.run('loadPreparation('+JSON.stringify(config.other_id)+',{role:"park_specialist"})');check($('synthetic-pause-panel').hidden,'other case clears private clock');}else{$('token').value=config.owner;$('token').emit('input');$('token').value=config.reviewer;$('token').emit('input');}
    await open(p);const current=p.run('pauseClockView');check(!!current,'new current context may read history');
    transport.resume();await writing;check(p.run('pauseClockView')===current,'late old success/403 cannot overwrite or clear current view');
    check(Object.keys(storage).some(k=>k.startsWith('parkweave.synthetic-pause.v1.')),'late response cannot release original handle');
    await $('synthetic-pause-recover').click();check(!p.run('pauseClockUnresolved()'),'only explicit original-key recovery unlocks');
   }else if(['lost-cold','advanced-history','not-observed'].includes(config.mode)){
    await $('synthetic-pause-start').click();check(p.run('pauseClockUnresolved()'),'unknown original handle retained');
    const count=calls.length;await $('intake').onsubmit({preventDefault(){}});check(calls.length===count,'original business write gate blocks another entry');
    const stored=Object.values(storage).map(JSON.parse);check(stored.length===1&&Object.keys(stored[0]).sort().join(',')==='actor,fp,id,key,revision,v','only bounded opaque locator and fingerprint persisted');
    check(!JSON.stringify(storage).includes(config.reviewer)&&!JSON.stringify(storage).includes('explicit wait'),'no token or note in storage');
    if(config.mode==='advanced-history'){const peer=page({...config,token:config.reviewer},{},calls,{});await open(peer);peer.$('synthetic-pause-note').value='SYNTHETIC second page explicitly ends pause';peer.$('synthetic-pause-confirm').checked=true;await peer.$('synthetic-pause-end').click();check(peer.run('pauseClockView').revision===2,'later authorized event exists in original history');}
    const cold=page({...config,token:config.reviewer},storage,calls,{}),start=calls.length;
    await open(cold);if(config.mode==='advanced-history'){const real=cold.run('fetch');cold.context.fetch=async(path,options)=>{const response=await real(path,options);if(path.endsWith('/synthetic-pause-clock')&&options?.headers?.['Idempotency-Key']){const x=await response.json();Object.assign(x,{state:'UNKNOWN',fixture_write_enabled:false,source_ref:null,calendar_ref:null,elapsed_work_seconds:null,target_work_seconds:null,timezone:null,deadline_utc:null,deadline_local:null,issues:['OWNED_UI_CURRENT_PROJECTION_UNKNOWN_FAULT']});return {ok:true,status:200,json:async()=>x};}return response;};}await cold.$('synthetic-pause-recover').click();
    check(calls.slice(start).every(c=>c.method==='GET'),'cold explicit recovery sends GET only');
    if(config.mode==='not-observed'){check(cold.run('pauseClockUnresolved()'),'NOT_OBSERVED does not release unknown');check(textOf(cold.$('synthetic-pause-status')).includes('保留未决'),'uncertainty disclosed');}
    else {if(config.mode==='advanced-history')check(cold.$('synthetic-pause-form').hidden&&cold.run('pauseClockView').state==='UNKNOWN','committed recovery releases only the handle; UNKNOWN remains nonwritable');check(!cold.run('pauseClockUnresolved()')&&cold.run('pauseClockView').revision===(config.mode==='advanced-history'?2:1),'committed original event recovered without repost');}
   }else{
    await $('synthetic-pause-start').click();check(p.run('pauseClockView')?.paused===true,'explicit pause is read back');
    check(textOf($('synthetic-pause-history')).includes('<img src=x onerror=bad>'),'note displayed as text');
    $('synthetic-pause-note').value='SYNTHETIC explicit resume';$('synthetic-pause-confirm').checked=true;await $('synthetic-pause-end').click();
    check(p.run('pauseClockView')?.paused===false&&p.run('pauseClockView').revision===2,'explicit end and two original events read back');
    const owner=page({...config,token:config.owner},{},calls,{});await open(owner,'enterprise_operator');
    check(owner.$('synthetic-pause-form').hidden&&owner.run('pauseClockView').events.length===2,'owner history only does not derive pause authority');
   }
  }
 }
 const writes=calls.filter(c=>c.method==='POST');check(writes.every(c=>c.path.endsWith('/synthetic-pause-clock')),'no other domain writes');
 console.log(JSON.stringify({scope:'SYNTHETIC_PAUSE_CLOCK_ORIGINAL_HTML',mode:config.mode,checks,calls,posts:writes.length,storage_fields:Object.values(storage).map(x=>Object.keys(JSON.parse(x))),real_browser:false}));readline.close();
})().catch(e=>{console.error(JSON.stringify({error:e.stack,diagnostics}));process.exitCode=1;readline.close();});
`;
eval(harness+scenario);
