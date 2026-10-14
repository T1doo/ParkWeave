import hashlib,json,pathlib,subprocess,sys,time
root=pathlib.Path.cwd();out=root/'.runtime/at-replay-20261014/cold-final-v3';out.mkdir(parents=True,exist_ok=True)
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','src','tests','scripts','pyproject.toml'],text=True).splitlines()
paths=sorted(set(p for p in paths if (root/p).is_file()))
def manifest():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=manifest();(out/'frozen-before.json').write_text(json.dumps(before,indent=2)+'\n')
command=[sys.executable,'-m','pytest','tests/test_service_cold_entry_nodevm_actual.py','-q','--junitxml='+str(out/'frozen.xml')]
start=time.monotonic()
with (out/'frozen.log').open('w') as f: result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
after=manifest();(out/'frozen-after.json').write_text(json.dumps(after,indent=2)+'\n');(out/'frozen.exit').write_text(str(result.returncode)+'\n')
changed=[p for p in before if before[p]!=after[p]]
summary=dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),command=command,tracked_plus_new_files=len(paths),source_files_changed=changed,exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),new_test_sha256=after['tests/test_service_cold_entry_nodevm_actual.py'])
(out/'frozen-window.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));print((out/'frozen.log').read_text());raise SystemExit(result.returncode)
