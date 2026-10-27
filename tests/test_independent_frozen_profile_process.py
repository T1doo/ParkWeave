import json,subprocess,sys
from pathlib import Path
from parkweave import bounded_planning as bp
from test_service_capability_catalog_actual import capability_catalog,register
from test_preparation import preparation_fixture


def test_new_process_frozen_action_profile_does_not_follow_today_actions(capability_catalog):
    release=register(capability_catalog)['release']
    payload=dict(release=release,registry=bp.REGISTRY,actions=bp.ACTIONS)
    code='''
import sys,json,importlib
from copy import deepcopy
from datetime import datetime,timezone
from parkweave import bounded_planning as bp
saved=json.load(sys.stdin)
bp.ACTIONS=deepcopy(bp.ACTIONS)
bp.ACTIONS['P1'][0]['commands'].append('SYNTHETIC_FUTURE_CURRENT_ACTION')
sys.modules.pop('parkweave.service_capability_contract',None)
c=importlib.import_module('parkweave.service_capability_contract')
assert c.REVISION_ONE_ACTIONS==saved['actions'], 'Frozen profile followed current actions at import'
assert c.validate_release_integrity(saved['release'],saved['registry'],saved['actions'])==saved['release']
try:c.validate_release(saved['release'],now=datetime(2026,10,14,tzinfo=timezone.utc))
except ValueError:pass
else:raise AssertionError('Frozen proof bypassed current action admission')
print('FROZEN_PROFILE_PASS_CURRENT_ADMISSION_DENIED')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=Path.cwd()/'src',input=json.dumps(payload),text=True,capture_output=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='FROZEN_PROFILE_PASS_CURRENT_ADMISSION_DENIED'
