from pathlib import Path
import os,sys,subprocess,json,hashlib,time
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/note-template-carry-backend';WORK=OUT/'private-worktree'
name=sys.argv[1];mods=sys.argv[2:]
env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(OUT),str(WORK/'src'),str(WORK/'tests')]),XDG_CACHE_HOME=str(OUT/'xdg-cache'),TYPED_COLLECTION=str(OUT/(name+'-collection.json')),TYPED_PRIVATE=str(OUT/('redaction-'+name+'.private.json')),AT_BATCH_ARTIFACT_ROOT=str(OUT/'artifacts'),AT_BATCH_WINDOW=name)
args=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q','-p','shared_capture','-o','pythonpath='+str(WORK/'src'),'-o','cache_dir='+str(OUT/'pytest-cache'),*mods,'--basetemp=/tmp/parkweave-note-template-carry-'+name,'--junitxml='+str(OUT/(name+'.xml'))]
paths=['src/parkweave/note_template_carry.py','src/parkweave/template_migration.py','src/parkweave/template_upgrade.py','tests/test_note_template_carry.py','tests/test_note_template_carry_epoch_types.py','tests/test_note_template_carry_material_anchor.py']
before={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in paths};start=time.monotonic()
with (OUT/(name+'.log')).open('w') as stream:code=subprocess.run(args,cwd=WORK,env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
after={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in paths}
result=dict(exit_code=code,elapsed_seconds=time.monotonic()-start,argv=args,private_hashes_before=before,private_hashes_after=after,private_drift=before!=after)
(OUT/(name+'-result.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));sys.exit(code)
