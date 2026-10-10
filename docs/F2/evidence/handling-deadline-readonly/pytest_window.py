from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()/'tests'))
import test_material_objections_browser as old
old.OUT=Path('.runtime/handling-deadline/original-material-objections-browser')
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
