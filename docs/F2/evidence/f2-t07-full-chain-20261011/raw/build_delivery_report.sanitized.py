"""Derive finite T07 reports only from the completed frozen actual window."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT/'.runtime/f2-t07-full-chain'
SOURCE = 'b5ea90ac9b366b015b43c426ad94b72faf7c8b72'
identity = lambda c: c.attrib.get('classname', '')+'::'+c.attrib['name']
state = lambda c: 'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'


def write_json(path, value):
    assert not path.exists(), ('immutable new report already exists', str(path))
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n')


def main():
    full = json.loads((PRIVATE/'full-complete-final-run.json').read_text())
    assert full['source_sha'] == SOURCE and full['exit_code'] == 0
    assert not full['source_drift'] and not full['prior_test_ids_missing']
    core = json.loads((PRIVATE/'goal-results-pg-complete-run.json').read_text())
    assert core['source_sha'] == SOURCE and core['exit_code'] == 0 and not core['source_drift']
    assert core['complete_module_count'] == 1 and core['FAIL'] == core['ERROR'] == core['SKIP'] == 0
    full_cases = ET.parse(PRIVATE/'full-complete-final.xml').getroot().findall('.//testcase')
    core_cases = ET.parse(PRIVATE/'goal-results-pg-complete.xml').getroot().findall('.//testcase')
    assert not {identity(c) for c in full_cases} & {identity(c) for c in core_cases}
    cases = full_cases+core_cases
    ids = {identity(c):state(c) for c in cases}; assert len(ids) == len(cases)
    assert full['PASS']+full['SKIP']+core['PASS'] == len(ids) and full['FAIL'] == full['ERROR'] == 0
    scenarios = []
    for trace in sorted((PRIVATE/'windows/full-complete-final').glob('*.json')):
        data = json.loads(trace.read_text())
        test_id = data['test_id'].replace('tests/', 'tests.').replace('.py::', '::')
        assert ids[test_id] == 'PASS'
        assert data['owned_postgres']['app_role'] == 'parkweave_app'
        assert all(n == 0 for n in data['initial_business_counts'].values())
        assert data['browser_attempts'] == 0 and data['formal_AT35'] is False
        assert all(w['exit_code'] == 0 and not w['timed_out'] and not w['mock'] for w in data['independent_worker_processes'])
        assert all(not p['termination_timeout'] and p['exit_code'] in (0,-15) and p['health']['process_id'] == p['pid'] for p in data['cold_api_processes'])
        scenarios.append(dict(test_id=test_id, actual_status=ids[test_id],
            trace_path=str(trace.relative_to(ROOT)), trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
            request_count=len(data['requests']), worker_count=len(data['independent_worker_processes']),
            cold_api_count=len(data['cold_api_processes']), persisted_chain_proof_count=len(data['persisted_chain_proofs']),
            assignment_precondition_count=len(data['fixture_assignment_preconditions']),
            setup_actor='OWNED_SYNTHETIC_FIXTURE_DATABASE_OWNER' if data['fixture_assignment_preconditions'] else None,
            roles=sorted({r['actor'] for r in data['requests']}), initial_business_counts=data['initial_business_counts'],
            final_business_counts=data['final_business_counts'], formal_AT35=False))
    assert len(scenarios) == 10
    new = {k:v for k,v in ids.items() if k.startswith('tests.test_f2_t07_full_chain::')}
    assert set(new) == {r['test_id'] for r in scenarios}
    write_json(PRIVATE/'final-scenario-map.json', dict(source_sha=SOURCE,
        source_manifest_sha256=full['source_manifest_sha256'], mode='SYNTHETIC_ORDINARY_HTTP_OWNED_PG_LOCAL_CLI_MANUAL_RECEIPT',
        formal_F2='NOT_RUN', formal_AT35='BLOCKED', production_source_changes=0,
        manual_human_confirmation='EXPLICIT_SYNTHETIC_TEST_DRIVER_NOT_NATURAL_PERSON_PILOT',
        browser_attempts=0, model_calls=0, paid_calls=0, scenarios=scenarios))
    selectors = {
        'identity_scope_and_current_permissions': [
            'tests.test_executor_receipts::test_current_revocation_before_replay_and_owner_decision',
            'tests.test_service_dispatches::test_accept_rechecks_live_authority_and_parent_without_side_effects',
            'tests.test_service_case_steps::test_current_owner_revocation_precedes_lost_reply_replay',
            'tests.test_case_resources::test_current_revocation_precedes_old_key_replay'],
        'versions_provenance_and_original_key': [
            'tests.test_executor_receipts::test_stale_version_hash_and_invalid_state_have_no_effect',
            'tests.test_service_case_steps::test_lost_reply_replay_key_mismatch_stale_cas_and_source',
            'tests.test_service_case_steps::test_concurrent_verify_commits_one_event_or_one_replayed_event',
            'tests.test_case_resources::test_same_key_concurrency_and_cross_case_fingerprint'],
        'real_pg_capacity_and_expiry': [
            'tests.test_resource_holds::test_overcapacity_and_concurrent_distinct_keys_never_overbook',
            'tests.test_resource_holds::test_expiration_without_cleaner_replay_does_not_extend_and_expired_release',
            'tests.test_resource_holds::test_clock_is_sampled_after_resource_lock_wait_not_transaction_start',
            'tests.test_resource_combinations::test_second_lock_wait_expiry_and_stable_order'],
        'cancel_accept_and_other_write_lock_waits': [
            'tests.test_case_cancellation::test_cancel_first_real_pg_wait_blocks_all_competitors',
            'tests.test_case_cancellation::test_accept_first_cancel_waits_then_rejects',
            'tests.test_case_cancellation::test_writer_first_real_pg_wait_cancel_rechecks_committed_sources'],
        'transaction_rollback': [
            'tests.test_case_cancellation::test_event_failure_rolls_back_every_change',
            'tests.test_executor_receipts::test_event_failure_rolls_back_receipt_and_state',
            'tests.test_service_case_steps::test_coordination_update_failure_rolls_back_plan_and_event'],
        'late_ui_and_historical_notice': ['tests.test_case_cancellation_offline::',
            'tests.test_case_cancellation::test_old_notice_consumption_and_open_recheck_cancelled_case'],
    }
    groups = {}
    for group, prefixes in selectors.items():
        selected = {id:result for id,result in ids.items() if any(id == p or id.startswith(p+'[') or p.endswith('::') and id.startswith(p) for p in prefixes)}
        assert selected and all(v == 'PASS' for v in selected.values()), group
        for prefix in prefixes:
            assert any(id == prefix or id.startswith(prefix+'[') or prefix.endswith('::') and id.startswith(prefix) for id in selected), prefix
        groups[group] = dict(actual_status='PASS', exact_test_ids=selected,
                            window='full-complete-final', historical_counts_reused=False)
    original = json.loads((PRIVATE/'independent-review/initial-full-chain-review.json').read_text())['at_mapping']
    assert len(original) == 35 and len({r['id'] for r in original}) == 35
    write_json(PRIVATE/'original-at-finite-map.json', dict(source_sha=SOURCE,
        whole_original_ATs='NOT_RUN', AT35_production_new_Run_assignment='BLOCKED',
        original_scenario_steps_oracles_retained=original, finite_current_window_groups=groups,
        case_goal_results_complete_current_module=dict(window='goal-results-pg-complete',
            exact_test_ids={identity(c):state(c) for c in core_cases}, source_sha=SOURCE),
        not_formal_phase_admission=True, no_browser_or_model_in_this_window=True))
    counts = Counter(state(c) for c in cases)
    suites = ET.parse(PRIVATE/'full-complete-final.xml').getroot().findall('.//testsuite')
    timing = dict(full_39_process_seconds=full['elapsed_seconds'],
                  full_39_junit_suite_seconds=sum(float(s.attrib['time']) for s in suites),
                  supplemental_goal_results_process_seconds=core['elapsed_seconds'])
    report = f'''# 原 F2-T07 有限整链工程验收

本轮实际完成同一新合成 Case 的新诉求、补件/核对、注册五目标规划、两个资源的组合占用与关联、本人接单、人工本地回执、企业明确 ACK/P1–P5 VERIFY、拒单重派、回执补正/反馈及本地关闭重开。普通生产 API 与独立 CLI worker 实际写入自有 PostgreSQL；新普通 API 子进程实际冷读。人工动作由合成测试驱动，不称自然人试点、真实模型办理或线下履约。

冻结验收源码 `{SOURCE}`；406 文件清单 SHA `{full['source_manifest_sha256']}`。原405源码零变，本轮新增整链测试与实施前合同，无生产功能补丁。根39模块完整窗口实际 {full['PASS']} PASS / {full['FAIL']} FAIL / {full['ERROR']} ERROR / {full['SKIP']} SKIP，exit{full['exit_code']}、{full['elapsed_seconds']}秒、JUnit {timing['full_39_junit_suite_seconds']:.3f}秒；另一个同SHA目标产物完整PG专项窗口 {core['PASS']} PASS / 0 FAIL / 0 ERROR / 0 SKIP，exit0、{core['elapsed_seconds']}秒。两窗口ID不重叠，共40模块、{len(ids)} unique IDs，{counts.get('PASS',0)} PASS与{counts.get('SKIP',0)} SKIP；不称一个40模块单进程窗口。原1561 IDs无缺失，新整链10 IDs另列。唯一旧SKIP是Windows原生文件后端门，本轮Linux不转签Windows。

A场景从零Run/Case、正常新Run走到资料/计划/资源，实际默认访问批准关闭、新Run无执行者assignment，分派403且业务/权限不变；目标不完成。B场景以原fixture owner-only assign_status作为**业务链之外明确合成管理前提**，仅新增指定Run/executor/scope assignment，之后全链只用原API/worker。它不是零授权setup的正式首用：当前普通新Run合法生产批准/分派授权合同缺失仍为BLOCKED，禁止用新Grant/registry/隔离桥掩盖。两次成功新输入为同一fixture-a企业；跨企业/园区/错误角色是拒绝矩阵。

每个五目标产物与PG精确同链：材料UUID/version/text SHA及REVIEW/CONFIRM事件，资源link/combination/member与实际容量，dispatch/offer/ACCEPT actor与receipt step，当前人工receipt UUID/version/text SHA/SUBMIT+ACK事件，当前cycle REVALIDATE snapshot SHA，以及嵌入计划的明确VERIFY来源SHA/事件。缺receipt/ACK、错误hash/陈旧资料版本、跨Case原key拒绝无半写；只GET原key核对丢响应，不自动重发。取消后的旧通知GET/OPEN/MARK_READ重核状态、迟到ACCEPT409，原offer保持OFFERED，组合仍占容量直到独立释放。关闭会使P5失效，需再次明确VERIFY；Case从未写FULFILLED。

独审新模块与额外反例的结果单列在[最终独立报告](evidence/f2-t07-full-chain-20261011/README.md)，不累加为根完整回归数量。原失败窗口及中断窗口全部保留，失败同testID最终对应表、每步HTTP/PG/worker/coldAPI证据与完整原AT01–35映射见[证据索引](evidence/f2-t07-full-chain-20261011/README.md)。导出件明确标脱敏/压缩，清单同时记录原件和导出件hash；失败未改为PASS。

补跑曾误选真实Chromium专项模块，pytest因缺playwright在收集阶段退出2、0PASS/0FAIL/1ERROR/0SKIP，未执行测试或启动浏览器；原argv/log/XML保留。该浏览器模块未重试、未安装依赖、仍NOT_RUN，不声称错误sameID已修。之后只跑独立允许的PG专项。此前39模块首窗因冷API主动SIGTERM退出码oracle需修正而由owned SIGINT停止，17PASS/0FAIL/0ERROR/0SKIP、exit1并附pytest teardown KeyError，均原样保留，不计完整回归通过。

正式F2/AT35/PR0-alpha、真实模型/正式服务发布、三工作台真实浏览器验收、真实园区/线下效果和干净Windows仍NOT_RUN。历史Chromium data:导航ERR_BLOCKED_BY_ADMINISTRATOR保持，浏览器启动与替代重试0；真实模型/付费调用0，无生产部署/迁移、新Grant/信任登记、凭据或网络配置、权限扩大、强推或保护分支写入。历史Case_count0仍UNCONFIRMED，本次CLI worker真实成功建新Case不消除该历史未知原因。

下一步需要在原产品范围明确普通新Run的合法批准/分派授权生产合同，并另验正式模型/发布与工作台；本片不扩大这些前提。源码之后的交付commit只归档文档证据，最终完整SHA与实际正常push/远端/干净工作区记录另核。
'''
    target = ROOT/'docs/F2/T07FullChain.md'; assert not target.exists(); target.write_text(report)
    write_json(PRIVATE/'report-generation.json', dict(utc=datetime.now(timezone.utc).isoformat(),
        source_sha=SOURCE, counts=dict(counts), timing=timing, scenario_count=len(scenarios),
        finite_regression_group_count=len(groups), generated_doc=str(target.relative_to(ROOT))))


if __name__ == '__main__': main()
