"""Independent full original HTML counterexamples; simulated transport only."""
import subprocess
from pathlib import Path
import pytest
from test_service_instance_cold_web import HARNESS

@pytest.mark.parametrize('probe',['prepare_loss','denied_other_views'])
def test_independent_cold_state_guards(probe):
    script=HARNESS
    if probe=='prepare_loss':
        script=script.replace("admit(name);body=dto();}","admit(name);if(mode==='independent_prepare_loss'&&!lost){lost=true;throw Error('independent lost stage preparation response');}body=dto();}")
        marker="for(const name of stages.slice(1)){"
        inject="""if(mode==='independent_prepare_loss'){
const before=calls.length;await p.get('cold-stage-prepare').onclick();
const first=calls.slice(before);await p.get('cold-stage-prepare').onclick();
const writes=calls.filter(c=>c.path.startsWith('/api/service-instance-cold-inputs/prepare-stage?')&&c.options.method==='POST');
assert.equal(writes.length,1,'lost prepare-stage response allowed repeated POST instead of GET-only recovery');
assert(first.some(c=>c.path==='/api/service-instance-cold-inputs/recovery'),'lost prepare-stage response did not GET original key');
console.log(JSON.stringify({result:'PASS',probe:'prepare_loss'}));process.exit(0);
}for(const name of stages.slice(1)){"""
        assert marker in script
        script=script.replace(marker,inject)
        mode='independent_prepare_loss'
    else:
        marker="const snapshot=p.snapshot();denied=true;await p.get('cold-recover').onclick();"
        replacement="const snapshot=p.snapshot();p.read(\"servicePlanView={secret:'private original Case source'}\");p.get('service-plan-summary').textContent='private original Case source';denied=true;await p.get('cold-recover').onclick();assert.equal(p.read('servicePlanView'),null,'403 left original non-cold private view in memory');assert.equal(p.get('service-plan-summary').textContent,'','403 left original non-cold private content visible');"
        assert marker in script
        script=script.replace(marker,replacement)
        mode='revoked_403'
    result=subprocess.run(['node','-e',script,mode],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
