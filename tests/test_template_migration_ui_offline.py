"""Full shipped template HTML action and privacy guards in offline Node VM."""
import subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode',['explicit','no_confirmation','no_choice_proof','choice_first','unknown_apply','unknown_choice','hot_wrong_target','hot_wrong_plan','hot_wrong_source','hot_wrong_check','hot_wrong_choice','hot_wrong_reason','bad_post_receipt','bad_recovery','identity','instance','target','denied','denied_invalid_json','denied_read_invalid_json','denied_unread_body','unknown_apply_non_json','late_denied_body','late'])
def test_template_migration_original_page_guards(mode):
    result=subprocess.run(['node',str(Path(__file__).with_name('template_migration_guards.js')),mode],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
