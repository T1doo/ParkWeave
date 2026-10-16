from pathlib import Path
root=Path(__file__).parent/'candidate/src/parkweave'
p=root/'case_resource_delivery.py';s=p.read_text().replace("    plan=parent['service_case_plan']\n", "    plan=parent['service_case_plan']\n    if plan['id']!=prior['context'].get('plan_id'):raise Conflict('original same plan reapproval required')\n");p.write_text(s)
p=root/'service_plan_approval.py';s=p.read_text();needle="                items[aid] = dict(id=aid, state='PROPOSED', proposal=e, approval=None, consumption=None)";replacement="""                anchor=b['context'].get('source_reapproval')
                if data.delivery.expected_link_revision is None:
                    if anchor is not None:raise ValueError()
                else:
                    anchor_keys={'link_id','link_revision','snapshot_sha256','previous_delivery_context','previous_approved_plan_revision',
                        'approved_plan_revision','source_adoption_event_id','source_adoption_revision','source_adoption_sha256','source_change_sha256'}
                    if (not isinstance(anchor,dict) or set(anchor)!=anchor_keys
                        or type(anchor['link_revision']) is not int or anchor['link_revision']!=data.delivery.expected_link_revision
                        or type(anchor['approved_plan_revision']) is not int or anchor['approved_plan_revision']!=data.delivery.expected_plan_revision
                        or type(anchor['previous_approved_plan_revision']) is not int or type(anchor['source_adoption_revision']) is not int
                        or not 1<=anchor['previous_approved_plan_revision']<anchor['source_adoption_revision']<=anchor['approved_plan_revision']<=64
                        or not isinstance(anchor['previous_delivery_context'],dict)
                        or anchor['previous_delivery_context'].get('plan_id')!=b['context'].get('plan_id')):raise ValueError()
                    for key in ('link_id','source_adoption_event_id'):UUID(anchor[key])
                    for key in ('snapshot_sha256','source_adoption_sha256','source_change_sha256'):
                        if not isinstance(anchor[key],str) or re.fullmatch('[a-f0-9]{64}',anchor[key]) is None:raise ValueError()
"""+needle;assert needle in s;s=s.replace(needle,replacement);p.write_text(s)
