"""Actual client controls, including parent-review unified-preview button gap."""
import json
import subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('mode',['busy','recovery','corrupt','readonly','plan_busy','idle'])
def test_dependency_preview_disabled_with_original_opportunity_controls(mode):
    p=subprocess.run(['node','tests/plan_reapproval_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr
    x=json.loads(p.stdout);assert x['mode']==mode and x['disabled']==(mode!='idle')

@pytest.mark.parametrize('mode',['body','local_body'])
def test_reapproval_client_exact_old_new_binding_and_first_delivery_shape(mode):
    p=subprocess.run(['node','tests/plan_reapproval_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr
    x=json.loads(p.stdout);assert x['checks']==16 and x['HTTP']=='NOT_RUN'


def test_reapproval_mode_and_case_aba_cannot_revive_old_context():
    p=subprocess.run(['node','tests/plan_reapproval_client_probes.js','aba'],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr
    x=json.loads(p.stdout);assert x['checks']==4 and x['HTTP']=='NOT_RUN'
