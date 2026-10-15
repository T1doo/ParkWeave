"""Whole shipped HTML structural confirmation and strict proof guards; no browser."""
import subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode', ['explicit','no_confirmation','no_structure_confirmation','no_choice_proof','choice_first','unknown_apply','unknown_choice','hot_wrong_target','hot_wrong_plan','hot_wrong_source','hot_wrong_check','hot_wrong_choice','hot_wrong_reason','bad_post_receipt','bad_recovery','identity','instance','target','denied','late','cold_valid','cold_confirm_integer','cold_extra','cold_wrong_hash','cold_seed','cold_affected','cold_added_goals','cold_missing_structure'])
def test_template_structural_original_page_guards(mode):
    result=subprocess.run(['node',str(Path(__file__).with_name('template_structure_migration_guards.js')),mode],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
