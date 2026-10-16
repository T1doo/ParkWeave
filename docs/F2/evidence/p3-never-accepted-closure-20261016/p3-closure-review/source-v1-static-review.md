# P3 closure backend source-v1 独立静态复核

STATIC_ONLY / NOT_TESTED；依据固定manifest `a49169c6ae72096bfa4c237716b51cd9ecabc314d8dd7aba2fd30e3f7e31471a`及其5产品源码。未启动PG或导入私有候选执行；不迁backend私有2PASS作为独审分数。

## 集成前阻断

1. native `_guard()`当前比较实际8表与snapshot、positive marker且无P4/P5，但未独立检查真实closed/neverACCEPT/完整trace。Python `_replay`强拒并不等于DB锚自身证明closed。需要专用原生约束实际terminal、无ACCEPT/receiptpointer、完整根和事件及positive trace；不能只把epoch0门放宽。根已确认修正，等待新固定source-v2。
2. `validate_qualification`先把closure改造成profileKNOWN_NOT_STARTED/epoch0及空集合再调用bf校验，虽只想复用结构，但实际伪造零资格DTO与本片独立profile边界不符。应独立验证或抽真正通用identity/prefix helper，原zero eligibility不改。根已要求修正。

## 已静态核实的正向设计

- 单独P3_NEVER_ACCEPTED_CLOSED_V1、compatibility schema3、专用append-only消费列与2trigger；未重置原positive marker。创建factory在同事务原ownerproof+parent ACCESS EXCLUSIVE+无prep/无8表行下安装完整原追踪及新anchor，再首次固定全catalog。旧base _install只是机械抽取，须冻结后再核零路径回归。
- `_snapshot`读取全部8表、每表65界检测64上界，不走当前视图或列表分页；event附实际xmin用于原DML事务对应。
- `_replay`要求root唯一、rev偶数2..62、全部事件连续、offers=rev/2、全terminal/无receipt、后五表空，精确OFFER/REOFFER与DECLINE/WITHDRAW交替；原payload/fingerprint/historical五字段fence精确重建；无handoff/未知extras。
- positive marker精确等于每个业务event的3项原DML顺序、table/op/recordid/xmin事务，epoch=3*rev；删除ABA/事件UPDATE/额外mutation不能被当前空表掩盖。普通SQL未解释marker增长fail-closed。
- 旧P1/P2真VERIFY/material proof与六目标/P1–P5绑定保留，当前target反复原reader/sourcelease复核；旧完整五VERIFY分支和原KNOWN_NOT_STARTED仍独立。
- record_consumption前重建资格+snapshot hash；原parent UPDATE和dispatch writer同锁；最后仍重建live资格。deferred约束关联原SQL immutable link/receipt/approval，资源/批准/anchor失败都应同事务回滚（实际并发与rollback未运行）。
- historical仅从不可变专用snapshot重放原事实，并验证当前marker完整prefix，重建结果与原q严格相等；后续合法新REOFFER/ACCEPT不会因live业务表新增抹原COMMITTED。现current协议catalog连续性仍要求未破坏；不声称通用迁移/重启/owner不可见DDL保护。

## 必须准确声明的范围与待验证

原fence固定该旧plan的P2 VERIFY revision；所有offer材料也固定该原P2材料版本。因此有其它中途plan协调/重复VERIFY或材料变动历史可保守UNKNOWN拒，不应宣传支持任意历史P3闭合。原tail协调活动一律拒；大于62根revision预算拒，不能为new ADOPT归零或扩64上限。

历史决定actor按原reviewer/executor、原精确事件/请求证明重建。指纹不是独立加密签名；受信应用事务与issued-owner连续性仍是原信任边界，不能把允许owner任意手造整套合法DML/事件当已抵抗的外部攻击。

source-v2冻结前优先核native假锚negative、OFFERED拒绝、ACCEPT先赢/commit先赢、REOFFER/withdraw迟到、完整多代DECLINE/WITHDRAW、资源后半失败回滚、newACCEPT后coldGET；历史raw-null/profile strip/downgrade拒绝；原zero/完整5profile独立回归。全部需真实完整窗口，不迁私有分数。既有Windows/正式AT/真实模型/生产等NOT_RUN保留。
