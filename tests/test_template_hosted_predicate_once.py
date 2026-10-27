"""Pure local contracts, no hosted/service/browser invocation."""
import json
import os
from pathlib import Path
import pytest
from scripts import template_hosted_predicate_once as m


def test_host_mismatch_never_reads_files_or_environment_values(monkeypatch):
    monkeypatch.setattr(m,'git',lambda *a:pytest.fail('source read after bad host'))
    report={'checks':{}}
    m.inspect({'GITHUB_REPOSITORY':'PRIVATE_VALUE_MUST_NOT_LEAK','PARKWEAVE_SESSION':'SECRET'},report,999)
    assert not all(report['checks'].values()) and all(type(v) is bool for v in report['checks'].values())
    assert 'PRIVATE_VALUE' not in json.dumps(report) and 'SECRET' not in json.dumps(report)


def test_metadata_reports_condition_without_executing_target(tmp_path):
    target=tmp_path/'NEVER_EXECUTED';target.write_bytes(b'NO_EXECUTABLE_PROGRAM');target.chmod(0o775)
    record=m.metadata(target)
    assert record['regular'] and record['trusted_owner'] and not record['not_group_or_other_writable']
    link=tmp_path/'link';link.symlink_to(target)
    assert m.metadata(link)['symlink'] and not m.metadata(link)['canonical']
    assert m.metadata(tmp_path/'missing')=={'exists':False}


def test_atomic_bounded_publication_keeps_prior_record(tmp_path):
    path=tmp_path/'diagnostic.json';m.publish(path,{'status':'NOT_COMPLETED'},initial=True)
    with pytest.raises(ValueError):m.publish(path,{'secret':'SYNTHETIC_'*2000})
    assert json.loads(path.read_text())=={'status':'NOT_COMPLETED'}
    m.publish(path,{'status':'CONDITIONS_REJECTED'})
    assert json.loads(path.read_text())=={'status':'CONDITIONS_REJECTED'}
