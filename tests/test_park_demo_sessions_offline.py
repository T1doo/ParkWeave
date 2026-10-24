"""Original guide import handlers with synthetic strings and DOM/window doubles.

No browser, real sessions, network, database or original business-page execution.
"""
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const mode=process.argv[1],roles=['enterprise','specialist','executor'];
const keys=[...roles,...roles.map(x=>'second_'+x)];
// Deliberately fake, in-memory format fixtures; never issued or authenticated.
const values=Object.fromEntries(keys.map((k,i)=>[k,String.fromCharCode(65+i).repeat(43)]));
const elements=new Map(),element=id=>({id,value:'',textContent:'',dataset:{},disabled:false,files:[]});
for(const id of ['sessions','workspace-open','status','scenario','fill-goal','fill-request','fill-need','fill-outline'])elements.set(id,element(id));
for(const role of roles){const e=element(role);e.dataset.role=role;elements.set(role,e);}
const buttons=[...elements.values()].filter(e=>e.id!=='sessions'&&e.id!=='status'&&e.id!=='scenario');
let opens=0,network=0;const events=[],token=element('token');
token.dispatchEvent=e=>{events.push(e.type);return true;};
const business={closed:false,location:{origin:'http://127.0.0.1:8765'},focus(){},
 document:{getElementById:id=>id==='token'?token:null},Event:class{constructor(type){this.type=type;}}};
const context=vm.createContext({JSON,Error,location:{origin:business.location.origin},
 fetch(){network++;throw Error('offline handler must not make network requests');},
 document:{getElementById:id=>elements.get(id),querySelectorAll:selector=>{
  if(selector==='button')return buttons;if(selector==='[data-role]')return roles.map(r=>elements.get(r));
  throw Error('unexpected selector');}},
 window:{addEventListener(){},open(url,target){assert.ok(url==='/'&&target==='_blank');opens++;return business;}}});
const html=fs.readFileSync('src/parkweave/park_demo_web.html','utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const run=code=>vm.runInContext(code,context);
async function load(data){const raw=JSON.stringify(data);elements.get('sessions').files=[{size:Buffer.byteLength(raw),text:async()=>raw}];await elements.get('sessions').onchange();}
(async()=>{
 await load(values);assert.ok(run('sessions!==null'),'six distinct values accepted');
 assert.ok(elements.get('status').dataset.tone==='success'&&opens===0,'import never opens a window');
 assert.ok(!elements.get('workspace-open').disabled&&roles.every(r=>elements.get(r).disabled),'explicit open still required');
 elements.get('workspace-open').onclick();elements.get('enterprise').onclick();
 assert.ok(token.value===values.enterprise&&opens===1,'explicit original role selection');
 assert.deepStrictEqual(events,['input','change'],'original identity callbacks');
 if(mode!=='normal'){
  const duplicate={...values};duplicate[mode==='duplicate-role'?'specialist':'second_executor']=values.enterprise;
  const previousEvents=events.length;await load(duplicate);
  assert.ok(run('sessions===null'),'duplicate values must refuse the import');
  assert.ok(buttons.every(b=>b.disabled),'failed import closes all guide actions');
  assert.ok(token.value===''&&events.length>previousEvents&&events.slice(previousEvents).every(e=>e==='input'),'clear token through original input callback');
  assert.ok(elements.get('status').dataset.tone==='error'&&elements.get('status').textContent.includes('六身份会话文件'),'original error feedback');
 }
 assert.ok(network===0&&opens===1,'no network or implicit window action');
 console.log(JSON.stringify({mode,result:'PASS',whole_guide_script:true,browser:false,network:0,real_sessions:0}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
"""


class GuideSessionImports(unittest.TestCase):
    def run_scenario(self, mode):
        result = subprocess.run(['node', '-e', SCENARIO, mode], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_distinct_values_keep_explicit_role_callbacks(self):
        self.run_scenario('normal')

    def test_repeated_role_value_refuses_and_clears(self):
        self.run_scenario('duplicate-role')

    def test_repeated_cross_scope_value_refuses_and_clears(self):
        self.run_scenario('duplicate-scope')


if __name__ == '__main__':
    unittest.main()
