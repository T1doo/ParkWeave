import json,sys
from pathlib import Path
ROOT=Path('/workspace/parkweave-at-review-20261014')
def pytest_sessionfinish(session,exitstatus):
    loaded={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.items() if name.startswith('parkweave') and getattr(module,'__file__',None)}
    invalid={name:path for name,path in loaded.items() if not Path(path).is_relative_to(ROOT/'src')}
    (ROOT/'.runtime/at-independent/final-loaded.json').write_text(json.dumps(dict(loaded=loaded,invalid=invalid),indent=2))
    if invalid:session.exitstatus=1
