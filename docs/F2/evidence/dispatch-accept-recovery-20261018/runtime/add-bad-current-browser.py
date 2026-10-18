from pathlib import Path
p=Path('tests/test_dispatch_accept_recovery_browser.py');s=p.read_text().replace("'revoked','restart']","'revoked','restart','bad_current']",1)
a="            page.locator('#dispatch-accept-release').click()\n            expect(page.locator('#dispatch-accept-recover')).to_be_hidden(timeout=15000)"
b="""            if mode=='bad_current':
                # The real server response is obtained, then this fault harness
                # corrupts one field. Never claim the backend produced it.
                path='**/api/service-dispatches/'+row['dispatch_id']
                def corrupt(route):
                    reply=route.fetch();assert reply.status==200
                    data=reply.json();data['history']=None
                    route.fulfill(response=reply,json=data)
                page.route(path,corrupt)
                page.locator('#dispatch-accept-release').click()
                expect(page.locator('#dispatch-error')).to_contain_text('当前分派与原接单证明不匹配',timeout=15000)
                assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
                page.unroute(path,corrupt)
            page.locator('#dispatch-accept-release').click()
            expect(page.locator('#dispatch-accept-recover')).to_be_hidden(timeout=15000)"""
assert a in s;s=s.replace(a,b,1);p.write_text(s)
