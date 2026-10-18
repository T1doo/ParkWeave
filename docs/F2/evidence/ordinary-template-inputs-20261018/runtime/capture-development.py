from pathlib import Path
from hashlib import sha256
import json,shutil,sqlite3
root=Path.cwd();out=root/'.runtime/ordinary-template-inputs-20261018/development-artifacts';out.mkdir(exist_ok=False)
inputs=[root/'.runtime/ordinary-template-inputs-20261018/development-pytest']+[Path('/tmp/pw-template-input-dev'+str(i)) for i in range(2,6)]
for index,base in enumerate(inputs,1):
    if not base.exists():continue
    for folder in sorted(base.glob('test_*')):
        if not folder.is_dir() or folder.is_symlink():continue
        for path in sorted(folder.rglob('*')):
            if not path.is_file() or path.is_symlink():continue
            rel=Path('window-'+str(index))/folder.name/path.relative_to(folder)
            if path.suffix in ('.json','.jsonl','.stdout','.stderr','.log','.txt'):
                target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
            elif path.name.endswith('.consumer.candidate.sqlite3'):
                with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
                    c.row_factory=sqlite3.Row
                    summary=dict(journal_sha256=sha256(path.read_bytes()).hexdigest(),read_only=True,
                        instances=[dict(instance_id=r['id'],input_sha256=sha256(r['input'].encode()).hexdigest(),binding_sha256=sha256(r['binding'].encode()).hexdigest(),state=r['state']) for r in c.execute('SELECT * FROM consumer_instances')],
                        stages=[dict(r) for r in c.execute('SELECT instance_id,name,request_key,body_sha256,state,result,error FROM consumer_stages')])
                target=out/rel.with_suffix('.summary.json');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(summary,indent=2)+'\n')
(out/'capture.json').write_text(json.dumps(dict(source_roots=[str(p) for p in inputs],private_input_or_cluster_data_copied=False,original_failures_preserved=True),indent=2)+'\n')
