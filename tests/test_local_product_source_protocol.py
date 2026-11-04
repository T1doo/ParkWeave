"""Source protocol bounds and Linux refusal only; native execution is separate."""
import json
import os
from pathlib import Path
import sys

import pytest

from scripts.windows_ci import local_product_source_protocol as protocol


def test_default_and_linux_guard_cannot_execute_composition(monkeypatch,capsys):
    def unexpected(*args):pytest.fail('platform refusal must precede any product work')
    monkeypatch.setattr(protocol,'composition',unexpected)
    monkeypatch.setattr(protocol,'compile_sources',unexpected)
    assert protocol.main([])==2
    assert json.loads(capsys.readouterr().out)['status']=='NOT_RUN'
    if sys.platform!='win32':
        assert protocol.main(['--run-protocol'])==2
        result=json.loads(capsys.readouterr().out)
        assert result['status']=='NATIVE_SERVER_REQUIRED' and result['activation_allowed'] is False


def test_pure_phase_fence_rejects_effects_without_invoking_them():
    fence=protocol.AuditFence();fence.active=True
    fence('open',('source.py','r',0))
    for event,args in [('open',('not-created','w',os.O_WRONLY)),('subprocess.Popen',()),
        ('ctypes.dlopen',()),('ctypes.dlsym',()),('socket.__new__',()),('os.mkdir',()),('os.chmod',())]:
        with pytest.raises(RuntimeError,match='PURE_PROTOCOL_OS_OPERATION_REFUSED'):fence(event,args)
    assert len(fence.denied)==7


def test_current_source_compiles_in_memory_and_one_push_window_is_fixed():
    root=Path(__file__).parents[1]
    result=protocol.compile_sources(root)
    assert result['files']>100 and result['bytecode_written'] is False
    workflow=(root/'.github/workflows/windows-server-engineering.yml').read_text()
    assert protocol.BEFORE in workflow and protocol.MARKER in workflow and protocol.REF in workflow
    assert 'github.run_attempt == 1' in workflow and 'github.event.repository.private == false' in workflow
