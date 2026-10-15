"""Render delivery prose only from closed final execution evidence."""
from pathlib import Path
import json, hashlib, re

root = Path.cwd()
runtime = root / '.runtime/multifield-source-root'
base = root / '.runtime/multifield-source-final'
freeze = json.loads((runtime / 'freeze.json').read_text())
reg = json.loads((runtime / 'final-regression-verification.json').read_text())
ind = json.loads((base / 'independent-new-v2-analysis/validation.json').read_text())
ind_success = json.loads((base / 'independent-new-v2-analysis/success.json').read_text())
assert ind_success['status'] == 'PASS' and ind_success['source_sha'] == freeze['source_sha']
for name, key in [('validate_window.py', 'validator_sha256'), ('mapping-input.json', 'mapping_input_sha256'), ('validation.json', 'validation_sha256')]:
    assert hashlib.sha256((base / 'independent-new-v2-analysis' / name).read_bytes()).hexdigest() == ind_success[key]
ci = json.loads((base / 'ci-metadata-v2.json').read_text())
review = json.loads((root / '.runtime/multifield-source-review/formal-30e8a60-v2/validation.json').read_text())
index = json.loads((root / 'docs/F2/evidence/multifield-source-conflict-20261015/index.json').read_text())
assert reg['status'] == review['status'] == 'PASS'
assert all(x['source_sha'] == freeze['source_sha'] for x in [reg, ind, ci, review, index])
assert ind['counts'] == {'PASS': 52, 'FAIL': 0, 'ERROR': 0, 'SKIP': 0}
assert ci['exit_code'] == 0 and ci['collection_junit_exact_match'] and ci['unique_junit_nodes']
assert not ci['source_drift'] and not ci['all_tracked_drift'] and not ci['runner_drift']
assert len(ci['modules']) == 12 and all(ci['counts'][k] == 0 for k in ['FAIL', 'ERROR'])
assert ci['counts']['PASS'] == 433 and ci['counts']['SKIP'] == 14
table = ['| 有效窗口 | 完整模块 | PASS |', '| --- | ---: | ---: |']
for w in reg['windows']:
    table.append(f"| {w['name']} | {len(w['selected_modules'])} | {w['selected_PASS']} |")
regtext = f"同一冻结 SHA 的 **{reg['complete_modules']} 个相关完整模块、{reg['unique_testcases']} 个去重有效项全部 PASS，0 FAIL/ERROR/SKIP**，不是全仓运行。\n\n" + '\n'.join(table)
regtext += f"\n\n完整 collection/JUnit 身份唯一精确，选择按完整模块且互不重叠；617 源码路径、15418 tracked 和4个运行器辅助文件前后零漂移。此前3101份原始证据和79份原独审证据保持。[主并集核验](evidence/multifield-source-conflict-20261015/multifield-source-root/final-regression-verification.json)。\n\n另同 SHA 的12个完整 CI 诊断消费者模块 **{ci['counts']['PASS']}PASS、{ci['counts']['SKIP']}SKIP、0FAIL/ERROR**，447个完整唯一身份，单列于主97之外；14项依赖原PowerShell/原生Windows前提，保持NOT_RUN，不算已执行。补充含公开摘要、最长25个ID、分片、清理和原字节预算。主并集已有的 ci_diagnostics60项不重复计入此补充。"
known = ind['literal_precision']['known']
unknown = ind['literal_precision']['intentional_UNKNOWN']
mapping = ind['design40_scope_counts']
newhtml = ind['new_HTML']
priorhtml = ind['prior_HTML']
indtext = f"新独测24项、原carry28项在同一完整52项窗口全部通过。新4条完整HTML实际{sum(x['calls'] for x in newhtml)}次HTTP（" + '/'.join(str(x['calls']) for x in newhtml) + f"）；原carry2条实际{sum(x['calls'] for x in priorhtml)}次HTTP，分列不合并为新样本。新闭环观察{ind['new_closure_observations']}项，要求当前六目标本地输出及完整分页工作清单，{ind['new_closures_B_original_plan_byte_exact']}项另逐字保持未影响Case的原计划。回执路径的P1/P2/P3及容量并集两Case的P1共5个完整锁步骤对象逐字保持。丢ACK后新VM仅用原key冷GET，当前403与迟到403/身份ABA分别测试。"
indtext += f"\n\nknown 字面矩阵{known['rows']}行：应影响{known['expected_affected']}、应保留{known['expected_preserved']}，漏更/误更/误保留均0；另{unknown['rows']}行有意UNKNOWN按全5步/Case保守拒绝，不计入known精度。来源/行UNKNOWN DTO与无MANUAL不适用分别列示。40项设计映射为{mapping['PASS']}限定scope PASS/{mapping['VARIANT']}变体/{mapping['NOT_RUN']}NOT_RUN，不宣称40全完成；Python API总调用数未由冻结采集器记录，不迁开发期计数。[新冻独测核验](evidence/multifield-source-conflict-20261015/multifield-source-final/independent-new-v2-analysis/validation.json)。"
raw_bytes = sum(e['raw_bytes'] for e in index['entries'])
export_bytes = sum(e['export_bytes'] for e in index['entries'])
archive = f"主档{len(index['entries'])}个raw/export配对，原件{raw_bytes}字节、导出{export_bytes}字节，逐项hash/大小及允许去敏转换核对。历史原件包含开发和首冻结，不以最终source_sha冒签旧执行。\n\n[主档索引](evidence/multifield-source-conflict-20261015/index.json)、[归档说明](evidence/multifield-source-conflict-20261015/README.md)、[根checkpoint](evidence/multifield-source-conflict-20261015/audit.json)、[独立终门](evidence/multifield-source-conflict-audit-20261015/final-gate.json)。"
retries = [w for w in reg['windows'] if w['reason']]
retry_text = '最终选择的整模块替代及原因：' + '；'.join(w['name'] + '：' + w['reason'] for w in retries) if retries else '最终冻结的主选择各窗均以完整窗口通过，无失败模块替代。'
text = (runtime / 'delivery-report-template.md').read_text()
for key, value in {'REGRESSION': regtext, 'INDEPENDENT': indtext, 'ARCHIVE': archive, 'FINAL_RETRY': retry_text}.items():
    text = text.replace('{{' + key + '}}', value)
assert not re.search(r'\{\{[A-Z_]+\}\}', text)
target = root / 'docs/F2/MultifieldSourceConflict-20261015.md'
target.write_text(text)
print(json.dumps({'report': str(target.relative_to(root)), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'source_sha': freeze['source_sha']}))
