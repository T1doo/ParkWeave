from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/ordinary-reuse-user-flow-20261018';dest=root/'docs/F2/evidence/ordinary-reuse-user-flow-20261018'
a=json.loads((r/'accepted-tests.json').read_text());freeze=json.loads((r/'frozen-freeze.json').read_text());ind=json.loads((r/'independent-final-review.json').read_text());reference=json.loads((r/'independent-report-reference.json').read_text());archive=json.loads((dest/'archive-validation.json').read_text());inherited=json.loads((r/'inherited-evidence-proof.json').read_text())
assert a['passed']==43 and a['failures']==a['errors']==a['skipped']==0 and ind['source_sha']==a['source_sha']
text=f'''# 两件新事项材料复用普通页面验收

冻结提交 `{a['source_sha']}`，src tree `{a['source_tree']}`，tests tree `{a['tests_tree']}`；基线 `6f8167a3e435b6fc198e757f8968c6c56ac27411`，分支 `dev/f2-material-reuse-dom-20261018`。[冻结合同](MaterialReuseDOM-20261018.md) SHA256 `{freeze['contracts']['docs/F2/MaterialReuseDOM-20261018.md']}`。完整项目仍 IN_PROGRESS，正式验收规格状态未改。

## 实际用户流程及修复

原 §5.1 同企业同用途复用、F2-T01／再次使用场景中，现有 ENG100 浏览器证据先由 API 创建两件事项。本片从零业务初态通过普通页面创建两件独立 Run／Case／preparation，不用 API 业务初态或 JS 业务操作。来源新诉求、两材料、专员核对和企业确认后，目标经原控件预览来源版本／SHA、勾选用途和明确复制；目标仅得到新 ID／v1／UNVERIFIED 材料目录，本次摘要、request intent、REVIEW 与 CONFIRM 独立提交。

真实红窗发现：目标仅有复用目录且无本次摘要／核对时，企业确认按钮仍启用，后端会按原规则拒绝。`web.html` 的唯一生产改动在原 pending／UNKNOWN 禁用条件上加当前 enterprise_operator／REVIEWED 门。实际 DOM 验证审核前禁用、REVIEWED 后启用、CONFIRM 后禁用、REOPEN 后禁用。原后端权限／CAS／当前审核 hash、未知结果恢复、必需读取与异议门保留；无新算法、provider、审批、身份或目录发布能力。

1200／320 两完整节点均核 source preview 与原 preparation／Case／Run／revision／review snapshot、材料 ID／版本／SHA 绑定，唯一复用事件完整 provenance 等于原来源及新 target ID／v1／SHA／明确用途／INDEPENDENT_COPY。两 parent 的 request intent 与 required goals 独立；按原 canonical 字段合同独立重算目标两槽审核 SHA，REVIEW／CONFIRM actor 和事件 SHA 一致。

来源再经原 REOPEN／ADD／REVIEW／CONFIRM 更新目录 v2；目标完整 Case 历史及 v1 副本和包字节不变，显示 HISTORICAL_SOURCE_CHANGED。两个普通启动中的新角色上下文在不同普通 API 进程中仅 GET 冷读，两角色分别实际下载来源／目标包。首阶段两个角色共 18 个发送 POST 与 18 个收到的成功回应（两集合分别观测）；冷阶段各宽度 49 个 GET。合计 14 个不同实际下载文件，均核全文 UTF-8 字节；七类权限表及 assignment 无运行时变化，Case 仍 NEEDS_INPUT／目标未完成。

## 分窗结果，不能累加

| 窗口 | 实际结果 | 限定 |
|---|---|---|
| dev1 修改中，Git HEAD 为基线 | 1 FAIL／0 ERROR／0 SKIP，45.944847 秒 | 新测试误选协同标签，隐藏服务目录；产品字节等基线。失败、PNG、原日志保留。 |
| dev2 修导航，Git HEAD 为基线 | 1 FAIL／0 ERROR／0 SKIP，28.716852 秒 | 复制后确认按钮仍 enabled；产品字节仍等基线，是真实 UI 缺口。 |
| dev3 修改中 | 1 PASS，39.925684 秒 | 修 gate 后 1200 完整链；输入还不同于最终补强后的冻结，不当作基线原样通过。 |
| 冻结完整定向窗 | **43 PASS／0 FAIL／0 ERROR／0 SKIP**，{a['elapsed_seconds']:.6f} 秒 | 32 原复用 API＋2 新完整 DOM＋9 原确认／补正／异议／必需读取／未知恢复用例；只此43范围。 |
| 独立同冻结私有镜像 | **4 PASS／0 FAIL／0 ERROR／0 SKIP**，90.706048 秒 | 新完整 DOM 两宽度＋原异议链＋必需读取 conflict。4 全是主43的重叠节点，不增加唯一数。 |

两冻结执行均用独有 Git archive 镜像和数据库；761 输入、五合同共享／镜像 PRE／POST 零漂移，0 自动重跑。主窗 84 个实际 pytest 模块均来自镜像 src 且匹配冻结 SHA；普通子 API／worker 没有额外逐模块来源探针，不能扩大该观测。主窗1118个连接均有 connect_end／close_end，无连接失败事件或失败数据库采样；四个新链 ordinary API 均 spawn／ready／stop_end，自有 terminate 后 child_exit=-15，pytest 退出0。启动前短暂 health_error 原样保留，未出现 deadline；原连接2秒、DROP5000ms、ordinary循环15秒、health HTTP15秒预算均未放宽。

独审开放 P1／P2 为0；[独立原报告](evidence/ordinary-reuse-user-flow-20261018/runtime/independent-final-review.json) 原件 SHA256 `{reference['sha256']}`。[主窗与证据原件目录](evidence/ordinary-reuse-user-flow-20261018/runtime/) 含逐 ID、模块来源、诊断、输入、原失败、实际下载及截图；[归档清单](evidence/ordinary-reuse-user-flow-20261018/manifest.json) 记录 raw/public 哈希与脱敏差异。

归档 {archive['pairs']} 个 raw/public 对、{archive['redactions']} 处临时 SYNTHETIC session candidate 脱敏，JUnit标识 {archive['JUnit_identifiers_unchanged']} 个实例保持，JSON／JSONL／XML 严格解析及 PNG CRC／解压通过。公开副本不含 PG data 或私有 bootstrap；原件留在本地新 runtime。基线继承 {inherited['actual_byte_hashes_verified']} 个 evidence Git blob 全部实际工作字节匹配，旧树未改，未知锁保留。截图为资料包附近的 viewport，不是复用历史面板全页截图；历史文本由真实 DOM 和 JSON 断言。1200／320 目视包与边界、窄屏按钮换行通过，完整正文以实际文件字节验。

先前301窗／错误修补窗／最终27及独25全重叠、382窗的原 setup＋teardown 两ERROR、独测53P1F及后来通过口径沿 [前片完整记录](OriginalCollaborationDOMValidation-20261018.md) 保持。连接／清理／启动底因仍 UNKNOWN，当前绿窗不解释或抹除它们。没有全项目单窗全绿、正式 AT35 或跨企业模板 AT08 结论。

## 还缺的最小合法输入与边界

- 本片普通 LOCAL 用例的安装包／journal 与当前数据库／目录绑定、既有会话和 READ／EXECUTE／case.create／PREPARE 权限、既有 REVIEW_ASSIGNED 专员、精确 preparation_catalog。再次使用须来源本人、同租户／精确服务版本、当前完整已核对并确认的两槽资料；目标是同主体新空白事项。本片不需要 Run executor assignment；实际执行者流程另需既有当前精确 assignment。缺项拒绝，不自动创建真实资料或权限。
- 正式来源仍缺专用 backend／主体映射／原采纳适配合同及代码。需既有来源域、记录 ID／合同版本／只读结构和获准脱敏样本；preparation／Case／Run／adopted plan 关系与版本／fingerprint／current-head；原 ADOPT decision／actor／状态／撤销及回执语义；既有主体映射、权限／用途／有效期／撤销；公开 trust／签名覆盖／独立验真协议。逐字段见 [既有来源合同](ReceiptSubmitRecovery-20261018.md)。不要交付 token、密码、私钥或 DSN。仅有凭据不能补合同与代码。
- 正式五证明仍 UNAVAILABLE／FORMAL_PROVENANCE_CONTRACT_NOT_IMPLEMENTED；NativeRunAccess permit／writer 默认拒绝，资源批准只读尚不可消费，IsolatedPlanApproval 仅隔离测试。真实 Windows11（含已审迁移与已安装 PG 环境）、正式 AT／真实业务输入与预期、正式模板／规则来源等仍待。无 Windows／真实模型／正式批准／业务／履约／部署验收。

本片没有触及既有 SUBMIT 并发测试。其 overlap 两分支仍旧回复先 fulfill、80ms 不证明 settled，尚缺“新回复先完成、旧200／403最后到”的确定顺序。该项作为下一最小本地候选记录，不宣称已覆盖；本轮先完成 distinct 两新事项复用用户流程。其他原方案缺口沿前片清单，不新增范围。无 main 改动、强推、部署、真实身份／Grant／分派／目录发布／批准、凭据、真实模型调用、费用或安全网络权限。

交付文档只追加当前状态；历史段原字节为后缀保留。正常 dev push 后的实际完整交付 SHA、远端全部 heads 差异、main 和显式目标 ref 的 ahead／behind，记录于本地 `.runtime/ordinary-reuse-user-flow-20261018/delivery-and-remote-verification.json` 并由最终回报给出；本报告不预认未执行网络动作。
'''
(root/'docs/F2/MaterialReuseDOMValidation-20261018.md').write_text(text)
print('Wrote source-bound validation report from actual completed windows and archive.')
