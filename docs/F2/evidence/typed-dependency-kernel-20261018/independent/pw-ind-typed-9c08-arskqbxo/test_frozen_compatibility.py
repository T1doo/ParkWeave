from copy import deepcopy
from parkweave import dependency_graph as graph

def test_original_schema2_conversion_is_independent_of_current_scope_or_compiler(monkeypatch):
    from test_unified_dependency_propagation_literal import scenario
    from parkweave import unified_dependency_propagation as original
    args=scenario('UP13');frozen=original.build_v1(*args);saved=deepcopy(frozen)
    monkeypatch.setattr(original,'SCOPE','FUTURE_CURRENT_COMPILER')
    def forbidden(*a,**k):
        raise AssertionError('frozen conversion must not recompile old graph')
    monkeypatch.setattr(original,'build_v1',forbidden)
    converted=graph.from_unified_v1(frozen)
    assert converted['legacy_sha256']==saved['sha256']
    assert frozen==saved
