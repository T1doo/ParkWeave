from pathlib import Path
import json,hashlib,os
root=Path.cwd();raw=root/'.runtime/ordinary-synthetic-scopes-20261018';frozen=raw/'frozen-b5f3a4a4';target=raw/'owned-root-artifacts'
target.mkdir(exist_ok=False)
paths=set()
for file in (frozen/'process-artifacts').rglob('*'):
    if not file.is_file():continue
    if file.name=='setup.stdout':
        for line in file.read_text().splitlines():
            if line.startswith('{'):
                row=json.loads(line)
                if 'setup_state_dir' in row:paths.add(row['setup_state_dir'])
    elif file.name=='setup-failure-proof.json':paths.add(json.loads(file.read_text())['state_dir'])
tokens=set();observations=[];runtime_maps=[]
inputs=json.loads((frozen/'shared-before.json').read_text())
for value in sorted(paths):
    state=Path(value);assert state.parent==Path('/tmp') and state.name.startswith('parkweave-ordinary-demo-')
    assert state.resolve()==state and state.stat().st_uid==os.geteuid()
    own=target/state.name;own.mkdir()
    for file in (state/'logs').rglob('*'):
        if file.is_file() and file.suffix in ('.json','.jsonl','.log','.txt','.stdout','.stderr'):
            dest=own/'logs'/file.relative_to(state/'logs');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(file.read_bytes())
    if (state/'failure.log').is_file():(own/'failure.log').write_bytes((state/'failure.log').read_bytes())
    if (state/'sessions.json').is_file():tokens.update(json.loads((state/'sessions.json').read_text()).values())
    observation=dict(state_dir=str(state),data_retained=(state/'data').exists(),state_retained=(state/'state.json').exists(),
        postmaster_marker=(state/'data/postmaster.pid').exists(),stop_unconfirmed=(state/'stop-unconfirmed').exists())
    if (state/'state.json').is_file():
        marker=json.loads((state/'state.json').read_text());marker.pop('sessions_sha256',None)
        (own/'state-observation.json').write_text(json.dumps(marker,indent=2)+'\n')
        files=marker['source']['files'];assert all(inputs.get(path)==value for path,value in files.items())
        runtime_maps.append(dict(state_dir=str(state),runtime_files=len(files),all_frozen_sha_equal=True,source_sha256=marker['source']['sha256']))
    observations.append(observation)
(raw/'private-owned-root-tokens.json').write_text(json.dumps(sorted(tokens))+'\n')
(raw/'owned-root-observations.json').write_text(json.dumps(dict(states=observations,runtime_bindings=runtime_maps,private_tokens=len(tokens),forensic_observations_not_readiness_claim=True),indent=2)+'\n')
assert not any(row['postmaster_marker'] or row['stop_unconfirmed'] for row in observations)
print(json.dumps(dict(owned_states=len(observations),state_bindings=len(runtime_maps),runtime_files_per_marker=[r['runtime_files'] for r in runtime_maps],private_tokens=len(tokens),owned_stop_markers=0)))
