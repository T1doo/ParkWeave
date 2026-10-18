from pathlib import Path
import json,hashlib
root=Path('/workspace/ParkWeave');r=root/'.runtime/receipt-submit-settled-order-20261018';d=root/'docs/F2/evidence/receipt-submit-settled-order-20261018';a=json.loads((r/'accepted-tests.json').read_text());f=json.loads((r/'frozen-freeze.json').read_text());v=json.loads((d/'archive-validation.json').read_text());ref=json.loads((r/'independent-report-reference.json').read_text());old=json.loads((r/'inherited-evidence-proof.json').read_text())
assert a['passed']==6 and a['failures']==a['errors']==a['skipped']==0
text=f'''# SUBMIT 冷恢复确定性完成顺序验证

冻结 `{a['source_sha']}`，src tree `{a['source_tree']}`，tests tree `{a['tests_tree']}`；基线 `c66eb07f381eb3b5d1fe5791f3291ad784d861e2`，分支 `dev/f2-receipt-submit-settled-order-20261018`。本片**未发现产品缺陷，未改src**；只补父级指出的测试证明缺口。[合同](ReceiptSubmitSettledOrder-20261018.md) SHA256 `{f['contracts']['docs/F2/ReceiptSubmitSettledOrder-20261018.md']}`。

## 实际完成顺序

保留原四个节点ID，含旧200／403与旧先返回／新恢复先开始。原 `new_before_old` 仅“新请求先开始”，仍旧回复先完成；不迁移旧成绩或重命名历史。删去80ms推定，用原按钮onclick返回的实际Promise完成屏障；原handler含页面async包装和receiptSubmitRecover().catch(receiptError)，观察其settlement在原catch／finally之后。

观察器仅附加then记录序号，真实DOM点击传原this／event单次调用并返回原Promise；不写业务变量、不改原函数体或安全门。所有屏障要求returnedPromise、settled与fulfilled；fulfilled指原handler包括catch结束，不代表被注入的旧HTTP403成功。捕获服务器回复的短轮询只等实际route.fetch结果，不作settled证明。

| 场景 | 旧handler结束序号 | 新handler结束序号 | 显式release结束 |
| --- | --- | --- | --- |
| 原旧先完成，200／403 | 4 | 6 | 8 |
| 原新先开始／旧先完成，200／403 | 5 | 6 | 8 |
| **新先完整完成／旧最后到，200／403** | **6** | **5** | **8** |

新两例先让新GET返回并等完整handler结束，核COMMITTED全文等真实新回复、busy=false、operation=null、release enabled；此时旧handler仍未settled才交付旧200／403。旧完成后完整受检state相同，proof／handle／view／context的对象引用身份亦相同。正文与来源草稿、完整原raw句柄、当前代／对象及视图不变，之后才显式release并等其handler完成，核proof为空和句柄删除、草稿保留。

比较范围准确限于现有state字段：按钮disabled、receipt-error、detailHidden、draft/source、proof/handle/storage/view及不含token的上下文。未覆盖所有可见状态文案或所有hidden属性；这是独审低优先观察建议，不将其当产品缺陷或继续制造外围测试。引用闭包不序列化完整context／token。

403由既有另一fixture主体对捕获旧GET的Authorization替换，经实际服务器拒绝后延迟交付；这是运输故障注入，不是当前executor撤权。当前token／Grant／assignment未改变。header不落证据；page request与实际route.fetch转发另列。每例仅一次原浏览器POST及一次实际转发POST，冷恢复段仅GET，Case完整历史与七类权限快照不变，SUBMIT一事件、无ACK。fixture无service_case_plan，空计划及preparation行不变且无P4写入；不称已采用计划P4正向全链或跨进程localStorage CAS，HTTP请求未物理取消。

## 实际窗口和证据

- 开发 dev1 新200节点：1PASS／0FES，14.793267秒。Git HEAD当时为c66，输入manifest记录修改中test/合同字节，尚无最终引用断言；不当作基线原样通过或最终冻结成绩。
- 冻结主窗：**6唯一PASS／0FAIL／0ERROR／0SKIP**，{a['elapsed_seconds']:.6f}秒，exit0。原4＋新2，完整实际collection与JUnit一致，没有跑全部17个browser节点或全项目。
- 独立私有镜像：**2PASS／0FES**，26.888959秒（pytest24.42秒），exit0；两项均在主6中，全部重叠，不加总。静审P1／P2与当前交付阻断为0。

两冻结窗762输入、6合同共享／镜像PRE／POST零漂移，0自动重跑。原11个非竞态节点代码前缀原字节保持，本片未重跑；已有成功实现及范围直接复用。84个实际pytest模块来自镜像src且匹配冻结；子API imports未额外仪表，命令cwd／PYTHONPATH是原镜像helper，不扩大成逐模块实证。主176连接均connect_end／close_end，无失败连接／遗留未close事件；六个自有ordinary API均ready和stop_end（原helper正常terminate为-15），pytest exit0。原2秒连接／DROP5000ms／ordinary循环15秒及health HTTP15秒不改。

[独立原报告](evidence/receipt-submit-settled-order-20261018/runtime/independent-final-review.json) raw SHA256 `{ref['sha256']}`。[实际完成序列摘要](evidence/receipt-submit-settled-order-20261018/runtime/actual-completion-summary.json)、[原JUnit](evidence/receipt-submit-settled-order-20261018/runtime/frozen.xml)、[原窗口／诊断目录](evidence/receipt-submit-settled-order-20261018/runtime/)和[raw/public清单](evidence/receipt-submit-settled-order-20261018/manifest.json)保留实际记录。归档{v['pairs']}对、{v['redactions']}处临时SYNTHETIC session candidate脱敏，JUnit标识{v['JUnit_identifiers_unchanged']}个实例保持，严格JSON／JSONL／XML、PNG CRC／解压及SHA／长度检查通过；无PGdata或私有bootstrap导出。

基线继承{old['actual_byte_hashes_verified']}个evidence Git blob实际字节逐一匹配，旧树未改，未知锁保留。此前301/382等原失败、setup＋teardown ERROR和独测53P1F／后来PASS口径沿[历史报告](OriginalCollaborationDOMValidation-20261018.md)及[前片材料复用](MaterialReuseDOMValidation-20261018.md)原字节保持；启动／连接／清理底因仍UNKNOWN，当前绿不解释旧失败。

## 原方案剩余交付门

完整清单见[原方案剩余实质交付门](RemainingDeliveryGates-20261018.md)：已完成的partial人工协作、同事项关闭重开、两新事项材料复用普通DOM链不重复列待办。本片LOCAL竞态证明缺口关闭后，下一实质条件是正式来源合同与专用backend／主体／原采纳适配、既有合法权限目录与记录、真实Windows原生／干净重建、获准LIVE工具与冻结B0/B1/B2、适用规则／日历与第二园区映射、原固定AT逐项实际回执，以及C0官方模板／规则／视频和接收回执。无试点可按原方案披露，不强加试点；F4–F6不加作PR0/C0前置，不要求新统一框架或单窗刷数。

正式五证明UNAVAILABLE／NativeRunAccess permit与writer默认拒绝／资源批准只读不可消费／IsolatedPlanApproval仅隔离测试保持。项目IN_PROGRESS，Windows／正式AT／真实来源批准业务／模型／现实履约均NOT_RUN；无main、强推、部署、新费用／凭据／安全权限或新增真实身份、Grant、分派、目录发布、批准。实际普通分支推送完整SHA与远端差异在本地 `.runtime/receipt-submit-settled-order-20261018/delivery-and-remote-verification.json` 另记并由最终回报给出，不在自引用文档预认网络动作。
'''
(root/'docs/F2/ReceiptSubmitSettledOrderValidation-20261018.md').write_text(text)
print('Wrote validation report and linked only original substantive delivery gates.')
