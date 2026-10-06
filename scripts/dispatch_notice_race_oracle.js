(async()=>{
const pending=[],checks={},tick=()=>new Promise(resolve=>setTimeout(resolve,0));
window.fetch=(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}));
const take=path=>{const i=pending.findIndex(q=>q.path===path);if(i<0)throw Error('Missing request '+path);return pending.splice(i,1)[0];};
const takeLast=path=>{const i=pending.findLastIndex(q=>q.path===path);if(i<0)throw Error('Missing latest '+path);return pending.splice(i,1)[0];};
const response=(q,data,status=200)=>q.resolve({ok:status<400,status,json:async()=>data});
const path=id=>'/api/dispatch-notices/'+id;
const item=(id,opened=false,read=false)=>({event_id:id,preparation_id:'P-'+id,dispatch_id:'D-'+id,revision:1,action:'OFFER',created_at:'synthetic time',delivered_at:'synthetic time',open_requested_at:opened?'synthetic open':null,read_at:read?'synthetic read':null,historical:false});
const token=t=>{$('token').value=t;$('token').dispatchEvent(new Event('input'));};
const load=id=>loadNotice(id).catch(noticeError);
const ready=async(id,opened=false,read=false)=>{const p=load(id);response(takeLast(path(id)),{notice:item(id,opened,read)});await p;};
const send=action=>noticeCommand(action).catch(noticeError);
token('synthetic-owner');let late=load('A');await ready('B');response(take(path('A')),{notice:item('A')});await late;checks.late_read_preserves_selection=noticeId==='B'&&noticeView.event_id==='B';
let command=send('OPEN');await tick();let q=take(path('B')+'/commands');checks.open_snapshot=JSON.parse(q.options.body).action==='OPEN'&&JSON.parse(q.options.body).expected_revision===1;await ready('C');response(q,{notice:item('B',true)});await command;checks.late_open_no_followup=noticeId==='C'&&!pending.length;
late=load('A');token('another');response(take(path('A')),{notice:item('A')});await late;checks.identity_clears=noticeView===null&&$('notice-items').textContent==='';
await ready('A');late=load('A');await ready('B');await ready('A',true,true);response(take(path('A')),{notice:item('A')});await late;checks.aba_preserves_read=noticeView.read_at==='synthetic read';
await ready('A',true);let open=send('OPEN');await tick();q=take(path('A')+'/commands');let read=send('MARK_READ');await tick();let rq=take(path('A')+'/commands');response(rq,{notice:item('A',true,true)});await read;response(q,{notice:item('A',true,false)});await open;checks.old_open_cannot_unread=noticeView.read_at==='synthetic read'&&!pending.length;
await ready('A',true);command=send('MARK_READ');await tick();q=take(path('A')+'/commands');await ready('B');response(q,{},403);await command;checks.stale_forbidden_ignored=noticeId==='B';
await ready('A',true);command=send('MARK_READ');await tick();q=take(path('A')+'/commands');response(q,{},403);await command;checks.current_forbidden_clears=noticeView===null&&$('notice-detail').hidden&&preparationView===null&&dispatchView===null&&$('page-feedback').textContent.length>0;
let list=loadNoticeList().catch(noticeError);q=take('/api/dispatch-notices');token('other');response(q,{items:[item('A')],check_limit:100});await list;checks.late_list_ignored=$('notice-items').textContent==='';
await ready('A');command=send('OPEN');await tick();q=take(path('A')+'/commands');response(q,{notice:item('A',true)});await tick();let source=take('/api/preparations/P-A/dispatch');token('new identity');response(source,{},403);await command;checks.identity_during_followup_clears=noticeView===null&&dispatchView===null;
await ready('A');command=send('OPEN');await tick();q=take(path('A')+'/commands');response(q,{notice:item('A',true)});await tick();source=take('/api/preparations/P-A/dispatch');response(source,{},403);await command;checks.current_source_forbidden_clears=noticeView===null&&dispatchView===null&&$('page-feedback').textContent.length>0;
await ready('A');command=send('OPEN');await tick();q=take(path('A')+'/commands');response(q,{notice:item('A',true)});await tick();source=take('/api/preparations/P-A/dispatch');let mark=send('MARK_READ');await tick();response(take(path('A')+'/commands'),{notice:item('A',true,true)});await mark;response(source,{},403);await command;checks.current_source_forbidden_after_mark_still_clears=noticeView===null&&dispatchView===null&&$('page-feedback').textContent.length>0;
await ready('A',true);command=send('MARK_READ');await tick();q=take(path('A')+'/commands');let back=loadNoticeList().catch(noticeError);response(take('/api/dispatch-notices'),{items:[item('B')],check_limit:100});await back;response(q,{notice:item('A',true,true)});await command;checks.back_invalidates_write=noticeView===null&&$('notice-items').textContent.includes('新分派');
await ready('A');late=load('B');document.querySelector('[data-tab=resource]').click();response(take(path('B')),{notice:item('B')});await late;checks.navigation_clears=noticeView===null&&$('notice-detail').hidden;
for(const [key,mutate] of [['id',()=>noticeView.event_id='OTHER'],['revision',()=>noticeView.revision=3]]){await ready('A',true);mutate();let caught=false;try{await noticeCommand('MARK_READ');}catch(e){caught=true;}checks[key+'_guard']=caught&&!pending.length;}
return JSON.stringify({scope:'CONTROLLED_RESPONSE_ORDER_ONLY',checks});
})()
