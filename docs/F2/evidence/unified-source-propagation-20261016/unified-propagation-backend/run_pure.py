from pathlib import Path
import importlib.util,sys
import pytest
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('parkweave.unified_dependency_propagation',root/'unified_dependency_propagation.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
raise SystemExit(pytest.main([str(root/'test_unified_dependency_propagation.py'),'-q','--junitxml='+str(root/'junit.xml')]))
