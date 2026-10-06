# ENG040 普通dev同步及新安全annotations实际送达

用户解除此前push暂停，授权普通快进同步ENG032—ENG039并跟踪一次既有标准Windows Server CI。实时origin/dev/f1-foundation=c5b389bf0ae45fd9601182114739a597da13dfa2，为本地8ddf139e293e18f77983c10f280dfb8ae4007f60祖先；远端独有0/本地7，工作树干净，无runtime/cache/log/zip进入差异。ENG039四份最终源码hash保持，工作流与实时远端字节相同。普通push成功，ls-remote精确验证8ddf139；未force/reset、merge main或修改runner/权限/环境/代理/身份。

## 精确本轮CI事实

唯一标准push run [37439323047](https://github.com/T1doo/ParkWeave/actions/runs/37439323047)，attempt1，head_sha=8ddf139e293e18f77983c10f280dfb8ae4007f60；job112188860230，终态completed/failure。Checkout/Python选择/原生PG准备成功；native_suite exit1，693.422秒，timed_out=False，cleanup=NOT_NEEDED。独立安全发布器与owned临时PG停止步骤success。没有manual dispatch、rerun或第二轮源码CI，未调用/下载被拒日志路由或artifacts。

正常checks API的title/summary/text仍null，但**新annotations真实送达**：一个SUMMARY_AVAILABLE头与4个FAIL/NOT_RUN摘要，report_state=COMPLETED、active_phase=UNKNOWN；头部实际case_counts=5PASS/3FAIL/1NOT_RUN、annotation_cases_omitted=0。收到的5条逐项解析/字段白名单/重新构造命令字节与全局精确测试ID界限均通过，暂无测试ID输出。聚合PASS是harness case数，不是pytest成绩或整项AT签收。

| 实际harness case | 正常API可见结果 |
|---|---|
| Doctor_native | FAIL，exit_code1；底层原因/类别未给出，UNKNOWN。 |
| Start_native | FAIL，exit_code1；底层原因/类别未给出，UNKNOWN。 |
| API_browser_restart | NOT_RUN，START_FAILED；不假定API/浏览器/重启通过。 |
| full_engineering_regression | FAIL，phase=regression_run，category=TimeoutExpired，counts_state=MISSING；没有具体pytest test ID。 |

同head源码native_suite在regression_run对子run_acceptance使用600秒wait；实际TimeoutExpired定位该内部完整回归等待边界，区别于外层900秒wrapper未超时。不能据此认定单个测试失败/挂住或给出pytest PASS/FAIL数量，也不能追溯断言旧37420887816是相同根因。Doctor/Start exit1的真正触发条件仍UNKNOWN，不猜授权、ACL、PG连接或依赖问题。

清理：workflow Stop owned临时cluster成功，pg_status exit0/无超时（0.032s），pg_stop exit0/无超时（0.234s）。native_suite外层cleanup=NOT_NEEDED只说明未触发超时回收，不代表逐项应用清理通过；app final_Stop子项未单列于失败摘要，不据缺行补造PASS。Stop过程仅现有绑定自有集群，权限/25分钟/contents:read/always顺序保持。

## 当前诊断收益及剩余信息

ENG039的新通道已通过真实GitHub正常annotations API验证，无需私有日志或新增权限。已有足够真实证据定位Doctor/Start失败与内部regression等待超时，但尚无底层BoundaryError原因代码及具体pytest进行中/失败ID。下一诊断建议仅给Doctor/Start增加有限白名单类别/原因码，并为完整回归增加有界可信进度ID；需另行授权后实施/独立复核，不盲改timeout、反复CI或读原日志。

证据见[evidence](evidence/eng040-sync-ci.json)。本轮事实文档的后续同步只改docs，现有唯一工作流paths不含docs，因此不触发第二轮CI；CI仅证明8ddf139源码的实际结果，不宣称后续docs SHA经过相同CI。原环境/备份/运行证据保留；0真实模型/预算、R4关闭、F1/F2未签收、Server不是Win11、36AT6EX NOT_RUN，无部署或外部履约。
