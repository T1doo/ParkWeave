// Executes the actual shipped callbacks using Node vm and explicit test doubles.
// This is not a DOM event engine, browser, screenshot or keyboard-device test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ref=process.env.PARKWEAVE_TEST_REF;if(ref)assert(/^[a-f0-9]{40}$/.test(ref));
const results=[],failures=[];
function check(name,run){try{run();results.push(name);}catch(error){failures.push({name,error:error.message});}}
for(const filename of ['web.html','local_preparation_web.html']){
 const path='src/parkweave/'+filename,html=ref?require('node:child_process').execFileSync('git',['show',ref+':'+path],{encoding:'utf8',maxBuffer:8*1024*1024}):fs.readFileSync(path,'utf8'),lines=html.split('\n');
 const registration=lines.find(line=>/\b(grid|calendar)\.addEventListener\('keydown'/.test(line)&&line.includes('[data-day]'));
 const closeLine=lines.find(line=>line.includes('prev.onclick=')&&line.includes('close.onclick='));
 const assembly=lines.find(line=>line.includes('heading.append(prev,monthTitle,next,close)'));
 assert(registration&&closeLine&&assembly.includes('calendar.append(heading,'),'header and grid share the declared calendar section');
 const handlers={grid:[],calendar:[]},state={focus:null,renders:0,months:[]},calendar={hidden:false,addEventListener(type,fn){handlers.calendar.push(fn);}},grid={addEventListener(type,fn){handlers.grid.push(fn);},querySelector(){return {focus(){state.focus=context.focusDay;}};}},trigger={focus(options){assert.equal(options.preventScroll,true);state.focus='original-date-trigger';}},close={click(){this.onclick();}};
 const context={calendar,grid,trigger,close,focusDay:'2026-11-09',month:new Date('2026-11-01T00:00:00Z'),dateAt:value=>new Date(value+'T00:00:00Z'),dateString:date=>date.toISOString().slice(0,10),renderCalendar(){state.renders++;},shiftMonth(amount){state.months.push(amount);}};
 vm.runInNewContext(closeLine.slice(closeLine.indexOf('close.onclick=')),context);
 vm.runInNewContext(registration,context);
 function key(origin,key){const day=origin==='day'?{dataset:{day:'2026-11-09'}}:null,event={key,target:{closest(){return day;}},defaultPrevented:false,stopped:false,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;}};
  // The source assembly places heading controls outside grid, under calendar.
  for(const host of origin==='day'?['grid','calendar']:['calendar']){for(const fn of handlers[host])fn(event);if(event.stopped)break;}return event;
 }
 for(const origin of ['previous-month','next-month','close-button'])check(filename+': Escape from '+origin+' closes and returns to original trigger',()=>{
  calendar.hidden=false;state.focus=origin;const event=key(origin,'Escape');assert.equal(calendar.hidden,true);assert.equal(state.focus,'original-date-trigger');assert.equal(event.defaultPrevented,true);
 });
 check(filename+': date-cell Escape preserves the original close action',()=>{calendar.hidden=false;state.focus='day';const event=key('day','Escape');assert.equal(calendar.hidden,true);assert.equal(state.focus,'original-date-trigger');assert.equal(event.defaultPrevented,true);});
 check(filename+': heading navigation keys do not become calendar selection commands',()=>{
  for(const origin of ['previous-month','next-month','close-button'])for(const name of ['ArrowDown','ArrowUp','Home','End']){calendar.hidden=false;state.focus=origin;const before=state.renders,event=key(origin,name);assert.equal(calendar.hidden,false);assert.equal(state.focus,origin);assert.equal(event.defaultPrevented,false);assert.equal(state.renders,before);}
 });
 check(filename+': date-cell arrows, week boundaries and month delegation remain available',()=>{
  assert.equal(key('day','ArrowRight').defaultPrevented,true);assert.equal(context.focusDay,'2026-11-10');assert.equal(state.focus,'2026-11-10');
  key('day','Home');assert.equal(context.focusDay,'2026-11-09');key('day','End');assert.equal(context.focusDay,'2026-11-15');
  key('day','PageUp');key('day','PageDown');assert.deepEqual(state.months,[-1,1]);
 });
}
console.log(JSON.stringify({kind:'shipped-callback-vm-with-test-doubles',results,failures,dom_engine:false,browser_runs:0,pixel_engine:false},null,2));assert.equal(failures.length,0);
