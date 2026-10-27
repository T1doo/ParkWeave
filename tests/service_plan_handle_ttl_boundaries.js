// Narrow unit contract over the actual production reader; no application flow is mocked.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const mode=process.argv[2],html=fs.readFileSync(process.argv[3]||'src/parkweave/web.html','utf8');
const fields=html.split('\n').find(line=>line.startsWith('const servicePlanRecoveryFields='));
const reader=html.split('\n').find(line=>line.startsWith('function readServicePlanHandle('));
assert(fields&&reader);
const now=1792238400000,day=86400000,id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const h={v:1,id:id(1),key:id(2),actor:'a'.repeat(64),case:id(3),run:id(4),action:'VERIFY',plan:id(5),step:id(6),revision:1,expires:now+1000};
const expiry={past:now-1,at_now:now,one_ms_valid:now+1,max_valid:now+day,over_max:now+day+1,zero:0,far_future:999999999999999,null:null,string:String(now+1000),boolean:true};
if(mode==='missing')delete h.expires;
else if(mode==='extra_field')h.reason='SYNTHETIC forbidden stored body';
else {assert(Object.hasOwn(expiry,mode));h.expires=expiry[mode];}
const name='parkweave.service-plan-recovery.v1.'+h.id+'.'+h.actor,otherName='parkweave.service-plan-recovery.v1.'+id(7)+'.'+h.actor;
const raw=JSON.stringify(h),otherRaw=JSON.stringify({...h,id:id(7),expires:now+1000}),store=new Map([[name,raw],[otherName,otherRaw]]),removals=[];
const context=vm.createContext({TextEncoder,Number,JSON,Error,Date:{now:()=>now},
 servicePlanRecoveryStorage:'parkweave.service-plan-recovery.v1.',localStorage:{getItem:n=>store.get(n)??null,removeItem:n=>{removals.push(n);store.delete(n);}}});
vm.runInContext(fields+'\n'+reader,context);
const result=vm.runInContext('readServicePlanHandle('+JSON.stringify(h.id)+','+JSON.stringify(h.actor)+')',context);
const valid=['one_ms_valid','max_valid'].includes(mode);
if(valid){assert.deepStrictEqual(JSON.parse(JSON.stringify(result)),h);assert.strictEqual(store.get(name),raw);assert.deepStrictEqual(removals,[]);}
else {assert.strictEqual(result,null,'invalid deadline/schema must not return a recovery handle');assert(!store.has(name));assert.deepStrictEqual(removals,[name]);}
assert.strictEqual(store.get(otherName),otherRaw,'another original handle must remain unchanged');
const again=vm.runInContext('readServicePlanHandle('+JSON.stringify(h.id)+','+JSON.stringify(h.actor)+')',context);
assert(valid?again.key===h.key&&again.expires===h.expires:again===null);
assert.strictEqual(store.get(otherName),otherRaw);
console.log(JSON.stringify({mode,checks:6,valid,expiry:h.expires??null,original_key_unchanged:valid,other_handle_preserved:true,HTTP_requests:0,scope:'ACTUAL_READER_STRICT_DEADLINE_AND_SCOPED_STORAGE_UNIT'}));
