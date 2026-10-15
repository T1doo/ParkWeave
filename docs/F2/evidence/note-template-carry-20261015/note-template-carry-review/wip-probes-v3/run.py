import sys,os,json,hashlib,time
from pathlib import Path
root=Path('/workspace/ParkWeave');here=Path(__file__).resolve().parent;snapshot=here.parent/'source-wip-v1/src'
sys.path.insert(0,str(snapshot));sys.path.insert(1,str(root/'tests'));sys.path.insert(2,str(here))
import parkweave
assert Path(parkweave.__file__).is_relative_to(snapshot),parkweave.__file__
import parkweave.note_template_carry as carry
(here/'import-provenance.json').write_text(json.dumps({'product_package':parkweave.__file__,'carry_module':carry.__file__,'carry_sha256':hashlib.sha256(Path(carry.__file__).read_bytes()).hexdigest(),'WIP_not_frozen':True},indent=2)+'\n')
os.environ.update(LEGACY_ARTIFACT_DESTINATION=str(here/'artifact-destination'),TYPED_COLLECTION=str(here/'collection.json'),TYPED_PRIVATE=str(here/'redaction.private.json'),AT_BATCH_ARTIFACT_ROOT=str(here/'artifacts'),AT_BATCH_WINDOW='wip-v3',XDG_CACHE_HOME=str(root/'.runtime/xdg-cache'))
import pytest
start=time.monotonic();code=pytest.main([str(here/'test_carry_review.py')+'::test_real_v2_material_continue_first_carry_then_edit_reconfirm_next_hop','-p','carry_review_capture','-p','legacy_artifact_capture','-o','pythonpath='+str(snapshot),'--basetemp=/tmp/note-carry-review-wip-pg-v3','-o','cache_dir=/tmp/note-carry-review-wip-cache-v3','--junitxml='+str(here/'results.xml'),'-vv'])
(here/'runner-result.json').write_text(json.dumps({'exit_code':int(code),'elapsed_seconds':time.monotonic()-start,'WIP_not_frozen':True},indent=2)+'\n');raise SystemExit(code)
