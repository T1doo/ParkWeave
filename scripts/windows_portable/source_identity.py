"""Exact source identity for Git builds and explicit uncommitted snapshots.

Identity binds bytes only. It never issues native acceptance or grants execution.
"""
import re


def validate(runtime):
    if type(runtime) is not dict:raise ValueError('RUNTIME_SOURCE_IDENTITY')
    keys=set(runtime)
    if keys=={'source_commit','manifest_sha256'}:field,width='source_commit',40
    elif keys=={'source_snapshot_sha256','manifest_sha256'}:field,width='source_snapshot_sha256',64
    else:raise ValueError('RUNTIME_SOURCE_IDENTITY')
    for key,size in ((field,width),('manifest_sha256',64)):
        if type(runtime[key]) is not str or not re.fullmatch('[0-9a-f]{'+str(size)+'}',runtime[key]):
            raise ValueError('RUNTIME_SOURCE_IDENTITY')
    return dict(runtime)


def from_manifest(manifest,manifest_sha256):
    commit=manifest.get('source_commit');snapshot=manifest.get('source_snapshot_sha256')
    if (commit is None)==(snapshot is None):raise ValueError('RUNTIME_SOURCE_IDENTITY')
    key='source_commit' if commit is not None else 'source_snapshot_sha256'
    return validate({key:commit if commit is not None else snapshot,'manifest_sha256':manifest_sha256})


def matches_manifest(manifest,runtime):
    try:return validate(runtime)==from_manifest(manifest,runtime['manifest_sha256'])
    except (ValueError,KeyError,TypeError):return False
