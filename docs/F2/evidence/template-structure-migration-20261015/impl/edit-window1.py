from pathlib import Path
p=Path('src/parkweave/template_migration.py')
s=p.read_text().replace('from uuid import UUID','from uuid import UUID\nfrom typing import Literal').replace('from pydantic import BaseModel, ConfigDict, Field','from pydantic import BaseModel, ConfigDict, Field, field_validator')
s=s.replace('\n\n\n@contextmanager\ndef source_connection', '''

class StructureApply(Apply):
    expected_structure_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    confirm_structure_change: Literal[True]

    @field_validator('confirm_structure_change', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('explicit true structure confirmation required')
        return value


def parse_apply_request(patch):
    """Historical nine-key requests and explicitly confirmed structure requests differ."""
    model = StructureApply if 'structure_change' in patch else Apply
    return model.model_validate(patch['request'])


@contextmanager
def source_connection''')
needle='\ndef validate_plan(parent,plan):'
insert='''
def structure_change(parent, plan, before, target):
    """Only strengthen template duties already declared and adopted by this Case.

    No Case goal, preview, step contract or original adoption is rewritten. The
    proof is rebuilt from those immutable inputs on every read and recovery.
    """
    old=before['snapshot'];new=target['snapshot']
    a=old['definition'];b=new['definition']
    if a['required_goals']==b['required_goals'] and a['steps']==b['steps']:
        return None
    from . import bounded_planning as planning, registered_dependencies as dependencies
    try:
        TemplateDraft.model_validate(a);TemplateDraft.model_validate(b)
        goals=a['required_goals'];declared=plan['required_goals']
        if (new['content_version']<=old['content_version'] or old['scope']!=new['scope'] or
            any(a[k]!=b[k] for k in ('service_id','service_version','parameter_schema')) or
            any(old[k]!=new[k] for k in ('registry_sha256','contract_sha256')) or
            b['required_goals'][:len(goals)]!=goals or len(b['required_goals'])<=len(goals) or
            plan.get('partial_adoption') is True or
            declared!=plan['binding']['request_intent']['required_goals'] or
            declared!=plan['adoption_preview']['required_goals'] or
            plan['goal_coverage']!=plan['adoption_preview']['goal_coverage'] or
            not set(b['required_goals'])<=set(declared) or
            any(step not in b['steps'] for step in a['steps'])):
            raise ValueError()
        steps={step['adapter_id']:step for step in plan['steps']}
        for template_step in b['steps']:
            case_step=steps[template_step['id']]
            if (case_step['adapter_revision']!=template_step['adapter_revision'] or
                case_step['depends_on']!=template_step['depends_on'] or
                case_step['contract']['id']!=template_step['id'] or
                case_step['contract']['revision']!=template_step['adapter_revision'] or
                case_step['contract']['depends_on']!=template_step['depends_on']):
                raise ValueError()
        added_goals=b['required_goals'][len(goals):]
        coverage={item['goal']:item for item in plan['goal_coverage']}
        for goal in b['required_goals']:
            compiled,_=planning.compile([goal])
            if coverage[goal]!=compiled[0] or compiled[0]['status']!='SUPPORTED_PREVIEW':raise ValueError()
        old_ids={step['id'] for step in a['steps']}
        added_steps=[step['id'] for step in b['steps'] if step['id'] not in old_ids]
        seeds=sorted(set(added_steps)|{planning.GOALS[goal] for goal in added_goals})
        affected=dependencies.closure(plan['steps'],seeds)
        if a['source']!=b['source']:affected=set(steps)
        binding=dict(preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
            plan_id=plan['id'],required_goals=declared,initial_request=plan['binding']['request_intent'],
            initial_adopt_fingerprint=plan['events'][0]['fingerprint'],adoption_preview=plan['adoption_preview'],
            goal_coverage=plan['goal_coverage'],steps=[dict(id=s['id'],adapter_id=s['adapter_id'],adapter=s['adapter'],
                adapter_revision=s['adapter_revision'],depends_on=s['depends_on'],contract=s['contract']) for s in plan['steps']])
        return dict(version=1,kind='REGISTERED_GOAL_STRENGTHENING',before_release_id=before['release_id'],
            before_release_sha256=before['release_sha256'],target_release_id=target['release_id'],target_release_sha256=target['release_sha256'],
            before_definition_sha256=old['definition_sha256'],target_definition_sha256=new['definition_sha256'],
            added_goals=added_goals,added_template_steps=added_steps,seed_adapters=seeds,
            affected_step_ids=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected],
            preserved_step_ids=[s['id'] for s in plan['steps'] if s['adapter_id'] not in affected],
            case_binding_sha256=sha(normal(binding)))
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        raise Conflict('UPGRADE_SCOPE_UNSUPPORTED: original Case goal and registered closure proof required')


def validate_plan(parent,plan):'''
s=s.replace(needle,insert)
s=s.replace("patch=event['template_upgrade'];request=Apply.model_validate(patch['request'])", "patch=event['template_upgrade'];request=parse_apply_request(patch)")
s=s.replace("if set(patch)!={'request','origin_binding','previous_release','target_release','check','choice','affected','preserved','source_changed'}:raise ValueError()", "structural='structure_change' in patch\n            keys={'request','origin_binding','previous_release','target_release','check','choice','affected','preserved','source_changed'}\n            if set(patch)!=(keys|{'structure_change'} if structural else keys):raise ValueError()")
s=s.replace("ids=[s['id'] for s in plan['steps']]\n            if (not _compatible(before['snapshot'],target['snapshot']) or patch['source_changed'] is not changed or\n                patch['affected']!=(ids if changed else []) or patch['preserved']!=([] if changed else ids) or", "ids=[s['id'] for s in plan['steps']]\n            proof=structure_change(parent,plan,before,target)\n            if structural:\n                if (proof is None or patch['structure_change']!=proof or\n                    request.expected_structure_sha256!=sha(proof) or request.confirm_structure_change is not True):raise ValueError()\n            elif proof is not None or not _compatible(before['snapshot'],target['snapshot']):raise ValueError()\n            affected=proof['affected_step_ids'] if proof else ids if changed else []\n            preserved=[id for id in ids if id not in affected]\n            if (patch['source_changed'] is not changed or\n                patch['affected']!=affected or patch['preserved']!=preserved or")
old="""    if source!=original:
        for step in plan['steps']:sources[step['adapter_id']]['adopted_template_source']=deepcopy(source)
"""
new=old+"""    for step in plan['steps']:
        # Append-only structure proofs survive later description/source releases.
        # Only this original step's affected events enter its source identity.
        proofs=[sha(e['template_upgrade']['structure_change']) for e in plan['events']
            if e['action']==ACTION and 'structure_change' in e['template_upgrade'] and step['id'] in e['template_upgrade']['affected']]
        if proofs:sources[step['adapter_id']]['adopted_template_structures']=proofs
"""
s=s.replace(old,new)
s=s.replace("    if not _compatible(effective['snapshot'],target['snapshot']):blockers.append('UPGRADE_SCOPE_UNSUPPORTED')\n    changed=", "    proof=None\n    try:\n        proof=structure_change(parent,plan,effective,target) if plan else None\n        if proof is None and not _compatible(effective['snapshot'],target['snapshot']):blockers.append('UPGRADE_SCOPE_UNSUPPORTED')\n    except Conflict:blockers.append('UPGRADE_SCOPE_UNSUPPORTED')\n    changed=")
s=s.replace("    if changed and plan and any(plans._manual_lock(plan,s) for s in plan['steps']):blockers.append('LOCK_CONFLICT')", "    affected=proof['affected_step_ids'] if proof else ids if changed else []\n    if proof:\n        binding_issues,issues,_,_,states,_=plans._inspect(checker.consumer.store,c,parent,deepcopy(plan),observe=False,fresh_clock=True)\n        if binding_issues or any(states[s['adapter_id']]!='VERIFIED' for s in plan['steps']):blockers.append('CURRENT_VERIFIED_CASE_PLAN_REQUIRED')\n    if plan and any(s['id'] in affected and plans._manual_lock(plan,s) for s in plan['steps']):blockers.append('LOCK_CONFLICT')")
s=s.replace("    verification_events=len(ids) if changed else 0", "    verification_events=len(affected)")
s=s.replace("        affected=ids if changed else [],preserved=[] if changed else ids,choice_revision=choice['revision'] if choice else 0,", "        affected=affected,preserved=[id for id in ids if id not in affected],\n        structure_change=proof,structure_sha256=sha(proof) if proof else None,requires_structure_confirmation=proof is not None,\n        choice_revision=choice['revision'] if choice else 0,")
s=s.replace("            origin=deepcopy(instance['binding'])\n            plan['revision']+=1", "            proof=projection['structure_change']\n            if proof is not None:\n                if not isinstance(data,StructureApply):raise Conflict('explicit structure confirmation required; use apply-structure')\n                if data.expected_structure_sha256!=sha(proof) or data.confirm_structure_change is not True:raise Conflict('structure confirmation proof changed')\n            elif isinstance(data,StructureApply):raise Conflict('current structural change required')\n            origin=deepcopy(instance['binding'])\n            plan['revision']+=1")
s=s.replace("check=check,choice=events[-1],affected=projection['affected'],preserved=projection['preserved'],source_changed=bool(projection['affected']))", "check=check,choice=events[-1],affected=projection['affected'],preserved=projection['preserved'],\n                source_changed=before['snapshot']['definition']['source']!=target['snapshot']['definition']['source'])\n            if proof is not None:event['template_upgrade']['structure_change']=proof")
p.write_text(s)
p=Path('src/parkweave/service_case_steps.py');s=p.read_text().replace("from .template_migration import Apply,fingerprint\n                    request=Apply.model_validate(event['template_upgrade']['request'])", "from .template_migration import parse_apply_request,fingerprint\n                    request=parse_apply_request(event['template_upgrade'])")
p.write_text(s)
p=Path('src/parkweave/template_upgrade.py');s=p.read_text()
old="""        classification = 'BREAKING_REJECTED' if breaking else 'LOCK_CONFLICT' if any(s == 'LOCK_CONFLICT' for s in states.values()) or (locked and needs) else 'NEEDS_RECHECK' if needs else 'COMPATIBLE'"""
new="""        lock_conflict=any(s=='LOCK_CONFLICT' for s in states.values()) or (locked and needs)
        if plan and not breaking and (a['required_goals']!=b['required_goals'] or a['steps']!=b['steps']):
            from .template_migration import structure_change
            try:
                proof=structure_change(parent,plan,dict(release_id=comparison['release_id'],release_sha256=sha(comparison),snapshot=comparison),
                    dict(release_id=new['release_id'],release_sha256=target_sha,snapshot=new))
                lock_conflict=any(s=='LOCK_CONFLICT' for s in states.values()) or any(s.get('manual_lock') and s['id'] in proof['affected_step_ids'] for s in plan['steps'])
            except Conflict:pass
        classification = 'BREAKING_REJECTED' if breaking else 'LOCK_CONFLICT' if lock_conflict else 'NEEDS_RECHECK' if needs else 'COMPATIBLE'"""
s=s.replace(old,new)
s=s.replace("    @app.get('/api/template-upgrade/{instance_id}/apply-requests/{key}')", "    @app.post('/api/template-upgrade/{instance_id}/apply-structure')\n    def apply_structure(instance_id: UUID, data: template_migration.StructureApply, authorization: str | None = Header(default=None), idempotency_key: str = Header()):\n        return checker.apply(token(authorization), instance_id, idempotency_key, data)\n\n    @app.get('/api/template-upgrade/{instance_id}/apply-requests/{key}')")
p.write_text(s)
