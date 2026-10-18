from pathlib import Path
p=Path('tests/test_receipt_submit_recovery_browser.py');s=p.read_text();r=Path('.runtime/receipt-submit-settled-order-20261018');(r/'baseline-test.py').write_text(s)
old="@pytest.mark.parametrize('old_status',[200,403])\n@pytest.mark.parametrize('overlap',[False,True],ids=['old_then_new','new_before_old'])\ndef test_cold_recovery_refresh_releases_only_its_own_busy_operation(demo_inputs,tmp_path,old_status,overlap):"
new='''def observe_receipt_handler_completion(page):
    """Observe original DOM handler promises after catch/finally; never set app state."""
    page.evaluate("""() => {
      const trace={sequence:0,calls:[],counts:{}};window.receiptRecoveryTestTrace=trace;
      for(const id of ['receipt-submit-recover','receipt-refresh','receipt-submit-release']){
        const button=document.getElementById(id),original=button.onclick;
        button.onclick=function(event){
          const ordinal=trace.counts[id]=(trace.counts[id]||0)+1;
          const call={id,ordinal,begin:++trace.sequence,settled:false};trace.calls.push(call);
          let result;
          try{result=Reflect.apply(original,this,[event]);}
          catch(error){call.outcome='synchronous-throw';call.settled=true;call.end=++trace.sequence;throw error;}
          call.returnedPromise=!!result&&typeof result.then==='function';
          Promise.resolve(result).then(()=>{call.outcome='fulfilled';call.settled=true;call.end=++trace.sequence;},
            ()=>{call.outcome='rejected';call.settled=true;call.end=++trace.sequence;});
          return result;
        };
      }
    }""")


def receipt_handler_settled(page,id,ordinal):
    page.wait_for_function("([id,n])=>receiptRecoveryTestTrace.calls.some(c=>c.id===id&&c.ordinal===n&&c.returnedPromise&&c.settled)",arg=[id,ordinal],timeout=15000)


def run_cold_recovery_refresh(demo_inputs,tmp_path,old_status,overlap,new_first=False):'''
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace("row=create(f,parent)[0].json();authority=authority_snapshot(f[1]);traffic=[];errors=[];held=[];phases=[]", "row=create(f,parent)[0].json();authority=authority_snapshot(f[1]);traffic=[];errors=[];held=[];phases=[];forwarded=[]")
a=s.index('        def snapshot(label):',s.index('def run_cold_recovery_refresh'));b=s.index('        try:',a)
s=s[:a]+'''        def state():
            return page.evaluate("""()=>({generation:receiptGeneration,busy:receiptSubmitBusy,
                operationActive:receiptSubmitOperation!==null,
                recoverDisabled:document.querySelector('#receipt-submit-recover').disabled,
                releaseDisabled:document.querySelector('#receipt-submit-release').disabled,
                proof:receiptSubmitProof,handle:receiptSubmitHandle,
                stored:Object.entries(localStorage).filter(([n])=>n.startsWith(receiptSubmitStorage)),
                detailHidden:document.querySelector('#receipt-detail').hidden,
                draft:document.querySelector('#receipt-text').value,source:document.querySelector('#receipt-source').value,
                view:receiptView,context:receiptContext&&{generation:receiptContext.generation,id:receiptContext.id,revision:receiptContext.revision,sha:receiptContext.sha},
                error:document.querySelector('#receipt-error').textContent})""")
        def snapshot(label):
            phases.append(dict(label=label,**state()))
            (tmp_path/'refresh-proof.json').write_text(json.dumps(dict(
                ordinary_configured_app=True,actual_chromium=True,old_status=old_status,overlap=overlap,
                completion_order='new_settled_then_old' if new_first else 'old_settled_then_new',
                old_403_transport_injection='existing other-tenant token used only for captured read' if old_status==403 else None,
                phases=phases,traffic=traffic,forwarded=forwarded,errors=errors,
                handler_trace=page.evaluate('window.receiptRecoveryTestTrace??null'),Windows='NOT_RUN'),indent=2)+'\\n')
''' +s[b:]
start=s.index('def run_cold_recovery_refresh');a=s[:start];body=s[start:]
body=body.replace("reply=route.fetch();assert reply.status==200\n                route.abort('failed')", "reply=route.fetch();assert reply.status==200\n                forwarded.append(dict(method='POST',path=urlsplit(route.request.url).path,status=reply.status))\n                route.abort('failed')")
body=body.replace("draft='SYNTHETIC current draft survives same-item refresh'\n            page.locator('#receipt-text').fill(draft)", "draft='SYNTHETIC current draft survives same-item refresh'\n            source='SYNTHETIC new unsent draft source retained'\n            page.locator('#receipt-text').fill(draft);page.locator('#receipt-source').fill(source)\n            observe_receipt_handler_completion(page)\n            assert before['preparations'][0]['service_case_plan'] is None\n            assert sum(e['action']=='SUBMIT' for e in before['service_receipt_events'])==1\n            assert not any(e['action']=='ACKNOWLEDGE' for e in before['service_receipt_events'])")
body=body.replace("held.append((route,reply))", "forwarded.append(dict(method='GET',path=urlsplit(route.request.url).path,status=reply.status,order=len(held)+1))\n                    held.append((route,reply))")
body=body.replace("page.wait_for_function('(g)=>receiptGeneration>g&&receiptView!==null&&receiptContext!==null',arg=generation)", "receipt_handler_settled(page,'receipt-refresh',1)\n            assert page.evaluate('(g)=>receiptGeneration>g&&receiptView!==null&&receiptContext!==null',generation)")
action_start=body.index('            held[0][0].fulfill');action_end=body.index("            page.locator('#receipt-submit-release').click()",action_start)
body=body[:action_start]+'''            if new_first:
                assert overlap and len(held)==2
                held[1][0].fulfill(response=held[1][1])
                receipt_handler_settled(page,'receipt-submit-recover',2)
                assert page.evaluate('!receiptSubmitBusy&&receiptSubmitOperation===null&&receiptSubmitProof?.status==="COMMITTED"')
                assert page.evaluate('receiptSubmitProof')==held[1][1].json()
                expect(page.locator('#receipt-submit-release')).to_be_enabled()
                snapshot('new-recovery-fully-settled-before-old-delivery')
                current=state()
                assert not page.evaluate('receiptRecoveryTestTrace.calls.find(c=>c.id==="receipt-submit-recover"&&c.ordinal===1).settled')
                held[0][0].fulfill(response=held[0][1])
                receipt_handler_settled(page,'receipt-submit-recover',1)
                snapshot('old-recovery-fully-settled-after-new')
                assert state()==current
                trace=page.evaluate('receiptRecoveryTestTrace.calls')
                old=next(c for c in trace if c['id']=='receipt-submit-recover' and c['ordinal']==1)
                new=next(c for c in trace if c['id']=='receipt-submit-recover' and c['ordinal']==2)
                assert new['end']<old['end'] and old['outcome']==new['outcome']=='fulfilled'
            else:
                held[0][0].fulfill(response=held[0][1])
                receipt_handler_settled(page,'receipt-submit-recover',1)
                snapshot('old-recovery-fully-settled')
                if overlap:
                    assert page.evaluate('receiptSubmitBusy&&receiptSubmitOperation!==null&&receiptSubmitProof===null')
                    expect(page.locator('#receipt-submit-recover')).to_be_disabled()
                else:
                    expect(page.locator('#receipt-submit-recover')).to_be_enabled(timeout=3000)
                    assert page.evaluate('!receiptSubmitBusy&&receiptSubmitProof===null')
                    page.locator('#receipt-submit-recover').click()
                    for _ in range(100):
                        if len(held)==2:break
                        page.wait_for_timeout(20)
                    assert len(held)==2
                held[1][0].fulfill(response=held[1][1])
                receipt_handler_settled(page,'receipt-submit-recover',2)
                assert page.evaluate('!receiptSubmitBusy&&receiptSubmitProof?.status==="COMMITTED"')
                snapshot('new-recovery-fully-settled')
            assert page.evaluate('(h)=>localStorage.getItem(h[0])===h[1]',handles[0])
            assert page.locator('#receipt-text').input_value()==draft
            assert page.locator('#receipt-source').input_value()==source
''' +body[action_end:]
body=body.replace("page.wait_for_function('()=>!receiptSubmitBusy&&!receiptSubmitStoredPending()')", "receipt_handler_settled(page,'receipt-submit-release',1)\n            assert page.evaluate('!receiptSubmitBusy&&receiptSubmitOperation===null&&!receiptSubmitStoredPending()&&receiptSubmitProof===null')")
body=body.replace("assert page.locator('#receipt-text').input_value()==draft\n            assert page.evaluate('(n)", "assert page.locator('#receipt-text').input_value()==draft\n            assert page.locator('#receipt-source').input_value()==source\n            assert page.evaluate('(n)")
body=body.replace("assert len([r for r in traffic if r['method']=='POST'])==1\n            assert page.evaluate('document", "assert len([r for r in traffic if r['method']=='POST'])==1\n            assert len([r for r in forwarded if r['method']=='POST'])==1\n            assert page.evaluate('document")
s=a+body+'''

@pytest.mark.parametrize('old_status',[200,403])
@pytest.mark.parametrize('overlap',[False,True],ids=['old_then_new','new_before_old'])
def test_cold_recovery_refresh_releases_only_its_own_busy_operation(demo_inputs,tmp_path,old_status,overlap):
    # Original IDs/old-first cases retained; new_before_old means new read STARTS first.
    run_cold_recovery_refresh(demo_inputs,tmp_path,old_status,overlap)


@pytest.mark.parametrize('old_status',[200,403])
def test_new_recovery_fully_settles_before_old_reply_cannot_change_current_proof(demo_inputs,tmp_path,old_status):
    run_cold_recovery_refresh(demo_inputs,tmp_path,old_status,True,new_first=True)
'''
p.write_text(s)
