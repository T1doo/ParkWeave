"""Bounded user-selected SYNTHETIC file -> editable material candidate.

This parses bytes supplied in the request, never host paths. It neither extracts
facts nor persists evidence. Saving uses the original ADD_EVIDENCE command and
its permission/revision/idempotency/recovery rules.
"""
import base64
import binascii
import csv
import hashlib
import io
import json
from pathlib import PurePath
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from . import preparation as prep
from .store import Conflict, Denied, digest

CONTRACT='parkweave-material-file-candidate/1'
MAX_BYTES=8192
MAX_TEXT_UNITS=4000


class FileCandidateError(ValueError):
    """Stable non-private error code, never parser text containing user content."""


class Request(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    expected_preparation_revision: int=Field(ge=1,le=64)
    expected_case_id: UUID=Field(strict=False)
    expected_run_id: UUID=Field(strict=False)
    data_classification: Literal['SYNTHETIC_SAMPLE']
    file_name: str=Field(min_length=1,max_length=100)
    content_base64: str=Field(min_length=1,max_length=10924)


def units(text):
    return len(text.encode('utf-16-le'))//2


def _json_tree(value,depth=0,budget=None):
    if budget is None:budget=[256]
    budget[0]-=1
    if budget[0]<0 or depth>8:raise FileCandidateError('JSON_COMPLEXITY_LIMIT')
    if isinstance(value,str):
        if any(0xD800<=ord(c)<=0xDFFF for c in value):raise FileCandidateError('UTF8_TEXT_REQUIRED')
    elif isinstance(value,dict):
        for key,item in value.items():
            _json_tree(key,depth+1,budget);_json_tree(item,depth+1,budget)
    elif isinstance(value,list):
        for item in value:_json_tree(item,depth+1,budget)


def parse(file_name,content_base64):
    """Deterministic formatting only; no fact or authenticity inference."""
    if (type(file_name) is not str or not file_name or
            any(c in file_name for c in ('/','\\',':')) or
            any(ord(c)<32 or 0xD800<=ord(c)<=0xDFFF for c in file_name) or
            file_name!=file_name.strip() or file_name.endswith('.') or units(file_name)>80):
        raise FileCandidateError('SAFE_FILE_NAME_REQUIRED')
    suffix=PurePath(file_name).suffix.lower()
    formats={'.txt':'TEXT','.md':'MARKDOWN','.csv':'CSV','.json':'JSON'}
    if suffix not in formats:raise FileCandidateError('SUPPORTED_TEXT_FORMAT_REQUIRED')
    if file_name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise FileCandidateError('SAFE_FILE_NAME_REQUIRED')
    try:
        if type(content_base64) is not str or len(content_base64)>10924:raise ValueError()
        raw=base64.b64decode(content_base64,validate=True)
    except (ValueError,binascii.Error):raise FileCandidateError('VALID_BASE64_REQUIRED') from None
    if not raw or len(raw)>MAX_BYTES:raise FileCandidateError('FILE_BYTE_LIMIT')
    try:text=raw.decode('utf-8-sig')
    except UnicodeError:raise FileCandidateError('UTF8_TEXT_REQUIRED') from None
    if any(ord(c)<32 and c not in '\r\n\t' for c in text):raise FileCandidateError('PLAIN_TEXT_REQUIRED')
    # CSV record separators may be normalized by the writer, but quoted field
    # CRLF/CR bytes are data. Let csv.reader(newline='') distinguish them.
    if suffix!='.csv':text=text.replace('\r\n','\n').replace('\r','\n')
    if suffix=='.json':
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise FileCandidateError('JSON_DUPLICATE_FIELD')
                result[key]=value
            return result
        def constant(value):raise FileCandidateError('JSON_FINITE_VALUES_REQUIRED')
        try:
            # The decoder validates number grammar; retain tokens without doing
            # arithmetic, including tiny/huge exponents and long precision.
            obj=json.loads(text,object_pairs_hook=unique,parse_constant=constant,parse_float=str)
            if type(obj) not in (dict,list):raise FileCandidateError('JSON_OBJECT_OR_ARRAY_REQUIRED')
            _json_tree(obj)
            # Retain exact number lexemes, including precision and exponent.
            # Validation must never silently round the user's material.
        except FileCandidateError:raise
        except (ValueError,RecursionError,OverflowError):raise FileCandidateError('VALID_JSON_REQUIRED') from None
    elif suffix=='.csv':
        try:rows=list(csv.reader(io.StringIO(text,newline=''),strict=True))
        except csv.Error:raise FileCandidateError('VALID_CSV_REQUIRED') from None
        if not rows or not 1<=len(rows[0])<=32 or len(rows)>101:raise FileCandidateError('CSV_TABLE_LIMIT')
        headers=[cell.strip() for cell in rows[0]]
        if not all(headers) or len(headers)!=len(set(headers)):raise FileCandidateError('CSV_DISTINCT_HEADERS_REQUIRED')
        if any(len(row)!=len(headers) for row in rows):raise FileCandidateError('CSV_ROW_WIDTH_MISMATCH')
        # Quotes protect edge spaces from the original command's text.strip().
        stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n',quoting=csv.QUOTE_ALL);writer.writerows(rows);text=stream.getvalue()
    text=text.strip()
    if not text or units(text)>MAX_TEXT_UNITS:raise FileCandidateError('CANDIDATE_TEXT_LIMIT')
    raw_sha=hashlib.sha256(raw).hexdigest()
    label=f'SYNTHETIC 原文件候选 {file_name} SHA256 {raw_sha}'
    assert units(label)<=200
    return dict(file_name=file_name,file_bytes=len(raw),format=formats[suffix],raw_file_sha256=raw_sha,
                candidate_text=text,candidate_sha256=digest(text),source_kind='DOCUMENT_EXCERPT',
                source_label=label,authenticity='UNVERIFIED')


def candidate(store,token,preparation_id,data):
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        principal=store.auth(c,token,lock=True)
        if principal['role']!='enterprise_operator':raise Denied('original enterprise material owner required')
        parent,_=prep.entry_context(store,c,principal,preparation_id)
        if (parent['revision'],parent['case_id'],parent['run_id'])!=(data.expected_preparation_revision,data.expected_case_id,data.expected_run_id):
            raise Conflict('material file target changed; reread original preparation')
        if prep.case_write_blocked(c,parent):raise Conflict('closed or reconciling Case cannot accept new material candidates')
        result=parse(data.file_name,data.content_base64)
        return dict(contract=CONTRACT,preparation_id=str(parent['id']),case_id=str(parent['case_id']),
                    run_id=str(parent['run_id']),preparation_revision=parent['revision'],
                    scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',persisted=False,
                    original_submission_required=True,**result)
