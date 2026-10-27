import json,subprocess
from pathlib import Path
import pytest
from test_preparation import preparation_fixture,create,headers


def run(mode,data=None):
    result=subprocess.run(['node',str(Path(__file__).with_name('case_worklist_offline.js')),mode],
        input=json.dumps(data) if data is not None else None,capture_output=True,text=True,timeout=15,
        cwd=Path(__file__).resolve().parents[1])
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('mode',['missing_session','403_pending','late_identity','identity_aba','context_reset','late_403',
    'bad_shape','bad_target','bad_receipt','claim_complete','bad_cursor','too_many','pagination','cancelled',
    'late_navigation','open_run','open_materials','open_dispatch','open_receipt','open_localcase'])
def test_actual_worklist_ui_offline(mode):
    x=run(mode);assert x['mode']==mode and x['checks']>=2


def test_real_asgi_queue_response_renders_in_original_page_code(preparation_fixture):
    f=preparation_fixture;create(f)
    response=f[3].get('/api/cases/worklist',headers=headers(f[2]));assert response.status_code==200,response.text
    x=run('backend_projection',response.json());assert x['checks']>=3
