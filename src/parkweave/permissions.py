"""Trusted role bounds, independent of client claims and catalogue declarations."""
ROLE_CAPABILITIES = {
    'enterprise_operator': frozenset({'READ','CONTROL','EXECUTE','FILE_READ'}),
    'park_specialist': frozenset({'READ'}),
    'resource_admin': frozenset({'READ'}),
    'service_executor': frozenset({'READ'}),
}
TRUSTED_ACTIONS = frozenset({'case.create','facts.assess','fault.record'})
