"use strict";
// Real shipped functions and Map with controlled values; no HTTP/browser.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('src/parkweave/web.html','utf8'),mode=process.argv[2];
const first=html.indexOf('function caseReconPhase('),last=html.indexOf('function clearCaseReconciliation(',first);
assert(first>=0&&last>first);
const token={value:'synthetic-owner-a'},c={preparationView:null,caseReconPhases:new Map(),$:()=>token};
vm.createContext(c);vm.runInContext(html.slice(first,last),c);
let checks=0;const check=(actual,expected)=>{assert.equal(actual,expected);checks++;};
const a='00000000-0000-4000-8000-000000000001',b='00000000-0000-4000-8000-000000000002';
if(mode==='null_identity'){
 for(const view of [null,undefined,{}, {preparation:null},{preparation:{}},{preparation:{case_id:undefined},case_write_blocked:true},{preparation:{case_id:null},case_write_blocked:true}]){
  c.preparationView=view;
  for(const id of [undefined,null,'',false,0])check(c.caseReconBlocked(id),false);
  check(c.caseReconBlocked(a),false);
 }
}else if(mode==='view_flags'){
 for(const flag of ['case_write_blocked','case_reconciling','case_cancelled']){
  c.preparationView={preparation:{case_id:a},[flag]:true};check(c.caseReconBlocked(a),true);check(c.caseReconBlocked(b),false);check(c.caseReconBlocked(undefined),false);
  c.preparationView[flag]=false;check(c.caseReconBlocked(a),false);
 }
 c.preparationView={preparation:{case_id:a}};check(c.caseReconBlocked(a),false);
}else if(mode==='known_phase'){
 for(const phase of ['RECONCILING','CANCELLED']){
  c.caseReconPhases.clear();c.preparationView=null;c.caseReconRemember(a,phase);check(c.caseReconBlocked(a),true);check(c.caseReconBlocked(b),false);check(c.caseReconBlocked(undefined),false);
  c.preparationView={preparation:{case_id:b}};check(c.caseReconBlocked(a),true);
  token.value='synthetic-owner-b';check(c.caseReconBlocked(a),false);token.value='synthetic-owner-a';check(c.caseReconBlocked(a),true);
 }
 c.caseReconRemember(a,'RECONCILING');check(c.caseReconPhase(a),'CANCELLED');check(c.caseReconBlocked(a),true);
 c.caseReconRemember(b,'UNKNOWN');check(c.caseReconBlocked(b),false);
}else throw Error('unknown mode');
console.log(JSON.stringify({mode,checks,actual_http:false,real_browser:'NOT_RUN',scope:'REAL_CASE_RECON_BLOCK_FUNCTIONS_CONTROLLED_MATRIX'}));
