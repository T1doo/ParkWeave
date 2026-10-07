"""Owner-only same-Case record navigation; existing assignment facts never grant access.

A read-only transaction projects existing metadata. Stored records are not
current acceptance checks; commands still revalidate independently.
"""
from . import preparation as prep, request_intents as intents, readiness
from .store import Denied
from . import executor_receipts as er


def read(store,token,id):
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        p=store.auth(c,token,lock=True)
        if p['role']!='enterprise_operator':raise Denied('own Case path required')
        prep.grant(store,c,p,'PREPARE')
        parent=c.execute('SELECT * FROM preparations WHERE id=%s AND owner_id=%s AND park_id=%s AND org_id=%s',
                         (id,p['id'],p['park_id'],p['org_id'])).fetchone()
        if not parent or parent['namespace']!='SYNTHETIC':raise Denied('own synthetic Case path unavailable')
        run=store.scoped_run(c,p,parent['run_id'])
        case=c.execute('SELECT id,state FROM cases WHERE id=%s AND run_id=%s',(parent['case_id'],run['id'])).fetchone()
        if not case:raise Denied('Case Run binding unavailable')
        available=bool(c.execute("""SELECT 1 FROM run_assignments a JOIN principals e ON e.id=a.principal_id
          AND e.park_id=a.park_id AND e.org_id=a.org_id JOIN capability_grants g ON g.principal_id=e.id
          AND g.park_id=e.park_id AND g.org_id=e.org_id AND g.capability='READ' AND g.active
          WHERE a.run_id=%s AND a.park_id=%s AND a.org_id=%s AND a.active AND e.active
          AND e.role='service_executor' LIMIT 1""",(run['id'],parent['park_id'],parent['org_id'])).fetchone())
        plan=c.execute('SELECT id,revision FROM controlled_plans WHERE preparation_id=%s',(id,)).fetchone()
        link=c.execute('SELECT id FROM case_resource_links WHERE preparation_id=%s AND case_id=%s AND run_id=%s AND owner_id=%s AND park_id=%s AND org_id=%s ORDER BY revision DESC LIMIT 1',(id,parent['case_id'],run['id'],p['id'],p['park_id'],p['org_id'])).fetchone()
        dispatch=c.execute('SELECT d.id,o.state FROM service_dispatches d LEFT JOIN service_dispatch_offers o ON o.id=d.current_offer_id AND o.dispatch_id=d.id WHERE d.preparation_id=%s',(id,)).fetchone()
        receipt=er.current_step(c,parent)
        if receipt and tuple(receipt[k] for k in ('case_id','run_id','owner_id','park_id','org_id'))!=(parent['case_id'],run['id'],p['id'],p['park_id'],p['org_id']):
            receipt=None
        local=c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s AND case_id=%s',(id,parent['case_id'])).fetchone()
        source,sha=readiness._sources(store,c,parent,p);material=readiness._view(parent,source,sha)
        return {'scope':'OWNER_SAME_CASE_READ_ONLY_RECORD_PATH','role':p['role'],'preparation_id':parent['id'],
          'preparation_revision':parent['revision'],'case_id':case['id'],'run_id':run['id'],'case_state':case['state'],
          'request':{'recorded':intents.view(parent)['recorded'],'coverage_state':intents.state(parent)},
          'plan':{'recorded':bool(plan),'record_id':plan['id'] if plan else None,'revision':plan['revision'] if plan else None},
          'materials':{'state':parent['state'],'assessment_state':material['state'],'local_truth':material['current_truth']},
          'resources':{'recorded':bool(link)},'dispatch':{'recorded':bool(dispatch),'offer_state':dispatch['state'] if dispatch else None},
          'receipt':{'recorded':bool(receipt),'state':receipt['state'] if receipt else None},
          'local_record_state':local['state'] if local else 'NOT_STARTED',
          'existing_run_access':{'state':'EXISTING_ASSIGNMENT_AVAILABLE' if available else 'BLOCKED_NO_EXISTING_ASSIGNMENT',
             'candidate_available':available,'scope':'EXACT_CURRENT_CASE_RUN_EXISTING_READ_ONLY','creates_access':False,
             'next_action':'ASSIGNED_REVIEWER_SELECTS_EXISTING_EXECUTOR' if available else 'KEEP_BLOCKED_CONTACT_EXISTING_AUTHORITY'},
          'record_acceptance':'NOT_REVALIDATED_BY_THIS_READ','authorization_writes':False,'business_writes':False,
          'automatic_execution':False,'qualification_truth':'UNKNOWN','case_goal_completed':False,'external_fulfillment':False}
