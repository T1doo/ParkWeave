"""Current grants + atomic immutable review/outbox, append-only clarification lineage."""
import json
import uuid
from psycopg.types.json import Jsonb
from .domain import Intake
from .candidate_review import MockCandidateModel,project,document,fingerprint
from .store import Conflict,Denied,digest

def intent(store,c,claim):
    p,r,op=store.locked_execution(c,claim)
    if op['action']!='facts.assess' or op['state']!='PREPARED' or r['control_intent']!='CONTINUE':raise Conflict('not pending candidate review')
    data=Intake.model_validate(r['input'])
    if not data.candidate_review or digest(json.dumps(r['input'],sort_keys=True,ensure_ascii=False))!=r['fingerprint']:
        raise Conflict('candidate intent changed')
    store.check_execution(c,p,r)
    return p,r,op,data

def assess(store,claim,model=None,fail_before_commit=False):
    try:
        with store.connect() as c:p,r,op,data=intent(store,c,claim)
    except Denied:
        with store.connect() as c:
            p,r,op=store.locked_execution(c,claim);store.safe_failure(c,r,op,'AUTHORIZATION_REVOKED')
        return
    try:projections=project(data.fact_candidates,model or MockCandidateModel())
    except (ValueError,TypeError,KeyError):
        with store.connect() as c:
            p,r,op=store.locked_execution(c,claim);store.safe_failure(c,r,op,'INVALID_CANDIDATE_PROJECTION')
        return
    with store.connect() as c:
        try:p,r,op,current=intent(store,c,claim)
        except Denied:
            p,r,op=store.locked_execution(c,claim);store.safe_failure(c,r,op,'AUTHORIZATION_REVOKED');return
        if current.snapshot()!=data.snapshot():raise Conflict('candidate intent changed')
        rows=store.facts_query(c,p,data.fact_fields)
        now=c.execute('SELECT clock_timestamp() now').fetchone()['now']
        review=document(data.fact_fields,projections,rows,now);sha=fingerprint(review)
        c.execute('INSERT INTO fact_reviews(run_id,document,sha256) VALUES(%s,%s,%s)',(r['id'],Jsonb(review),sha))
        receipt={'source':'SYNTHETIC_CANDIDATE_REVIEW','review_sha256':sha,'qualification_decision':'NOT_EVALUATED',
                 'results':review['results'],'necessary_questions':review['necessary_questions']}
        c.execute("UPDATE operations SET state='VERIFIED',receipt=%s WHERE id=%s",(Jsonb(receipt),op['id']))
        c.execute("UPDATE runs SET state='SUCCEEDED',success_scope='CANDIDATES_REVIEWED_UNVERIFIED',lease_until=NULL,revision=revision+1 WHERE id=%s",(r['id'],))
        store.event(c,r['id'])
        if fail_before_commit:raise RuntimeError('SYNTHETIC review transaction interruption')

def authorized(store,c,token,run_id):
    p=store.auth(c,token,lock=True);r=store.scoped_run(c,p,run_id)
    if p['role']!='enterprise_operator' or not r['input'].get('candidate_review'):raise Denied('candidate review unavailable')
    store.check_fields(c,p,r['input']['fact_fields'],'READ')
    review=c.execute('SELECT document,sha256 FROM fact_reviews WHERE run_id=%s',(run_id,)).fetchone()
    if not review:raise Conflict('candidate review not ready')
    return p,r,review

def read(store,token,run_id):
    with store.connect() as c:
        p,r,review=authorized(store,c,token,run_id)
        links=c.execute('SELECT parent_run_id,decision,child_run_id FROM fact_followups WHERE parent_run_id=%s OR child_run_id=%s ORDER BY created_at',(run_id,run_id)).fetchall()
        return review|{'run_id':str(run_id),'followups':links}

def followup(store,token,run_id,key,data):
    request_hash=digest(json.dumps(data.model_dump(),sort_keys=True,ensure_ascii=False))
    with store.connect() as c:
        p,r,review=authorized(store,c,token,run_id)
        store.check_capability(c,p,'CONTROL')
        if review['sha256']!=data.review_sha256:raise Conflict('parent review hash changed')
        # Recheck current WRITE/EXECUTE on retries, not just when key was first used.
        if data.decision=='ANSWER':
            store.check_execution(c,p,r)
            store.check_fields(c,p,[a.field for a in data.answers],'WRITE')
            if any(a.field not in r['input']['fact_fields'] for a in data.answers):raise Conflict('answer field outside review')
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('clarification:'+str(run_id)+':'+key,))
        old=c.execute('SELECT * FROM fact_followups WHERE parent_run_id=%s AND request_key=%s',(run_id,key)).fetchone()
        if old:
            if old['fingerprint']!=request_hash:raise Conflict('clarification key fingerprint mismatch')
            return {'decision':old['decision'],'run_id':str(old['child_run_id']) if old['child_run_id'] else None,'parent_run_id':str(run_id)}
        child=None
        if data.decision=='ANSWER':
            combined=r['input'].get('fact_candidates',[])+[a.model_dump()|{'origin':'USER_STATEMENT'} for a in data.answers]
            if len(combined)>12:raise Conflict('candidate source limit reached')
            intake=Intake.model_validate(r['input']|{'fact_candidates':combined})
            snapshot=intake.snapshot()
            if len(json.dumps(snapshot,ensure_ascii=False).encode())>16384:raise Conflict('combined candidate input exceeds 16 KiB')
            child=uuid.uuid4();child_key='clarification-'+str(uuid.uuid4())
            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state) VALUES(%s,%s,%s,%s,'SYNTHETIC',%s,%s,%s,'QUEUED')",
                      (child,p['id'],p['park_id'],p['org_id'],child_key,digest(json.dumps(snapshot,sort_keys=True,ensure_ascii=False)),Jsonb(snapshot)))
            c.execute("INSERT INTO operations(id,run_id,action,state) VALUES(%s,%s,'facts.assess','PREPARED')",(uuid.uuid4(),child))
            store.event(c,child)
        c.execute('INSERT INTO fact_followups(parent_run_id,request_key,fingerprint,decision,child_run_id) VALUES(%s,%s,%s,%s,%s)',(run_id,key,request_hash,data.decision,child))
        return {'decision':data.decision,'run_id':str(child) if child else None,'parent_run_id':str(run_id)}
