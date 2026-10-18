"""Local administrator configuration of two existing preparation permissions.

No identity, capability, catalogue, material or Run authority is issued here.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,ValidationError,model_validator
from . import preparation as prep,catalog_publication as catalog
from .case_step_assignments import _CaseStepTransactions
from .controlled_plans import binding_catalog_known
from .store import Store,Conflict,Denied,digest

SCOPE='EXISTING_PREPARATION_ACCESS_CONFIGURATION_V1'
TABLES=('principals','capability_grants','preparation_grants','preparation_catalog','authorization_audit')


class CatalogReference(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    service_id:Literal['synthetic-material-preparation']
    version:int=Field(ge=1,le=9999)


class Configuration(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    version:int=Field(ge=1,le=1)
    scope:Literal['EXISTING_PREPARATION_ACCESS_CONFIGURATION_V1']
    park_id:str=Field(min_length=1,max_length=100)
    org_id:str=Field(min_length=1,max_length=100)
    owner_id:str=Field(min_length=1,max_length=100)
    reviewer_id:str=Field(min_length=1,max_length=100)
    catalog:CatalogReference
    reason:str=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def references(self):
        for value in (self.park_id,self.org_id,self.owner_id,self.reviewer_id,self.reason):
            if value!=value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):
                raise ValueError('literal bounded references required')
        if self.owner_id==self.reviewer_id:raise ValueError('distinct existing participants required')
        return self


def load(path):
    """One explicitly selected bounded JSON file; never return its error values."""
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('duplicate key')
            result[k]=v
        return result
    try:
        flags=os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_NOFOLLOW',0)
        fd=os.open(Path(path),flags)
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('regular file required')
            data=stream.read(8193)
        if len(data)>8192:raise ValueError('bounded file required')
        value=json.loads(data.decode('utf-8'),object_pairs_hook=unique)
        return Configuration.model_validate(value)
    except (OSError,UnicodeError,ValueError,ValidationError):
        raise ValueError('bounded configuration JSON required; input values omitted') from None


class ExistingPreparationAccess:
    def __init__(self,store):
        self.store=store
        self._plain()

    def _plain(self):
        if type(self.store) is not Store or self.store.mode!='LOCAL':
            raise Denied('separate LOCAL administrator Store required')
        _CaseStepTransactions._unmixed(self)
        if getattr(self.store,'_ordinary_case_step_sources',None) is not None:
            raise Denied('separate administrator Store required')

    @contextmanager
    def _connection(self,read_only):
        self._plain()
        with self.store.connect() as c:
            if read_only:c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            c.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
            c.execute("SET LOCAL lock_timeout='3s'")
            c.execute("SET LOCAL statement_timeout='10s'")
            self._schema(c)
            yield c
            self._plain()

    @staticmethod
    def _schema(c):
        row=c.execute('SELECT max(version) v FROM public.schema_version').fetchone()
        if not row or row['v'] not in (32,33):raise Denied('existing business schema32/33 required')

    @staticmethod
    def _database(c):
        row=c.execute("""SELECT d.oid::text oid,d.datname name,
            pg_get_userbyid(d.datdba) owner,pg_postmaster_start_time() started,
            current_user::text actor,session_user::text session
            FROM pg_database d WHERE d.datname=current_database()""").fetchone()
        owners=c.execute("""SELECT t.relname name,pg_get_userbyid(t.relowner) owner
            FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='public' AND t.relkind='r' AND t.relname=ANY(%s)
            ORDER BY t.relname""",(list(TABLES),)).fetchall()
        allowed=(row['actor']==row['session']==row['owner'] and
                 len(owners)==len(TABLES) and all(r['owner']==row['owner'] for r in owners))
        # A fresh-state fence, not a signature or privileged cluster attestation.
        binding=dict(name=row['name'],oid=row['oid'],started=row['started'].isoformat(),
                     endpoint=[c.info.host,c.info.port],owner=row['owner'],tables=owners)
        return binding,allowed,row['actor']

    def _snapshot(self,c,data):
        binding,administrator,actor=self._database(c)
        issues=[];participants=[];actions=[]
        for id,role,capability,caps in sorted(((data.owner_id,'enterprise_operator','PREPARE',('READ','EXECUTE')),
                                            (data.reviewer_id,'park_specialist','REVIEW_ASSIGNED',('READ',)))):
            p=c.execute('SELECT id,park_id,org_id,role,active,xmin::text generation FROM public.principals WHERE id=%s',(id,)).fetchone()
            if not p or not p['active'] or (p['role'],p['park_id'],p['org_id'])!=(role,data.park_id,data.org_id):
                issues.append(dict(principal_id=id,code='CURRENT_SAME_SCOPE_ROLE_REQUIRED'))
            rights=[]
            for cap in caps:
                row=c.execute('SELECT principal_id,capability,park_id,org_id,active,revision,xmin::text generation FROM public.capability_grants WHERE principal_id=%s AND capability=%s',(id,cap)).fetchone()
                rights.append(row)
                try:
                    if not p:raise Denied('existing principal required')
                    self.store.check_capability(c,p,cap)
                except Denied:issues.append(dict(principal_id=id,code='CURRENT_'+cap+'_REQUIRED'))
            grant=c.execute('SELECT principal_id,park_id,org_id,capability,active,xmin::text generation FROM public.preparation_grants WHERE principal_id=%s AND capability=%s',(id,capability)).fetchone()
            action='INSERT' if grant is None else 'KEEP'
            if grant and (not grant['active'] or (grant['park_id'],grant['org_id'])!=(data.park_id,data.org_id)):
                action='BLOCKED';issues.append(dict(principal_id=id,code='EXISTING_PREPARATION_GRANT_NOT_REPLACEABLE'))
            actions.append(dict(principal_id=id,park_id=data.park_id,org_id=data.org_id,capability=capability,action=action))
            participants.append(dict(principal=p,capabilities=rights,preparation_grant=grant))
        value=c.execute('SELECT *,xmin::text generation FROM public.preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
                        (data.park_id,data.catalog.service_id,data.catalog.version)).fetchone()
        descriptor=None
        if value:
            try:
                head=catalog.proof(value)
                current=dict(value,**({'cooperative_catalog':head} if head is not None else {}))
                if not binding_catalog_known(current):raise Conflict('known synthetic source required')
                descriptor=digest(prep.canonical(value))
            except Conflict:issues.append(dict(code='CURRENT_ORIGINAL_CATALOG_REQUIRED'))
        else:issues.append(dict(code='CURRENT_ORIGINAL_CATALOG_REQUIRED'))
        state=dict(configuration=data.model_dump(mode='json'),database=binding,participants=participants,catalog=value)
        sha=digest(prep.canonical(state))
        return dict(scope=SCOPE,status='BLOCKED' if issues else 'READY_TO_APPLY' if any(a['action']=='INSERT' for a in actions) else 'NO_CHANGE',
                    plan_sha256=sha,database_sha256=digest(prep.canonical(binding)),
                    administrator_connection=administrator,actor=actor,issues=issues,changes=actions,
                    catalog=dict(service_id=data.catalog.service_id,version=data.catalog.version,source_sha256=descriptor),
                    read_only=True,applied=[])

    def preview(self,data):
        if type(data) is not Configuration:raise ValueError('typed configuration required')
        with self._connection(True) as c:return self._snapshot(c,data)

    def apply(self,data,expected_plan_sha256):
        if type(data) is not Configuration or not isinstance(expected_plan_sha256,str) or not re.fullmatch('[a-f0-9]{64}',expected_plan_sha256):
            raise ValueError('typed configuration and exact plan SHA required')
        with self._connection(False) as c:
            if not self._database(c)[1]:raise Denied('direct database and table owner session required')
            ids=sorted((data.owner_id,data.reviewer_id))
            for id in ids:self.store.lock_principal(c,id,exclusive=True)
            # Obtain every possible row/key wait before reading the current plan.
            c.execute('SELECT id FROM public.principals WHERE id=ANY(%s) ORDER BY id FOR SHARE',(ids,)).fetchall()
            for table in ('capability_grants','preparation_grants'):
                c.execute('SELECT principal_id,capability FROM public.'+table+' WHERE principal_id=ANY(%s) ORDER BY principal_id,capability FOR SHARE',(ids,)).fetchall()
            key=(data.park_id,data.catalog.service_id,data.catalog.version)
            catalog.lock(c,key)
            c.execute('SELECT service_id FROM public.preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s FOR SHARE',key).fetchone()
            self._schema(c)
            result=self._snapshot(c,data)
            if not result['administrator_connection']:raise Denied('current database and table owner session required')
            if result['issues']:raise Conflict('existing configuration prerequisites unavailable; inspect dry-run')
            if result['plan_sha256']!=expected_plan_sha256:raise Conflict('configuration changed; inspect fresh dry-run')
            for change in result['changes']:
                if change['action']!='INSERT':continue
                c.execute('INSERT INTO public.preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,%s,%s,%s)',
                          tuple(change[k] for k in ('principal_id','park_id','org_id','capability')))
                self.store.audit(c,change['principal_id'],'PREPARATION_ACCESS_CONFIG:'+change['capability']+':'+expected_plan_sha256,'ALLOWED')
                result['applied'].append(change)
            result.update(status='APPLIED' if result['applied'] else 'NO_CHANGE',read_only=False)
            return result
