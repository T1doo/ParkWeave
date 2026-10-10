from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OUT=Path(__file__).parent
SHA='d12afaa6258dd89a539e3a859b965ca9441e2111'
def artifact(p):
    data=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
def window(name):
    meta=json.loads((OUT/(name+'-execution.json')).read_text());xml=ET.parse(OUT/(name+'-junit.xml')).getroot();suites=list(xml.iter('testsuite'));nodes=list(xml.iter('testcase'))
    failed=sum(n.find('failure') is not None for n in nodes);errors=sum(n.find('error') is not None for n in nodes);skipped=sum(n.find('skipped') is not None for n in nodes)
    assert not(failed or errors or skipped) and meta['returncode']==0
    return dict(name=name,modules=meta['modules'],pytest_args=meta['pytest_args'],passed=len(nodes),failed=failed,errors=errors,skipped=skipped,observer_failures=0,natural_exit=True,returncode=meta['returncode'],junit_seconds=sum(float(s.attrib['time']) for s in suites),controlled_seconds=meta['end']-meta['start'],start_utc=datetime.fromtimestamp(meta['start'],timezone.utc).isoformat(),end_utc=datetime.fromtimestamp(meta['end'],timezone.utc).isoformat(),minimal_environment=meta['minimal_environment'],test_ids=[n.attrib.get('classname','')+'::'+n.attrib['name'] for n in nodes],artifacts=[artifact(OUT/(name+s)) for s in ('-execution.json','-junit.xml','-progress.json','-pytest.log')])
manifest=OUT/'frozen-source.json';basis=json.loads(manifest.read_text());drift=[p for p,h in basis.items() if not (ROOT/p).exists() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
after=dict(sha=(OUT/'head-final.txt').read_text().strip(),paths=len(basis),manifest_sha256=artifact(manifest)['sha256'],drift=drift)
(OUT/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
remote={ref:sha for sha,ref in (line.split() for line in (OUT/'remote-final.raw').read_text().splitlines())}
assert after['sha']==SHA and len(basis)==343 and not drift and after['manifest_sha256']=='1c8d0bb193e82ed236b4185e40ac7f9cba6185fb4166a3ddfa874cccc280ce46'
assert not (OUT/'git-status-final.txt').read_text().strip()
assert remote=={'refs/heads/candidate/registered-local-revision-20261010':SHA,'refs/heads/dev/f1-foundation':'ee646825b2bb9a00418b7a708e6b638187f61da2','refs/heads/main':'31e7acb7e53bb1ab6465b9daae59de28757f7583'}
windows=[window(n) for n in ('feature2','independent-prior5','compatible-selectors','independent-boundaries4','new-pid-writeoff1')]
evidence_names={'structural-revision.json','valid-impact-swap.json','saved-unknown-now-known.json','technical-version-evidence.json','overflow-action-boundaries.json','fresh-original-page.json','literal-resource.json','literal-run-access.json','actual-owned-pg-api-restart.json','schema-valid-writeoff.json'}
evidence=[dict(artifact=artifact(p),data=json.loads(p.read_text())) for p in sorted(OUT.rglob('*.json')) if p.name in evidence_names]
assert len(evidence)==10 and all(x['data']['exact_sha']==SHA for x in evidence)
previous=[]
for dirname,sha,h in [
 ('independent-registered-local-revision-review','ecf5d793311bd9d14853be2320c45f1c48fced69','1e56d10c7789c1dd23655a1433ee64d8a12656b5a4274f5688f7f1d11dbc25c4'),
 ('independent-registered-local-revision-version-compatibility-review','3cda6019fec72c842e039cd739bf84ab75b04079','13858c76d7a3662a26869d6953bd8d8a27b5bd192d4c22ecca83a04198a63bdf'),
 ('independent-registered-local-revision-accepted-final-review','5bc5a2b5be52f0ab7f99bd8319f055508695bc2e','79e848bcf2a913aadd747def351dcc61eac31c6c15f6661f3f23a12e94f63165')]:
    p=ROOT/'.runtime'/dirname/'report.json';a=artifact(p);assert a['sha256']==h;previous.append(dict(decision='BLOCKED',exact_sha=sha,report=a,unchanged=True))
report=dict(decision='LIMITED_PASS',exact_sha=SHA,generated_utc=datetime.now(timezone.utc).isoformat(),reviewer_scope='Independent read-only review of original F3-T03/AT25 bounded registered synthetic local Case-plan revision; exact final runtime tree only.',windows=windows,
    conclusions=dict(fresh_actual_257_to_known_all_case_projection='PASS: core/view/event affectedP1-P4; preserved[]; THIS_CASE; P1 pending VERIFY409 until explicit ADOPT201; original keyCOMMITTED',
      structural_local_journal='PASS: changed local-event revision normalGET/recovery/goal409 without observation row write',
      semantic_impact_proof='PASS: valid existing UUID partition swap with untouched original request/manifests is rejected409 by all three reads',
      old_declaration_version='PASS: private process-only VERSION1to2 preserves legitimate old localADOPT read/recovery200, THIS_CASE/all4; no source file edit',
      original_fresh_page='PASS: actual320 Chromium original page literal4affected/0preserved, committed lost initialADOPT oldhandle warm/coldGET-only; explicit original page localADOPT; other enterprise private view cleared',
      literal_resource_impact='PASS: P2-P5 affected/P1 preserved; affectedP3lock409, originalownerUNLOCK then ADOPT; P1lock and old proofs retained',
      literal_run_access_impact='PASS: P3-P5 affected/P1-P2 preserved; both original upstream locks retained',
      CAS_and_idempotency='PASS: independent distinct keys201/409; same key/body no new event; changed body409; GET recovery no business write',
      original_VERIFY_diagnostics='PASS: original11 partial-proof damage cases retain200 nonverified diagnostic; structural7 reject409; original5 actions recovery and manual-lock historical-read compatibility retained',
      actual_owned_PG_and_API_restart='PASS: exclusive own temporaryPG stop/start changes realPID/postmaster_start; databaseOID/systemID/data preserved; different configuredAPI PIDs/sameorigin; same opaque localADOPT key coldGET-only COMMITTED, stale original goal outputs UNVERIFIED, rows unchanged',
      new_PID_default_off='PASS: schema-valid APPROVE command through actual new configured API process returns403, no candidate column/business writes; existing unconsumed ledger not recreated in this narrow default-off test'),
    evidence=evidence,source=dict(before=json.loads((OUT/'source-before.json').read_text()),after=after,tracked_source_registry_tests_or_contract_writes=False),
    git=dict(clean_before_and_after=True,actual_remote=remote,dev_unmerged=True,main_unchanged=True,reviewer_git_writes=False),
    runtime_scope=dict(real_HTTP_PostgreSQL_Chromium=True,owned_UUID_fixture_databases=True,all_subprocesses_controlled_with_minimal_environment=True,all_collected_OUT_redirected_to_own_0700_ignored_directory=True,shared_root_database_processes_and_outputs_untouched=True,all_owned_windows_naturally_exited=True,active_owned_probes=0,model_calls=0),
    immutable_history_note='Future-version ordinary owner GET may persist the original planning invalidation flags. Its snapshot-wide unchanged=false fields are expected original observation behavior, not historical event or business rewrite. Assertions retain immutable events and step contracts. Recovery/goal/coldGET paths tested here have identical business-row snapshots and no replay.',
    prior_BLOCKED_reports_preserved=previous,
    limitations=['LIMITED_PASS applies only to exactd12 runtime bounded registered synthetic slice. The oldecf5/3cda/5bc5 actual FAIL windows remain BLOCKED historical evidence and are not cancelled or reused as current passes.',
      '45 complete feature tests,24 selected compatibility tests,5 previous-blocker/action oracles,4 independent boundary tests and1 newPID negative are five separate natural windows, not one79-test run. No root counts are borrowed.',
      'The final one-line view correction did not rerun complete12/13/27 related modules; old5bc5 381/440 and3cda907 are historical only. Full two touched feature modules plus targeted original readers/diagnostics and own literal probes are current evidence.',
      'VERSION change is a private process-only technical future-compatibility oracle, not a production version migration. Real PGrestart and configured API PID restart are separately identified; no fixture capability is reissued or nonce forged.',
      'Fixture-only optional resources/memberships copy the original synthetic grant template inside owned disposable databases. No product permission, Grant, policy approval, automaticADOPT/VERIFY, resource release/pause, Casecompletion, Release, model, credential or network change.',
      'No fullrepository/fullAT25/general dynamicDAG/real business/productiondeployment/Windows acceptance; remaining original V1 broader graph kinds and formal lifetime behavior are outside this bounded slice.',
      'Full Approval lifecycle, existing unconsumed Approval ledger restoration and production activation were not rerun by the newPID default-off probe; it verifies schema-valid403 and no installation/write only.'],
    supporting_artifacts=[artifact(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='report.json'])
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(decision=report['decision'],exact_sha=SHA,report=artifact(OUT/'report.json'),windows=[{k:w[k] for k in ('name','passed','failed','errors','skipped','returncode','junit_seconds','controlled_seconds')} for w in windows],source_paths=len(basis),drift=len(drift))))
