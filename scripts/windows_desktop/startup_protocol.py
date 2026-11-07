"""Bounded startup messages; delegates request validation to the original bridge."""
import io
import json
from scripts.windows_portable.desktop_bridge import request,MAX_REQUEST


def parse_message(raw):
    if type(raw) is not str or len(raw.encode('utf-8'))>MAX_REQUEST:
        raise ValueError('STARTUP_MESSAGE_BOUNDS')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('STARTUP_DUPLICATE_FIELD')
            value[key]=item
        return value
    message=json.loads(raw,object_pairs_hook=pairs)
    if type(message) is not dict or set(message)!={'protocol','request'} or message['protocol']!='PARKWEAVE_STARTUP_V1':
        raise ValueError('STARTUP_PROTOCOL')
    encoded=(json.dumps(message['request'],ensure_ascii=True,separators=(',',':'))+'\n').encode('ascii')
    value=request(io.BytesIO(encoded))
    if value['action'] not in ('new','reopen'):raise ValueError('STARTUP_ACTION')
    return value
