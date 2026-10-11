"""Load only read-only exported frozen modules for historical defect proof."""
import importlib.util
import sys
import parkweave
for leaf in ('api','history_summary'):
    name = 'parkweave.' + leaf
    spec = importlib.util.spec_from_file_location(name, '/tmp/parkweave-independent-review/old_source/' + leaf + '.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    setattr(parkweave,leaf,module)
