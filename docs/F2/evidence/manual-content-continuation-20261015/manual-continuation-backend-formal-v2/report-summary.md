冻结 `14bc83f241149bd03907bd088a35eb6df53ba0a2` 的七个完整模块 235 PASS，0 FAIL/ERROR/SKIP，耗时 2402.01s。collection/JUnit 各235个唯一节点精确对应，调用进度与JUnit顺序一致；608源码与全部13252跟踪文件前后哈希无差异，HEAD和工作树保持冻结状态。旧ef16窗214 PASS/21未执行为明确中止证据，不纳入成绩。

41份原HTML轨迹为6+9+14+12。共957条页面驱动fetch记录，排除Python夹具初始化与控制消息；夹具HTTP总数未计。按原mode分29份真实后端响应场景、7份真实后端提交后受控丢回执、5份受控客户端负向。逐文件hash/mode见html-summary.json；Node VM/DOM shim不等于真实浏览器。

下表每格为“记录数 / 期望受影响步骤对数”，逐记录字面集合比较，不能作为产品完成度或总体精度估计。77条记录全部绑定本冻结SHA；各分组漏影响、错影响、错保留、漏保留均0。typed实际额外UNKNOWN保留为1条/5步，未混入确定组。

| Suite | 确定分区 | 声明UNKNOWN | 额外观察UNKNOWN |
|---|---:|---:|---:|
| test_typed_source_impact_independent | 8 / 23 | 2 / 10 | 1 / 5 |
| test_shared_source_cases_independent | 8 / 14 | 4 / 10 | 0 / 0 |
| test_service_release_preflight_independent | 15 / 62 | 4 / 20 | 0 / 0 |
| test_at24_27_change_batch_independent | 27 / 100 | 8 / 40 | 0 / 0 |

Release预检19条记录具锁字段，期望锁交集共3对，错锁0；其它原oracle无锁字段，不能视作零锁测试。另选中容量真实重绑定的A/B两Case分别证明P1锁逐字保留、六目标本地输出核验完成。Windows、真实浏览器、正式业务AT、真实模型、生产均未执行；无Git/共享源码写入。
