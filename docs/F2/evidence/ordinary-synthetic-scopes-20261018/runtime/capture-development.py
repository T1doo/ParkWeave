from pathlib import Path
import json,shutil,re,hashlib
raw=Path('.runtime/ordinary-synthetic-scopes-20261018');development=raw/'development';paths=[];tokens=set();seen=set()
for folder in Path('/tmp/pytest-of-agent').glob('pytest-*/test_*'):
    if not folder.is_dir() or folder.is_symlink() or folder.parent.is_symlink() or not (folder.name.startswith('test_second_enterprise_first_c') or folder.name.startswith('test_scope_binding_missing_or_c')):continue
    p=folder/'setup.stdout'
    if not p.is_file() or p.stat().st_mtime<(development/'input-before.json').stat().st_mtime:continue
    for line in p.read_text().splitlines():
        if not line.startswith('{'):continue
        row=json.loads(line);value=row.get('setup_state_dir')
        if not value or value in seen:continue
        seen.add(value);state=Path(value);assert state.parent==Path('/tmp') and state.name.startswith('parkweave-ordinary-demo-')
        paths.append(dict(test_dir=str(folder),state_dir=str(state),postmaster_exists=(state/'data/postmaster.pid').exists(),stop_unconfirmed=(state/'stop-unconfirmed').exists()))
        if (state/'sessions.json').is_file():tokens.update(json.loads((state/'sessions.json').read_text()).values())
        target=development/'owned-states'/state.name;target.mkdir(parents=True,exist_ok=True)
        def save(dest,data):
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==data
            else:dest.write_bytes(data)
        for log in (state/'logs').rglob('*'):
            if log.is_file():save(target/'logs'/log.relative_to(state/'logs'),log.read_bytes())
        for name in ('failure.log',):
            if (state/name).is_file():save(target/name,(state/name).read_bytes())
        marker=json.loads((state/'state.json').read_text());marker.pop('sessions_sha256',None)
        save(target/'state-observation.json',(json.dumps(marker,indent=2)+'\n').encode())
        for file in folder.rglob('*'):
            if file.is_file() and file.suffix in ('.log','.json','.stdout','.stderr','.txt'):
                save(development/'test-artifacts'/folder.name/file.relative_to(folder),file.read_bytes())
(raw/'private-development-tokens.json').write_text(json.dumps(sorted(tokens))+'\n')
(development/'owned-states.json').write_text(json.dumps(paths,indent=2)+'\n')
(development/'capture-attempt1-failure.json').write_text(json.dumps(dict(exit_code=1,reason='pytest-current parent symlink caused duplicate state path; FileExistsError at exclusive evidence directory creation',completed='first owned state logs and observations copied',correction='skip symlink parents and deduplicate exact observed state paths; verify existing evidence bytes before adding missing copies',deleted=False,product_changed=False),indent=2)+'\n')
print(json.dumps({'owned_states':paths,'registered_private_tokens':len(tokens)},ensure_ascii=False))
for p in (development/'owned-states').rglob('*.log'):
    lines=[s for s in p.read_text(errors='replace').splitlines() if re.search('ERROR|Traceback|deadlock|timed out|Exception|terminating',s,re.I)]
    if lines:print(json.dumps({'log':str(p),'matched_lines':lines[-15:]},ensure_ascii=False))
