# 修正候选复核：LIMITED PASS

沿用gpt-6.1-sol / medium。首次BLOCKED、源码快照与期限反例原FAIL完整保留，本文件单独签修正后的源码hash快照。修正前后审查源hash零漂移；最终冻结源码 `8ea7060509e6e91aacaf06a2bce7f14997225000` 的8个受审源码/测试/清单路径逐项Git blob hash/bytes与审查快照相同（frozen-source-check.json）。

修正后独立candidate DI **62 PASS / 0 FAIL / 0 ERROR / 0 SKIP**；独立期限反例复测 **1 PASS / 0 FAIL / 0 ERROR / 0 SKIP**。根既有final-corrected XML **239 PASS / 0 FAIL / 0 ERROR / 0 SKIP**只核对原件，不重复运行、不相加。独立先前57PASS、deadline-first 1FAIL、根233PASS/1FAIL注册缺口均保留；注册失败同ID在根最终窗口PASS。

HC01–HC04已在限定范围解决：失败保留T和其身份；成功删身份前核NOFOLLOW/单链接/UID/mode并把已知秘密收回root0600，T删除失败也不留下可复用UID秘密。CLOSE共用select+os.write，绝对monotonic120s cleanup budget，专用CleanupTimeout穿透所有逐资源异常handler；外层标未完成项UNKNOWN/FAIL。原来源逐项lstat/root保护拒symlink后复制。固定T外claim对象及其排他权限/寿命已明确写入待审批清单。setup原owner Store/proof持久保存。app/case共用实际42501/rollback/SELECT1控制，纯DI也覆盖拒绝及正控制。

默认approval仍false/null/null；workflow单次repo/branch/push/number/attempt、25m job门禁未放开。封闭公开摘要、private pipe/log、既有postgres账号不改组、retainedPopen/PID实例、新库issued-owner proof、SQLnative与business角色/Store分离、Case单事件和Run历史保留约束成立。用户批准仍未发行；需冻结包含helper的最终完整源码SHA，审批精确绑定后才能单一approval差异。

**LIMITED_PASS_CORRECTED_CANDIDATE_PURE_STATIC_ONLY，无剩余阻断发现。** 本轮仅只读与有界纯DI，未执行helper、runner、OS身份/权限、SQL/PG/IPC、随机秘密配置或网络动作；不签真实host/ACL结果。外部SIGKILL、失联worker、不可恢复解释器挂死不签全清理；失败保留资源明确FAIL，不能用VM回收冒充擦除。丢响应仅限TestClient已返回后主动丢弃→原key GET，不签真实传输断线/worker死亡恢复。当前结论不授权执行、不合并窗口计数。
