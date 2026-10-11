// Actual original notice section in offline Node VM; no browser or network.
const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync('/workspace/ParkWeave/src/parkweave/web.html','utf8');
const source=html.slice(html.indexOf('let noticeGeneration='),html.indexOf('// Durable registered adapter instances.',html.indexOf('let noticeGeneration=')));
const mode=process.argv[2];
const prefix=`
class El{constructor(tag='div',text=''){this.tag=tag;this.children=[];this._text=text;this.dataset={};this.hidden=false;this.disabled=false;this.value='';}
set textContent(x){this._text=String(x);this.children=[];}get textContent(){return this._text+this.children.map(x=>x.textContent).join('');}
append(...x){this.children.push(...x);}replaceChildren(...x){this._text='';this.children=x;}}
const els=new Map(),pending=[],requests=[],checks=[];
function $(id){if(!els.has(id))els.set(id,new El());return els.get(id);}
function textElement(tag,text){return new El(tag,text);}
function clearPreparation(preserve=false){if(!preserve)clearNotices();}
function clearReceipts(){}function clearResources(){}function dispatchCurrent(){return false;}
async function loadDispatch(){throw Error('forbidden implicit business navigation');}
function fetch(path,options){requests.push({path,options});return new Promise(resolve=>pending.push({path,options,resolve}));}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function next(path){let n=pending.findIndex(q=>q.path===path);if(n<0)throw Error('no request '+path);return pending.splice(n,1)[0];}
function reply(q,data,status=200){q.resolve({ok:status<400,status,json:async()=>data});}
function item(id){return {event_id:id,action:'OFFER',revision:1,historical:false,read_at:null,open_requested_at:null,delivered_at:'SYNTHETIC',preparation_id:'PRIVATE-P-'+id};}
const one='a'.repeat(43),two='b'.repeat(43),list='/api/dispatch-notices';
function page(ids,cursor){return {scope:'SYNTHETIC_INTERNAL_DISPATCH_NOTICES_ONLY',items:ids.map(item),check_limit:100,page_limit:20,next_cursor:cursor};}
function identity(token){$('token').value=token;clearNotices();}
function assert(ok,label){if(!ok)throw Error(label);checks.push(label);}
async function fresh(ids=['NEW'],cursor=two){const p=loadNoticeList().catch(noticeError);reply(next(list),page(ids,cursor));await p;}
`;
const probe=`
(async()=>{
 identity('SYNTHETIC-A');
 if(mode==='detail_success_late'||mode==='detail_403_late'){
  await fresh(['OLD'],one);
  const detail=loadNotice('OLD').catch(noticeError),q=next('/api/dispatch-notices/OLD');
  await fresh(['FRESH'],two);reply(q,{notice:item('OLD')},mode==='detail_403_late'?403:200);await detail;
  assert($('notice-items').children[0].dataset.noticeId==='FRESH','late detail cannot overwrite current list');
  assert(noticeId===null&&noticeView===null&&noticeNextCursor===two&&$('notice-detail').hidden,'late detail cannot restore private detail or cursor');
  assert(!$('notice-error').textContent,'late detail error cannot clear new list');
 }else if(mode==='body_delay_success_aba'||mode==='body_delay_403_aba'){
  const old=loadNoticeList().catch(noticeError),q=next(list);let release;
  q.resolve({ok:mode==='body_delay_success_aba',status:mode==='body_delay_success_aba'?200:403,
   json:()=>new Promise(resolve=>release=resolve)});await tick();
  identity('SYNTHETIC-B');identity('SYNTHETIC-A');await fresh(['NEW-IDENTITY'],two);
  release(page(['OLD-IDENTITY'],one));await old;
  assert($('notice-items').children[0].dataset.noticeId==='NEW-IDENTITY','identity ABA during JSON parse invalidates original reply');
  assert(noticeNextCursor===two&&!$('notice-error').textContent,'delayed body preserves new identity cursor and feedback');
 }else if(mode==='three_requests_mixed_order'){
  await fresh(['FIRST'],one);const oldButton=$('notice-items').children[0].children[2];
  const continuation=loadNoticeList({continueOlder:true}).catch(noticeError),q=next(list+'?cursor='+one);
  const middle=loadNoticeList().catch(noticeError),r=next(list);
  const newest=loadNoticeList().catch(noticeError),s=next(list);
  reply(s,page(['NEWEST'],two));await newest;reply(q,{},403);await continuation;reply(r,page(['MIDDLE'],one));await middle;
  oldButton.onclick();await tick();
  assert($('notice-items').children.length===1&&$('notice-items').children[0].dataset.noticeId==='NEWEST','only newest page survives mixed continuation refresh replies');
  assert(noticeNextCursor===two&&!$('notice-error').textContent&&pending.length===0,'late 403 and old detached action cannot affect current page');
 }else if(mode==='empty_duplicate_continue'){
  await fresh([],one);assert(!$('notice-next').hidden&&!$('notice-next').disabled,'empty authorized page remains continuable');
  const first=loadNoticeList({continueOlder:true}).catch(noticeError),q=next(list+'?cursor='+one);
  await loadNoticeList({continueOlder:true});assert(pending.length===0,'duplicate continuation does not start another request');
  assert($('notice-items').textContent===''&&noticeNextCursor===null,'continuation clears prior private page immediately');
  reply(q,page(['OLDER'],null));await first;
  assert($('notice-items').children[0].dataset.noticeId==='OLDER'&&$('notice-next').hidden,'older authorized row reached with explicit terminal state');
 }else throw Error('unknown mode');
 assert(requests.every(q=>q.options.method==='GET'&&q.options.cache==='no-store'&&!q.options.body),'all requests GET no-store without automatic OPEN or MARK_READ');
 return JSON.stringify({mode,checks,scope:'INDEPENDENT_OFFLINE_NODE_VM_ONLY'});
})()
`;
Promise.resolve(vm.runInNewContext(prefix+source+probe,{mode,setImmediate},{timeout:5000}))
.then(data=>process.stdout.write(data+'\n')).catch(err=>{process.stderr.write(String(err)+'\n');process.exitCode=1;});
