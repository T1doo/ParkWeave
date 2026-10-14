# 旧采纳错误终态的冷读与新键隔离

基线 `83dbad384d4b8af5250fcb9ad5754b18d4b330d9`；源码 `16c24a4fa74429aabc730ec9216ebf4ec643698a`。旧版本将一次首次明确拒绝错误标为 `CLOSED_NOT_COMMITTED / FIRST_DEFINITE_REFUSAL`。删除本地恢复句柄后，普通实例 GET 与新键采纳没有沿原恢复端点隔离，可能重新打开采纳入口。

本轮普通冷读直接返回 UNKNOWN、adoption_quarantined 与原日志状态/原因；页面无 localStorage 也关闭预览、采用、办理入口。服务端在新键编辑/采用及 resume 日志写入前验证隔离，并覆盖旧 ADOPT_PLAN reconcile 的持久更新。规划 GET 保留历史读取并明确禁用采纳。数据库原状态、请求、资料与迟到实际成功方案均不改写；UNKNOWN 优先于已存在的方案事实。

不是所有 CLOSED 均被禁止。严格版本推进终态必须验证原外键、派生内键、原 body SHA、全参数 fingerprint、模板必需目标、原 Run/准备绑定，再经原 core recovery 核实真实严格推进和永久不提交证明；只改 proof_kind 标签不能绕过。合法严格版本终态仍允许查看当前方案并以显式新键采用。当前 READ/PREPARE/EXECUTE 撤权优先返回403，既有历史有权读取保留。原 consume 创建键已确认的 CREATE_RUN 回放保持只读，不扩大本片业务写合同。

## 真实验证

原源码红窗：两项实际 API/完整HTML NodeVM→ASGI→owned PostgreSQL测试均 FAIL，2 WARN、exit1；失败证据完整保留。补丁中间绿窗2 PASS单列，不计最终成绩。

独立冻结最终窗：9 PASS、0 FAIL/ERROR/SKIP、2 WARN、9.90秒，229文件前后哈希零差异。覆盖无本地句柄采用/编辑/resume409且业务/授权审计/consumer日志无写，迟到原内键201成功保留而新键仍409，真实严格推进终态继续、伪造严格标签隔离和三种能力撤权403。独审 LIMITED_PASS，无新增阻断。独审首窗9个夹具setup ERROR未执行业务；修夹具中间9 PASS未冻结，分别归档，不计最终窗。

最终根11模块冻结回归：**221 PASS、0 FAIL/ERROR/SKIP、2 WARN、171.83秒、exit0**；229文件哈希一致。实际页面冷启动9断言PASS、2次真实GET、0 POST，业务/日志零写。见归档 final-regression 和 cold-page-chain；各窗口不加总。页面运行完整原HTML，真实GET桥接原ASGI/owned PostgreSQL，空localStorage，无业务POST或日志变化。

## 范围与后续

这是旧无效终态的兼容隔离修复，未恢复或替换旧历史，也未宣称完整正式模板生命周期。没有浏览器执行；历史明确拒绝保持。prepare一次授权的元数据读取 Forbidden 保持停止，没有切换工具或启动作业；两份approval仍false/null/null。没有真实模型、生产迁移、部署、新Grant或registry。

下一片沿原V1 §5.1与ENG100：核实新实例事实用途/来源选择与冲突澄清的纵向缺口，复用已存在 FactBundle/clarifications，不重复后端组件。当前 Intake 只允许 facts.assess 的 candidate_review，模板普通 case.create 不能直接传事实候选；原 submit 还需当前 facts.assess action grant 及字段 READ/WRITE。不得默增 Grant 或把 case.create 输入伪装为事实评估；此后续未实施或申领通过。

机器证据：[export-index.json](evidence/legacy-closed-20261014/export-index.json)，保留各原始窗口SHA及导出SHA。仅生成夹具会话repr行脱敏，原件保存在指定环境.runtime下。
