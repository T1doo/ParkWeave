"""Documented restricted-group postconditions, no native token operations."""
from copy import deepcopy
import json
import pytest
from scripts.windows_portable import restricted_token_candidate as t
from scripts.windows_ci.native_failure_diagnostics import detail


def snapshots(before=15,observed=16):
    base={8:1,1:b'USER',2:{b'ADMIN':before,b'OTHER':7},3:{(23,0):2,(24,0):2}}
    derived={8:1,1:b'USER',2:{b'ADMIN':observed,b'OTHER':7},3:{(23,0):2}}
    return base,derived


@pytest.mark.parametrize('before,observed',[(15,16),(15,17),(15,24),(15,25),(7,16),(7,17),(6,16),(16,16)])
def test_disabled_group_can_lose_ignored_flags_but_never_regain_allow_access(before,observed):
    base,derived=snapshots(before,observed);old=deepcopy((base,derived))
    t._check(base,derived,{b'ADMIN'},(23,0))
    assert (base,derived)==old
    assert not t._RestrictedPrimaryCandidate.launch_ready


@pytest.mark.parametrize('before,observed',[(15,0),(15,1),(15,18),(15,20),(15,22),(6,17),(15,0x20000010)])
def test_missing_deny_bit_enabled_bits_or_new_flags_are_rejected(before,observed):
    base,derived=snapshots(before,observed)
    with pytest.raises(t.TokenGroupRefused) as caught:t._check(base,derived,{b'ADMIN'},(23,0))
    public=detail(caught.value,'TokenRefused')
    assert public['token_group']==dict(scope='REQUESTED_DISABLED',before=before,observed=observed)
    assert 'ADMIN' not in json.dumps(public) and 'USER' not in json.dumps(public)


@pytest.mark.parametrize('observed',[0,1,6,8,16,23])
def test_unrequested_group_must_still_be_identical(observed):
    base,derived=snapshots();derived[2][b'OTHER']=observed
    with pytest.raises(t.TokenGroupRefused) as caught:t._check(base,derived,{b'ADMIN'},(23,0))
    assert caught.value.group_scope=='UNCHANGED_GROUP'


@pytest.mark.parametrize('damage',['user','type','added-group','removed-group','added-privilege','enabled-privilege'])
def test_membership_identity_and_privilege_guards_remain(damage):
    base,derived=snapshots()
    if damage=='user':derived[1]=b'OTHER_USER'
    elif damage=='type':derived[8]=2
    elif damage=='added-group':derived[2][b'NEW']=16
    elif damage=='removed-group':derived[2].pop(b'OTHER')
    elif damage=='added-privilege':derived[3][(999,0)]=0
    else:derived[3][(24,0)]=2
    with pytest.raises(t.TokenRefused):t._check(base,derived,{b'ADMIN'},(23,0))


def test_group_diagnostic_rejects_non_numeric_or_private_fields():
    error=t.TokenGroupRefused('PRIVATE_SCOPE','PRIVATE_SID',True)
    public=detail(error,'TokenRefused')
    assert public['token_group']==dict(details='UNAVAILABLE')
    assert 'PRIVATE' not in json.dumps(public)
