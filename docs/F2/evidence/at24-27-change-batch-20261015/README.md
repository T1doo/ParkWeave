# AT24–27 固定双 Case 变化批证据

最终验证源码 `5a7eee826564426a4c36607ac038bd61e00665d7`；基线交付 `f9834d44e5ec7600848784bfaf07f88ff4cf8691`。历史WIP、首轮77059失败/中断与最终5a7eee8完整窗口分列保留。index的source_sha是最终参考，不表示每个历史条目都在该SHA重跑。

同一最终冻结五个不重叠窗口：root27模块900PASS、root25模块789PASS、independent7模块235PASS、review13模块388PASS、公共入口消费者18模块305PASS；90完整相关模块2617唯一项，0FAIL/ERROR/SKIP，不是全仓。各窗原始collection/JUnit精确唯一、605源码和原12417 tracked文件零漂移，详[根并集核验](at24-27-root/final-regression-verification.json)。独审20个页面函数VM探针单列，不加入2617。

[独测交接](at24-27-independent/independent-v3-handoff.json)、[逐AT与20场景](at24-27-independent/independent-v3-per-at.json)及[精度统计](at24-27-independent/independent-v3-oracle-statistics.json)。新35条传播观测为known27/100对与保守UNKNOWN8/40对，漏更/误更/误保留0；35条没有锁字段，实际已选容量两Case的P1锁/旧预约与重绑后六目标验证另列2例。旧typed一条实际UNKNOWN不归入known；其他组分别统计，不将未知扩大重验称精确定位。

[41个原HTML流程](at24-27-independent/independent-v3-html-summary.json)为typed6/shared9/preflight14/new12；本批12严格分9真实后端响应模式与3受控客户端negative，全41含5个DOM/transport负向，不称都是真实后端拒绝。实际Node捕获957 HTTP、Python test-body捕获6109 loopback HTTP，不含全部setup。原HTML以Node VM/DOM替身执行，使用实际HTTP/ASGI/自有PostgreSQL；真实浏览器未执行。两实际新说明GET403直接无业务写快照、5条读取差异观测另列，其中late_403一条有3项原invalidated字段观察差异，其余4条无变化，授权拒绝审计与业务事实分开。

首轮root完整896P4F/767P22F，26失败同公共清理路径与旧DOM驱动firstChild缺口有关。只把新option值在插入前设置，真实DOM等价，原tests/driver/assert及业务/权限门不变；原26修复焦点全PASS，7ASGI/PG桥接与19DOM/transport分列，再新freeze从头90完整模块。旧独测208/235中断不称235通过，旧独审388只属旧SHA；私有getter候选前2项后中断及其无classname后处理停点、初始hash门、夹具/收口失败和有限修正全部保留。未创造不存在的首hash门raw stderr；integration-first-failure.json仅为当时错误和实际hash差异记录。

主档775个raw/export配对，公开配对载荷50,568,287字节；20处精确已登记合成会话值替换、52行pytest截断fixture repr掩码。私有原件/hash/大小保持，JSON/XML/JSONL解析后去敏，未改用例名/状态冒充通过。私有登记集0600、PG/SQLite数据、cache、完整工作副本及未填草稿不导出；旧模板共用去敏集只用于识别合成值，不是本批专属测试证据。原始证据的文本格式按目录.gitattributes保留，证据范围关闭whitespace检查不影响产品源码检查。known-token matcher有明确共享已验证来源，不声称算法多样性。

根audit.json保留待独审checkpoint，后续独立重构及完整门见[独立审计目录](../at24-27-change-batch-audit-20261015/)。不覆盖初始失败、不自引用；独立重构不导入根producer/verifier。原始失败和本轮实际命令及source/runner/plugin/前后清单均在index中。

P1仅为本人协调注记，KEEP_MANUAL/DEFER保留决定但继续待办，完成冲突采纳使用明确ACCEPT_SOURCE→原ADOPT→受影响VERIFY。携注记非局部替换/模板应用拒绝，未实现一般内容合并；原六目标、P1–P5、历史和未影响锁保留。真实合同变化拒绝局部替换，真实UNKNOWN扩大重验且拒绝ADOPT。原再绑定正式替代Approval仍NOT_IMPLEMENTED；MIGRATE422仅类型拒绝，BREAKING apply409有当前完整proof，旧ref403不是执行业务回滚。

Windows/Win11、真实浏览器、正式业务AT、真实产品模型/B0–B2、正式来源治理/批准主体、现实履约回执、生产和本分支CI均未执行。模型调用0，无新增费用/真实凭据/安全权限、部署、强推或main修改。
