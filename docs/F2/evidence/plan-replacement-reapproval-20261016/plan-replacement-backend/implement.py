from pathlib import Path
root=Path('/workspace/ParkWeave/.runtime/plan-replacement-backend/candidate/src/parkweave')
p=root/'case_resource_delivery.py';s=p.read_text();s=s.replace('from pydantic import AwareDatetime, Field, field_validator','from pydantic import AwareDatetime, Field, field_validator, model_validator')
s=s.replace('    expected_link_revision: int | None = Field(default=None, ge=1, le=64)\n','''    expected_link_revision: int | None = Field(default=None, ge=1, le=64)
    expected_previous_plan_id: UUID | None = Field(default=None, strict=False)

    @model_validator(mode='after')
    def replacement_requires_original_link(self):
        if self.expected_previous_plan_id is not None and self.expected_link_revision is None:
            raise ValueError('replacement requires exact original association revision')
        return self
''',1)
s=s.replace("    if not historical and (not approval or not approval.enabled or not approval.source_reapproval_enabled):", "    replacement=getattr(data,'expected_previous_plan_id',None) is not None\n    if not historical and (not approval or not approval.enabled or not (approval.plan_replacement_enabled if replacement else approval.source_reapproval_enabled)):")
s=s.replace("own=own_proof.get('context',{}).get('source_reapproval',{})", "own_context=own_proof.get('context',{})\n        own=own_context.get('plan_replacement',{}) if replacement else own_context.get('source_reapproval',{})")
s=s.replace("    current_plan=parent['service_case_plan'];plan=current_plan", """    if replacement:
        from .plan_replacement_compatibility import binding as replacement_binding
        return dict(context,plan_replacement=replacement_binding(parent,data,anchor,prior,historical=historical))
    current_plan=parent['service_case_plan'];plan=current_plan""")
s=s.replace("**({'expected_link_revision':data.expected_link_revision} if getattr(data,'expected_link_revision',None) is not None else {}))", "**({'expected_link_revision':data.expected_link_revision} if getattr(data,'expected_link_revision',None) is not None else {}),\n            **({'expected_previous_plan_id':str(data.expected_previous_plan_id)} if data.expected_previous_plan_id is not None else {}))")
s=s.replace("    anchor=expected.get('source_reapproval')", "    anchor=expected.get('plan_replacement') if 'plan_replacement' in expected else expected.get('source_reapproval')")
s=s.replace('from .service_plan_approval import _ledger, REAPPROVAL_PURPOSE','from .service_plan_approval import _ledger, REAPPROVAL_PURPOSE, REPLACEMENT_PURPOSE')
s=s.replace("or item['proposal']['binding']['purpose']!=REAPPROVAL_PURPOSE)", "or item['proposal']['binding']['purpose']!=(REPLACEMENT_PURPOSE if 'plan_replacement' in expected else REAPPROVAL_PURPOSE))")
s=s.replace("    if 'source_reapproval' in expected:", "    if 'source_reapproval' in expected or 'plan_replacement' in expected:")
p.write_text(s)
p=root/'service_plan_approval.py';s=p.read_text().replace("REAPPROVAL_PURPOSE = 'CASE_RESOURCE_REAPPROVAL'", "REAPPROVAL_PURPOSE = 'CASE_RESOURCE_REAPPROVAL'\nREPLACEMENT_PURPOSE = 'CASE_RESOURCE_PLAN_REPLACEMENT'")
s=s.replace('    return REAPPROVAL_PURPOSE if data.expected_link_revision is not None else PURPOSE', "    if data.expected_previous_plan_id is not None:return REPLACEMENT_PURPOSE\n    return REAPPROVAL_PURPOSE if data.expected_link_revision is not None else PURPOSE")
s=s.replace("                anchor=b['context'].get('source_reapproval')\n                if data.delivery.expected_link_revision is None:", """                anchor=b['context'].get('source_reapproval')
                if data.delivery.expected_previous_plan_id is not None:
                    from .plan_replacement_compatibility import validate_binding
                    if 'source_reapproval' in b['context']:raise ValueError()
                    validate_binding(b['context'].get('plan_replacement'),data.delivery,b['context'])
                elif data.delivery.expected_link_revision is None:""")
s=s.replace("if 'source_reapproval' in b['context']:raise ValueError()", "if 'source_reapproval' in b['context'] or 'plan_replacement' in b['context']:raise ValueError()",1) # replacement branch must only source; fix below
s=s.replace("if 'source_reapproval' in b['context'] or 'plan_replacement' in b['context']:raise ValueError()\n                    validate_binding", "if 'source_reapproval' in b['context']:raise ValueError()\n                    validate_binding")
s=s.replace("                else:\n                    anchor_keys=", "                else:\n                    if 'plan_replacement' in b['context']:raise ValueError()\n                    anchor_keys=",1)
s=s.replace('enabled_for_source_reapproval_tests=False):', 'enabled_for_source_reapproval_tests=False, enabled_for_plan_replacement_tests=False):',1)
s=s.replace('        self.source_reapproval_enabled=enabled_for_source_reapproval_tests is True', '        self.source_reapproval_enabled=enabled_for_source_reapproval_tests is True\n        self.plan_replacement_enabled=enabled_for_plan_replacement_tests is True')
s=s.replace('        if self.source_reapproval_enabled and not self.enabled:', '        if (self.source_reapproval_enabled or self.plan_replacement_enabled) and not self.enabled:')
p.write_text(s)
p=root/'case_resources.py';s=p.read_text().replace("getattr(approval,'source_reapproval_enabled',False) and str(parent['id'])", "(getattr(approval,'source_reapproval_enabled',False) or getattr(approval,'plan_replacement_enabled',False)) and str(parent['id'])")
s=s.replace("anchor=delivery_binding.get('context',{}).get('source_reapproval',{})", "context=delivery_binding.get('context',{})\n        anchor=context.get('plan_replacement',{}) if 'plan_replacement' in context else context.get('source_reapproval',{})")
p.write_text(s)
