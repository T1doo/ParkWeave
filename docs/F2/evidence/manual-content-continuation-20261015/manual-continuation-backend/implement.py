from pathlib import Path
p=Path('src/parkweave/plan_source_conflicts.py');s=p.read_text();s=s.replace('from copy import deepcopy','from collections import Counter\nfrom copy import deepcopy',1)
s=s.replace("ACTIONS=('EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER')", "ACTIONS_V1=('EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER')\nCONTINUATION_ACTIONS=('KEEP_AND_CONTINUE','MERGE_NOTE')\nACTIONS=ACTIONS_V1+CONTINUATION_ACTIONS\nCONTINUATION_SCOPE='OWNER_NOTE_EXACT_LINE_CONTINUATION'\nMAX_CONDITIONS_V1=128",1)
s=s.replace("action:Literal['EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER']", "action:Literal['EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER','KEEP_AND_CONTINUE','MERGE_NOTE']",1)
s=s.replace("if self.action=='EDIT_NOTE':\n", "if self.action in ('EDIT_NOTE','MERGE_NOTE'):\n",1)
s=s.replace("        return self\n\n\ndef sha", "        if self.action in CONTINUATION_ACTIONS and self.card_id is None:raise ValueError('current opportunity required for explicit continuation')\n        if self.action=='MERGE_NOTE':\n            try:self.text.encode('utf-8')\n            except UnicodeError:raise ValueError('valid exact UTF-8 content required') from None\n        return self\n\n\ndef sha",1)
helpers='''

def line_coverage_v1(text,source_text):
    """Frozen bounded exact-line carriage; never a semantic obligation check."""
    if not isinstance(text,str) or not isinstance(source_text,str):
        return dict(coverage_known=False,coverage_satisfied=False,conditions=[])
    try:text.encode('utf-8');source_text.encode('utf-8')
    except UnicodeError:return dict(coverage_known=False,coverage_satisfied=False,conditions=[])
    required=[line for line in source_text.splitlines() if line.strip()]
    if not 1<=len(required)<=MAX_CONDITIONS_V1:
        return dict(coverage_known=False,coverage_satisfied=False,conditions=[])
    counts=Counter(required);present=Counter(text.splitlines());conditions=[]
    for line,count in counts.items():
        missing=max(0,count-present[line])
        conditions.append(dict(id=sha(dict(schema=1,kind='EXACT_NONEMPTY_SOURCE_LINE',line=line)),line=line,
            required_count=count,present_count=present[line],missing_count=missing,satisfied=missing==0))
    return dict(coverage_known=True,coverage_satisfied=all(row['satisfied'] for row in conditions),conditions=conditions)


def line_coverage(text,source_text):return line_coverage_v1(text,source_text)


def continuation_data_v1(note,source,baseline,baseline_epoch):
    return dict(schema=1,scope=CONTINUATION_SCOPE,baseline=deepcopy(baseline),baseline_epoch=baseline_epoch,
        manual={k:note[k] for k in ('text','text_sha256','revision','event_id')},incoming=deepcopy(source),
        **line_coverage_v1(note['text'],source['text']),manual_preserved=True,semantic_evaluated=False)


def continuation_snapshot(c,parent,note,source):
    if note is None:return None
    captured=next(m for m in note['source_package'] if m['slot']=='material_outline')
    row=c.execute('SELECT id,slot,version,text,source_kind,source_label,source_sha256,authenticity,xmin::text AS row_epoch FROM preparation_evidence WHERE preparation_id=%s AND id=%s AND slot=%s AND version=%s AND source_sha256=%s',
        (parent['id'],captured['id'],captured['slot'],captured['version'],captured['source_sha256'])).fetchone()
    baseline=None;epoch=None
    if row:
        epoch=row['row_epoch'];actual=op.normal({k:v for k,v in row.items() if k!='row_epoch'})
        if same(actual,captured):baseline=actual
        else:epoch=None
    return continuation_data_v1(note,source,baseline,epoch)


def continuation_basis(c,parent,basis):
    data=continuation_snapshot(c,parent,basis['note'],basis['source'])
    if not data or data['baseline'] is None or not data['coverage_known']:
        raise Conflict('known actual historical source and bounded source lines required')
    return dict(basis,schema=2,continuation=data)
'''
pos=s.index('\ndef _material(');s=s[:pos]+helpers+s[pos:]
start=s.index('def validate_embedded_event(');end=s.index('\n\ndef validate_ledger_links',start)
old=s[start:end].replace('def validate_embedded_event(','def validate_embedded_event_v1(',1)
# Old request/proof bytes and the complete old branch remain fixed.
new=old.replace('def validate_embedded_event_v1(','def validate_embedded_event_v2(',1)
new=new.replace("proof['version']!=VERSION", "proof['version']!=2",1)
new=new.replace("'case_versions_sha256','source_change'}", "'case_versions_sha256','source_change','continuation'}",1)
new=new.replace("basis['schema']!=VERSION", "basis['schema']!=2",1)
a=new.index("        if data.action in ('KEEP_MANUAL','DEFER'):");b=new.index('        return plan_event',a)
new=new[:a]+'''        if data.action not in CONTINUATION_ACTIONS or before is None or after is None:raise ValueError()
        snapshot=basis['continuation'];baseline=snapshot['baseline'];_material(baseline)
        expected=continuation_data_v1(before,basis['source'],baseline,snapshot['baseline_epoch'])
        captured=next(m for m in before['source_package'] if m['slot']=='material_outline')
        if (not same(snapshot,expected) or not same(baseline,captured) or
            not isinstance(snapshot['baseline_epoch'],str) or not re.fullmatch('[0-9]{1,20}',snapshot['baseline_epoch']) or
            not snapshot['coverage_known'] or after['revision']!=before['revision']+1 or after['event_id']!=plan_event['id'] or
            after['origin']!='MANUAL' or after['verified_package_sha256'] is not None or
            not same(after['source_ref'],source_ref(basis['source'])) or not same(after['source_package'],basis['materials'])):raise ValueError('continuation three-version binding invalid')
        text=before['text'] if data.action=='KEEP_AND_CONTINUE' else data.text
        if (after['text']!=text or (data.action=='MERGE_NOTE' and before['text'] not in text) or
            not line_coverage_v1(text,basis['source']['text'])['coverage_satisfied']):raise ValueError('explicit manual carriage proof invalid')
'''+new[b:]
wrapper='''

def validate_embedded_event(value,event):
    """Schema dispatch never reinterprets an old note decision as continuation."""
    try:
        proof=event['payload']['plan_event']['plan_note'];action=event['payload']['plan_event']['action']
        if type(proof['version']) is not int:raise ValueError()
        if proof['version']==1 and action in ACTIONS_V1:return validate_embedded_event_v1(value,event)
        if proof['version']==2 and action in CONTINUATION_ACTIONS:return validate_embedded_event_v2(value,event)
    except (KeyError,TypeError,AttributeError):pass
    raise ValueError('unsupported original note event schema or action')
'''
s=s[:start]+old+'\n\n'+new+wrapper+s[end:]
# Guard follow-up editing even when the material identity remains equal.
s=s.replace("    if same(note['source_ref'],source_ref(actual)):return []", """    if same(note['source_ref'],source_ref(actual)):
        rebased=next((e for e in reversed(plan['events']) if e['action'] in ('ACCEPT_SOURCE',)+CONTINUATION_ACTIONS and
            same(e['plan_note']['after_note']['source_ref'],note['source_ref'])),None)
        if note['origin']=='MANUAL' and rebased:
            reasons=[]
            if note['event_id']!=rebased['id']:reasons.append('OWNER_NOTE_CONTENT_EDIT_REQUIRES_RECONFIRMATION')
            coverage=line_coverage(note['text'],actual['text'])
            if not coverage['coverage_known']:reasons.append('OWNER_NOTE_SOURCE_LINES_UNKNOWN')
            elif not coverage['coverage_satisfied']:reasons.append('OWNER_NOTE_SOURCE_LINES_NOT_CARRIED')
            return reasons
        return []""",1)
s=s.replace("result=dict(scope=SCOPE,schema=VERSION", "result=dict(continuation=None,scope=SCOPE,schema=VERSION",1)
s=s.replace("    conflict=bool(note and note['source_ref']!=source_ref(basis['source']))", "    conflict=bool(note and adoption_blockers(c,parent,plan))",1)
s=s.replace("    if source_view['unknown_scope'] or source_blockers:state='UNKNOWN'", """    if note and not conflict and last and last['action'] in CONTINUATION_ACTIONS:
        _,_,_,_,states,_=service._inspect(store,c,parent,deepcopy(plan),observe=False)
        state='RESOLVED' if states['P1']=='VERIFIED' else 'CONTINUED_AWAITING_RECHECK'
    if source_view['unknown_scope'] or source_blockers:state='UNKNOWN'""",1)
needle="    action_requests={a:dict(template,action=a,text='' if a=='EDIT_NOTE' else None) for a in (['EDIT_NOTE'] if can_edit else [])+choices}\n"
replacement=needle+'''    continued=continuation_snapshot(c,parent,note,basis['source'])
    if continued is not None:
        continue_blocks=[]
        if continued['baseline'] is None:continue_blocks.append('ACTUAL_HISTORICAL_NOTE_SOURCE_REQUIRED')
        if not continued['coverage_known']:continue_blocks.append('BOUNDED_NONEMPTY_SOURCE_LINES_REQUIRED')
        eligible=bool(resolve_context and not locked and accept_capacity and not continue_blocks)
        new_basis=dict(basis,schema=2,continuation=deepcopy(continued)) if not continue_blocks else None
        continued.update(blocking_reasons=sorted(set(continue_blocks+blocks)),preview_sha256=sha(new_basis) if new_basis else None,
            can_keep_and_continue=bool(eligible and continued['coverage_satisfied']),can_merge=eligible)
        if continued['can_keep_and_continue']:action_requests['KEEP_AND_CONTINUE']=dict(template,expected_preview_sha256=continued['preview_sha256'],action='KEEP_AND_CONTINUE',text=None)
        if continued['can_merge']:action_requests['MERGE_NOTE']=dict(template,expected_preview_sha256=continued['preview_sha256'],action='MERGE_NOTE',text='')
    result['continuation']=continued
'''
assert needle in s;s=s.replace(needle,replacement,1)
# Command uses the matching old or new preview, preserving all legacy dumps.
needle="        if view['state']=='UNKNOWN':raise Conflict('unknown source inspection; preserve original request key')\n"
s=s.replace(needle,needle+"        if data.action in CONTINUATION_ACTIONS:basis=continuation_basis(c,parent,basis)\n        preview_sha=sha(basis)\n",1)
s=s.replace("data.expected_preview_sha256!=view['preview_sha256']", "data.expected_preview_sha256!=preview_sha",1)
s=s.replace("        before=deepcopy(view['note']);after=deepcopy(before);plan['revision']+=1", """        before=deepcopy(view['note']);after=deepcopy(before)
        if data.action in CONTINUATION_ACTIONS:
            text=before['text'] if data.action=='KEEP_AND_CONTINUE' else data.text
            if (not line_coverage(text,basis['source']['text'])['coverage_satisfied'] or
                data.action=='MERGE_NOTE' and before['text'] not in text):raise DefinitiveConflict(parent,p,key,data)
        plan['revision']+=1""",1)
s=s.replace("        if data.action in ('EDIT_NOTE','ACCEPT_SOURCE'):", "        if data.action in ('EDIT_NOTE','ACCEPT_SOURCE')+CONTINUATION_ACTIONS:\n",1)
s=s.replace("material_package=basis['materials'] if before is None or data.action=='ACCEPT_SOURCE' else before['source_package']", "material_package=basis['materials'] if before is None or data.action in ('ACCEPT_SOURCE',)+CONTINUATION_ACTIONS else before['source_package']",1)
needle="            after=dict(version=VERSION,revision=";idx=s.index(needle)
s=s[:idx]+"            content=data.text if data.action in ('EDIT_NOTE','MERGE_NOTE') else before['text'] if data.action=='KEEP_AND_CONTINUE' else basis['source']['text']\n"+s[idx:]
s=s.replace("text=data.text if data.action=='EDIT_NOTE' else basis['source']['text']", "text=content",1)
s=s.replace("text_sha256=digest(data.text if data.action=='EDIT_NOTE' else basis['source']['text']),origin='MANUAL' if data.action=='EDIT_NOTE' else 'SOURCE'", "text_sha256=digest(content),origin='SOURCE' if data.action=='ACCEPT_SOURCE' else 'MANUAL'",1)
s=s.replace("verified_package_sha256=before['verified_package_sha256'] if before and data.action=='EDIT_NOTE' else verified", "verified_package_sha256=None if data.action in CONTINUATION_ACTIONS else before['verified_package_sha256'] if before and data.action=='EDIT_NOTE' else verified",1)
s=s.replace("proof=dict(version=VERSION,request=request(data)", "proof=dict(version=2 if data.action in CONTINUATION_ACTIONS else VERSION,request=request(data)",1)
s=s.replace("        if final_basis!=basis or final['preview_sha256']!=data.expected_preview_sha256:", "        if data.action in CONTINUATION_ACTIONS:final_basis=continuation_basis(c,parent,final_basis)\n        if not same(final_basis,basis) or sha(final_basis)!=data.expected_preview_sha256:",1)
p.write_text(s)
for name in ('case_goal_results.py','case_opportunities.py','registered_dependencies.py','service_case_steps.py'):
 p=Path('src/parkweave')/name;s=p.read_text();s=s.replace("'KEEP_MANUAL','ACCEPT_SOURCE','DEFER'", "'KEEP_MANUAL','ACCEPT_SOURCE','DEFER','KEEP_AND_CONTINUE','MERGE_NOTE'");p.write_text(s)
