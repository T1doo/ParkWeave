# 历史检查与当前来源对照：本批交付范围

源码冻结 `c74489ccb67347bc9ec607a5b7148be6e81830c4`，基线 `9c7bbc569353dc9234d10ee566f03114f686d3b4`。开发分支 `dev/f3-fact-history-comparison-20261016`；最终归档提交以Git分支HEAD和交接记录为准。

用户在 `/local-facts` 第4节填写已有历史运行编号，点击“只读对照当前来源”。服务端重新检查当前身份、owner、园区/组织与原检查全部字段READ，以同一SQL语句快照及服务器时间读取来源，再用原worker共用的判定函数显示新增来源、新过期来源和当前冲突。失去READ返回403，页面清空对照；不补权、不重建历史。来源正文只按文本显示。历史中的KNOWN仅指当时有效来源取值一致，真实性始终UNVERIFIED、资格NOT_EVALUATED。

需要新检查时仍在第2节填写目的、勾选确认并明确提交原facts.assess。待原worker完成，保留旧编号于第4节、填写新编号于第3节，再并列读取。新检查须时间更晚、字段相同；它是另一份独立保存记录，不是旧回执的替换或Case版本采纳。快照持续可能变化，并列展示不承诺新检查覆盖后来变化。查看按钮只有GET，不触发worker或新的模型步骤。

新增GET `/api/runs/{run_id}/fact-comparison` 复用原READ和字段权限；事务READ ONLY，返回原回执、当前非持久化投影和逐字段变化ID。无新增POST、schema、命令权限、PREPARE、分派、批准或Case进度；原输入、运行、worker和幂等提交合同保持。拒绝请求可能按原HTTP审计路径写授权审计，测试的“不变”指所列业务/权限表，不冒称审计表零写。

## 实际验证

同冻结SHA运行五个完整受影响模块，73唯一项通过，0失败/错误/跳过：

```sh
.venv/bin/python -m pytest tests/test_fact_history_comparison.py tests/test_local_fact_entry.py tests/test_facts_heartbeat.py tests/test_candidate_review.py tests/test_foundation.py -q --basetemp=/tmp/parkweave-fact-compare-final-v1 --junitxml=.runtime/fact-compare-root/final-v1.xml
```

新模块仅三项：

- 实际HTML/Chromium两次保存来源：首次原检查一致，新增矛盾来源只读显示新增1、冲突2且原回执不变；业务/权限表快照不变，只有用户原表单再次明确提交后才产生第二次检查。新旧实际并列，逆序旧检查拒绝。原流程共4POST，比较0POST；停止后同端口重启，新浏览器只GET两份记录，0POST、所列表快照不变。跨组织读取拒绝。
- 原API保存短有效期来源，原worker首次检查一致；不改数据库时间或来源，等待真实服务器时间到期，只读显示新过期ID和补当前有效来源条件。明确原facts.assess才保存过期结果，旧记录保持。
- 原owner夹具独立撤回region READ，页面对照403并清空；重启后比较、历史读取和新检查均拒绝。权限表保持已撤回状态，用户路径无补权或seed。

原来源页7项覆盖丢回执原键冷GET/参数冲突/身份和读取ABA；原facts heartbeat14、candidate28、foundation21完整模块覆盖共享投影与原执行合同。candidate回归使用原离线Mock，真实模型调用0。不扩增无关矩阵、不称全仓通过。独立审查者同SHA独跑新3项，全部与73重叠，不能加成76；源码/测试/配置708文件hash复核无差异。

## 失败、证据与边界

首开发dev-v1为3失败：测试观察器额外get_server持有生命周期引用，原启动器退出时postmaster.pid仍存在；已保留原失败XML、日志与原目录。修测试为从本次自有postmaster.pid直连已运行socket，不注册新server，不改变产品停库规则。dev-v2开发3通过，正式冻结和独审另列。没有清理失败数据、绕CSP或访问拒绝；没有把开发通过计入最终唯一项。6268份旧封存原件hash保持。

证据入口：[最终门禁](evidence/fact-history-comparison-20261016/root/final-gate.json)、[原始测试XML](evidence/fact-history-comparison-20261016/root/final-v1.xml)、[新旧实际页面](evidence/fact-history-comparison-20261016/root/actual-history-current-new.png)、[用户链证明](evidence/fact-history-comparison-20261016/root/actual-chain-proof.json)、[独立审查](evidence/fact-history-comparison-20261016/review/frozen-review.md)、[封存清单](evidence/fact-history-comparison-20261016/primary-seals.json)。公开副本逐字配对，已扫描注册合成token且零命中；不复制私有会话文件。

本批是原F3-T03最小历史检查/当前来源对照。来源仅合成，尚不绑定Case计划/版本、不自动采纳来源修订、不执行受影响P1–P5。原六目标、计划节点、历史及未受影响证据保持既有范围。后续关键路径仍为合法普通运行时身份/访问分派、可信目录/批准跨进程接线，以及原方案下明确Case修订采纳闭环。Windows、完整正式AT35、来源真实性、真实模型、生产/部署、CI未执行；原90模块/2251历史节点仍未重跑。没有改main、强推、部署、新增费用/凭据或产品安全权限。
