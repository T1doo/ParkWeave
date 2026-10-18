from pathlib import Path
root=Path('/workspace/ParkWeave')
entry="""## 2026-10-18：F2-T05 普通 ACCEPT 原键只读冷恢复

产品冻结 `35031ba7334006089889f6488dfbe1feb5bc10b4`，最终源码/测试冻结 `0ec816ff566ad4b9966229f5eb82123f5b984693`，二者产品src树均为 `e0f8443127b49b5feb9e1b880e8998ca67b5c404`。复用原身份/READ/精确Run分派及ACCEPT与回执CREATE原事务证明，增加原actor/key/offer/revision限定GET；页面只存有界不含会话或正文的句柄，未知结果经明确GET历史核对和当前GET再释放，无重发ACCEPT或自动P3。NOT_OBSERVED保持未决，损坏/过期不解锁；普通其他动作/回执未获得通用恢复。

最终8完整相关模块161唯一项PASS，745输入PRE/POST零漂移；独测77项与161全部重叠，不累加。较早bfb的24完整模块实际575PASS/1FAIL保留，旧过期fixture在目标锁前P5准备409；仅修测试准备窗口并保留原等待预算/负断言，新增实际SQL存活/等待/过期见证，再重跑上述最终范围。两SHA/开发/独测成绩不拼接为全仓或576项全绿。原证据仅更正已由源码证明的测试标识，旧副本及所有失败/中断保全。详见[本批范围与原件](REPORT_LINK)。

真实Chromium普通configured_app正向初态仍由自有合成fixture预置已REVIEW/CONFIRM资料、精确Run合法assignment及OFFER。普通运行缺PREPARE/REVIEW_ASSIGNED/preparation_catalog继续准确拒绝；可信NativeRunAccess/provider及正式来源/批准接线仍未完成，permit/writer默认拒绝，IsolatedPlanApproval不作普通批准。Windows、正式AT/AT35、真实主体/业务/模型、生产与部署未验；完整项目未完成。没有main修改、强推、部署、新费用/真实身份/Grant/分派/目录发布/批准/凭据或安全权限扩大，未知锁保留。下方历史原字节保留。

"""
for name,link in [('docs/F2/Plan.md','DispatchAcceptRecovery-20261018.md'),('docs/分阶段开发计划.md','F2/DispatchAcceptRecovery-20261018.md')]:
    p=root/name;old=p.read_text();assert not old.startswith('## 2026-10-18：F2-T05 普通 ACCEPT 原键只读冷恢复');p.write_text(entry.replace('REPORT_LINK',link)+old)
print('Prepended two dated plan entries; historical text untouched')
