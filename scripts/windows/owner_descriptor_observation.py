"""Read-only, fixed-vocabulary comparison; never grants an owner mutation.
Ordered ACE byte equality is an observation, not an access-equivalence proof.
The original full-byte/control contract must still reject any changed input.
"""
import struct

CONTROL_BITS=((1,'OWNER_DEFAULTED'),(2,'GROUP_DEFAULTED'),(4,'DACL_PRESENT'),(8,'DACL_DEFAULTED'),(16,'SACL_PRESENT'),(32,'SACL_DEFAULTED'),(256,'DACL_AUTO_INHERIT_REQ'),(512,'SACL_AUTO_INHERIT_REQ'),(1024,'DACL_AUTO_INHERITED'),(2048,'SACL_AUTO_INHERITED'),(4096,'DACL_PROTECTED'),(8192,'SACL_PROTECTED'),(16384,'RM_CONTROL_VALID'),(32768,'SELF_RELATIVE'))

def _acl(value):
    if value is None:return {'kind':'NULL','revision':None,'aces':None,'slack':None,'reserved':None,'size':None}
    if type(value) is not bytes or not 8<=len(value)<=65535:raise ValueError('ACL_OBSERVATION_REFUSED')
    rev,reserved,size,count,reserved2=struct.unpack_from('<BBHHH',value)
    if rev not in (2,4) or size!=len(value) or size%4:raise ValueError('ACL_OBSERVATION_REFUSED')
    cursor=8;aces=[]
    for _ in range(count):
        if cursor+4>size:raise ValueError('ACL_OBSERVATION_REFUSED')
        ace_size=struct.unpack_from('<H',value,cursor+2)[0]
        if ace_size<4 or ace_size%4 or cursor+ace_size>size:raise ValueError('ACL_OBSERVATION_REFUSED')
        aces.append(value[cursor:cursor+ace_size]);cursor+=ace_size
    return {'kind':'ACL','revision':rev,'aces':tuple(aces),'slack':value[cursor:],'reserved':(reserved,reserved2),'size':size}

def compare_acl_control(before_acl,before_control,after_acl,after_control):
    # Never print/hash/return SID, ACL bytes, masks or opaque ACE payloads.
    result={'scope':'OWNER_DESCRIPTOR_READONLY','acl_observation':'UNAVAILABLE','ordered_ace_bytes':'UNAVAILABLE','strict_contract':'REFUSED','control_observation':'UNAVAILABLE','semantic_permission_change':'UNKNOWN','sacl_content':'NOT_QUERIED'}
    valid_control=all(type(v) is int and 0<=v<=65535 for v in (before_control,after_control))
    if valid_control:
        delta=before_control^after_control
        result.update(control_observation='AVAILABLE',control_equal_excluding_owner_defaulted=(before_control&~1)==(after_control&~1),control_changed_bits=[name for bit,name in CONTROL_BITS if delta&bit],unknown_control_bits_changed=bool(delta&0xc0))
    try:left=_acl(before_acl);right=_acl(after_acl)
    except ValueError:return result
    same=before_acl==after_acl
    result.update(acl_observation='AVAILABLE',raw_acl_equal=same,acl_kind_equal=left['kind']==right['kind'])
    if left['kind']==right['kind']=='ACL':
        result.update(ordered_ace_bytes='EQUAL' if left['revision']==right['revision'] and left['aces']==right['aces'] else 'DIFFERENT',revision_equal=left['revision']==right['revision'],capacity_equal=left['size']==right['size'],reserved_equal=left['reserved']==right['reserved'],slack_equal=left['slack']==right['slack'])
    elif left['kind']==right['kind']=='NULL':result['ordered_ace_bytes']='NOT_APPLICABLE'
    if valid_control and same and result['control_equal_excluding_owner_defaulted']:result['strict_contract']='UNCHANGED'
    return result
