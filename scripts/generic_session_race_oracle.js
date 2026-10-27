(async()=>{
const pending=[],checks={};const tick=()=>new Promise(r=>setTimeout(r,0));
window.fetch=(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}));
const take=path=>{const i=pending.findIndex(q=>q.path===path);if(i<0)throw Error('missing request '+path);return pending.splice(i,1)[0];};
const respond=(q,x,status=200)=>q.resolve({ok:status<400,status,json:async()=>x});
const identity=t=>{$('token').value=t;$('token').dispatchEvent(new Event('input'));};
identity('A');$('result').textContent='OLD PRIVATE JSON';$('run').value='old-run';$('goal').value='old goal';$('candidate-region').value='old region';$('candidate-employees').value='9';$('candidate-service_need').value='old need';$('answer-version').value='old version';identity('B');checks.identity_clears_generic_data=$('result').textContent===''&&$('run').value===''&&$('goal').value===''&&$('candidate-region').value===''&&$('candidate-employees').value===''&&$('candidate-service_need').value===''&&$('answer-version').value==='1';
identity('A');const old=apiCall('/api/runs/old').catch(()=>undefined);identity('B');respond(take('/api/runs/old'),{secret:'OLD PRIVATE JSON'});await old;checks.old_identity_response_ignored=!$('result').textContent.includes('OLD PRIVATE');
identity('A');$('run').value='old-run';const review=$('review').onclick();identity('B');respond(take('/api/runs/old-run/fact-review'),{run_id:'old-run',document:{necessary_questions:[{field:'region',prompt:'OLD PRIVATE QUESTION'}]}});await review;checks.old_review_cannot_restore_question=currentReview===null&&$('clarifications').hidden&&$('questions').textContent==='';
identity('A');$('goal').value='SYNTHETIC old goal';const intake=$('intake').onsubmit({preventDefault(){}});identity('B');respond(take('/api/runs'),{run_id:'old-intake'});await intake;checks.old_create_cannot_restore_run=$('run').value==='';
identity('A');$('run').value='run-A';const reading=$('refresh').onclick();$('run').value='run-B';$('run').dispatchEvent(new Event('input'));respond(take('/api/runs/run-A'),{run_id:'run-A',private:'OLD RUN'});await reading;checks.run_change_invalidates_pending=!$('result').textContent.includes('OLD RUN');
identity('A');const first=apiCall('/api/runs/first').catch(()=>undefined),second=apiCall('/api/runs/second').catch(()=>undefined);respond(take('/api/runs/second'),{run_id:'SECOND'});await second;respond(take('/api/runs/first'),{run_id:'FIRST'});await first;checks.latest_generic_read_wins=$('result').textContent.includes('SECOND')&&!$('result').textContent.includes('FIRST');
identity('A');const nav=apiCall('/api/runs/nav').catch(()=>undefined);document.querySelector('[data-tab=resource]').click();respond(take('/api/runs/nav'),{private:'OLD NAVIGATION'});await nav;checks.navigation_invalidates_pending=!$('result').textContent.includes('OLD NAVIGATION');
return JSON.stringify({checks});
})()
