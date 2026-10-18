// Node VM + minimal DOM/fetch doubles; never starts a browser or a network request.
const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(process.argv[2],'utf8'),mode=process.argv[3];
const start=html.indexOf('let noticeGeneration='),end=html.indexOf('// Durable registered adapter instances.',start);
if(start<0||end<0||!html.includes('id="notice-next" class="secondary" hidden disabled'))throw Error('Missing original notification section');
// Pull the real original transport and read-failure dependencies from each tested
// page. No authorization/context predicate or original assertion is replaced.
function originalBlock(a,b){const at=html.indexOf(a),end=html.indexOf(b,at+1);if(at<0||end<=at)throw Error('Missing original helper '+a);return html.slice(at,end);}
function originalLine(marker){const line=html.split('\n').find(s=>s.startsWith(marker));if(!line)throw Error('Missing original helper '+marker);return line+'\n';}
const dependencies=originalLine('const deniedOperationReferences=')+originalLine('const entryWriteRequests=')+
 originalLine('const entryFailureFlows=')+originalLine('function failEntryFlow(')+
 (html.includes('const capturedCancelFrontierRequests=')?originalLine('const capturedCancelFrontierRequests='):'')+
 originalLine('function clearEntryWriteRequests(')+originalLine('function failCurrentEntryRead(')+
 originalLine('let receiptHistoryGeneration=')+originalLine('function clearReceiptHistory(')+
 originalBlock('function receiptCommandExplicitlyRejected(', 'function runEntryReadProof(')+
 originalBlock('async function entryFetch(', 'function retainDeniedOperationReference(')+
 originalBlock('function retainDeniedOperationReference(', 'function clearDeniedPrivateViews(');
const prefix=`
class Element {
 constructor(tag='div',text=''){this.tag=tag;this.children=[];this._text=text;this.dataset={};this.hidden=false;this.disabled=false;this.value='';}
 set textContent(x){this._text=String(x);this.children=[];} get textContent(){return this._text+this.children.map(x=>x.textContent).join('');}
 append(...xs){this.children.push(...xs);} replaceChildren(...xs){this._text='';this.children=[...xs];}
 click(){if(!this.disabled&&!this.hidden&&this.onclick)return this.onclick();}
}
const elements=new Map(),pending=[],requests=[];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function $(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}
function textElement(tag,text){return new Element(tag,text);}
let preparationView=null,dispatchView=null,receiptView=null;
function clearPreparation(preserveNotice=false){if(!preserveNotice)clearNotices();preparationView=null;dispatchView=null;}
function clearReceipts(){receiptView=null;}
function clearResources(){}
async function loadDispatch(){throw Error('Unexpected automatic business navigation');}
function dispatchCurrent(){return false;}
function fetch(path,options){requests.push({path,options});return new Promise(resolve=>pending.push({path,options,resolve}));}
function take(path){const i=pending.findIndex(x=>x.path===path);if(i<0)throw Error('Missing offline request '+path);return pending.splice(i,1)[0];}
function answer(q,data,status=200){q.resolve({ok:status<400,status,json:async()=>data});}
function item(id){return {event_id:id,preparation_id:'P-'+id,dispatch_id:'D-'+id,revision:1,action:'OFFER',delivered_at:'SYNTHETIC',historical:false,open_requested_at:null,read_at:null};}
function page(ids=[],cursor=null){return {scope:'SYNTHETIC_INTERNAL_DISPATCH_NOTICES_ONLY',items:ids.map(item),check_limit:100,page_limit:20,next_cursor:cursor};}
function token(value){$('token').value=value;clearPreparation();clearReceipts();}
const one='a'.repeat(43),two='b'.repeat(43),listPath='/api/dispatch-notices',nextPath=()=>listPath+'?cursor='+one;
function assert(value,label){if(!value)throw Error(label);checks.push(label);}
const checks=[];
async function first(ids=['A'],cursor=one){const p=loadNoticeList().catch(noticeError);answer(take(listPath),page(ids,cursor));await p;}
`;
const probe=`
(async()=>{
 token('SYNTHETIC-A');
 if(mode==='empty_continue'){
  await first([],one);assert(!$('notice-next').hidden&&!$('notice-next').disabled,'empty page permits continuing');
  const p=$('notice-next').click(),q=take(nextPath());assert($('notice-next').hidden&&noticeListLoading,'continuing clears and locks private view');
  $('notice-next').click();assert(pending.length===0,'duplicate continue has no request');
  answer(q,page(['OLDER'],null));await p;assert($('notice-items').textContent.includes('新分派')&&$('notice-next').hidden,'older page reached and end explicit');
 }else if(mode==='refresh_order'){
  const old=loadNoticeList().catch(noticeError),q=take(listPath),fresh=loadNoticeList().catch(noticeError),r=take(listPath);
  answer(r,page(['B'],two));await fresh;answer(q,page(['A'],one));await old;
  assert($('notice-items').children[0].dataset.noticeId==='B'&&noticeNextCursor===two,'older refresh response ignored');
 }else if(mode==='continue_then_refresh'){
  await first();const old=loadNoticeList({continueOlder:true}).catch(noticeError),q=take(nextPath());
  assert($('notice-items').textContent===''&&noticeNextCursor===null,'old page cleared before next response');
  const fresh=loadNoticeList().catch(noticeError),r=take(listPath);answer(r,page(['FRESH'],two));await fresh;answer(q,page(['OLD'],one));await old;
  assert($('notice-items').children[0].dataset.noticeId==='FRESH'&&noticeNextCursor===two,'late continuation cannot overwrite refreshed high water');
 }else if(mode==='identity_aba'){
  const old=loadNoticeList().catch(noticeError),q=take(listPath);token('SYNTHETIC-B');token('SYNTHETIC-A');await first(['NEW'],two);
  answer(q,page(['OLD'],one));await old;assert($('notice-items').children[0].dataset.noticeId==='NEW'&&noticeNextCursor===two,'identity ABA invalidates original reply');
 }else if(mode==='current_denied'){
  await first();preparationView={private:'old'};dispatchView={private:'old'};
  const p=loadNoticeList({continueOlder:true}).catch(noticeError);answer(take(nextPath()),{},403);await p;
  assert($('notice-items').textContent===''&&noticeNextCursor===null&&$('notice-next').hidden&&preparationView===null&&dispatchView===null,'403 clears every linked private view and position');
  assert($('notice-error').textContent.includes('刷新'),'denial offers explicit refresh');
 }else if(mode==='stale_denied'){
  const old=loadNoticeList().catch(noticeError),q=take(listPath);await first(['NEW'],two);answer(q,{},403);await old;
  assert($('notice-items').children[0].dataset.noticeId==='NEW'&&noticeNextCursor===two&&!$('notice-error').textContent,'stale 403 cannot clear current page');
 }else if(mode==='detail_clears'){
  await first();const button=$('notice-items').children[0].children[2],p=button.click(),q=take('/api/dispatch-notices/A');
  assert($('notice-items').textContent===''&&noticeNextCursor===null&&$('notice-next').hidden,'detail navigation clears list and cursor');
  answer(q,{notice:item('A')});await tick();assert(noticeId==='A'&&noticeView.event_id==='A','explicit detail remains readable');
 }else if(mode==='stale_card'){
  await first();const old=$('notice-items').children[0].children[2];await first(['B'],two);old.click();
  assert(pending.length===0&&$('notice-items').children[0].dataset.noticeId==='B','detached previous-page action ignored');
 }else if(mode==='malformed_response'){
  await first();const p=loadNoticeList({continueOlder:true}).catch(noticeError);const invalid=page(['BAD'],one);invalid.next_cursor='PRIVATE_BAD_CURSOR';answer(take(nextPath()),invalid);await p;
  assert($('notice-items').textContent===''&&noticeNextCursor===null&&$('notice-next').hidden&&!!$('notice-error').textContent,'invalid response leaves no old private data or continue handle');
 }else if(mode==='clear_inflight'){
  await first();const old=loadNoticeList({continueOlder:true}).catch(noticeError),q=take(nextPath());clearNotices();answer(q,page(['OLD'],one));await old;
  assert($('notice-items').textContent===''&&noticeNextCursor===null&&$('notice-next').hidden,'explicit clear invalidates in-flight continuation');
 }else throw Error('Unknown offline mode');
 assert(requests.every(x=>x.options.method==='GET'&&x.options.cache==='no-store'&&!x.options.body),'no automatic OPEN MARK_READ or cached response');
 return JSON.stringify({mode,checks,scope:'NODE_VM_WITH_DOM_AND_FETCH_DOUBLES_ONLY'});
})()
`;
Promise.resolve(vm.runInNewContext(prefix+dependencies+html.slice(start,end)+probe,{mode,setImmediate},{timeout:5000})).then(x=>process.stdout.write(x+'\n')).catch(e=>{process.stderr.write(String(e)+'\n');process.exitCode=1;});
