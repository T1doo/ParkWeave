"""Bounded current-run result of the outer owned native stage command."""
import json
from pathlib import Path
import stat


def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate stage field')
        result[key]=value
    return result


def _constant(value):raise ValueError('invalid stage constant')


def read_command(path,binding):
    path=Path(path);info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024)) or path.resolve()!=path:raise ValueError('stage command path refused')
    with path.open('rb') as stream:data=stream.read(16*1024+1)
    if len(data)>16*1024:raise ValueError('stage command exceeds bound')
    row=json.loads(data.decode('utf-8'),object_pairs_hook=_object,parse_constant=_constant)
    if not isinstance(row,dict) or set(row)!={'schema','diagnostic_binding','exit_code','timed_out','cleanup'} or type(row['schema']) is not int or row['schema']!=1 or binding is None or row['diagnostic_binding']!=binding or type(row['exit_code']) is not int or not -(2**31)<=row['exit_code']<2**32 or type(row['timed_out']) is not bool or not isinstance(row['cleanup'],str) or row['cleanup'] not in ('NOT_STARTED','SUSPENDED_CHILD_STOPPED','OWNED_TREE_STOPPED','OWNED_TREE_STOP_UNCONFIRMED'):raise ValueError('current stage command result required')
    return row


def failure(row,case):
    if row['exit_code']==0 and not row['timed_out'] and row['cleanup']=='OWNED_TREE_STOPPED':return None
    value={'case':case,'status':'FAIL','exit_code':row['exit_code'],'phase':'final_stop','category':'TimeoutExpired' if row['timed_out'] else 'RuntimeError'}
    if row['cleanup']!='OWNED_TREE_STOPPED':value['reason']='CLEANUP_NOT_CONFIRMED'
    return value
