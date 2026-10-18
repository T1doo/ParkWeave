# F3-T03 有界类型依赖图内核合同

基线 `a56ecc0ac12af80f69811edc66dd4808956d376e`；依据原产品设计 §8、F3-T03 和 AT25/26。本片补显式图的只读计算，不更换原 P1–P5、schema1/2 编译器或历史 hash，不接 ADOPT、发布、迁移、执行或 authority。

新合同 `parkweave.dependency-graph/1`：同一 graph_id、park/org/package 范围，递增 revision；节点有稳定 ID、原12类 type、case_id（共享来源可为空）、revision_sha256、source_kind、锁字段及可选有界集合。边有稳定 ID、上游/下游、原7类 kind、来源和 CONFIRMED/CANDIDATE；可带独立稳定 observation ID、版本和 known。集合成员 ID/版本排序纳入快照 hash，增删均为变化。节点类型/Case、边端点/类型不能借同 ID 重绑。

节点最多128，边256，集合成员合计512，单集合256，显式未知范围32；ID最多80字符、锁字段每节点16项。每个快照有规范化 SHA256，顺序无关；拒绝悬空、环（含候选边）、重复 ID/关系、非法范围和越界。图只能含同一 park/org/package；跨Case边必须显式提供。未知范围明确为 NODES、CASES 或 PACKAGE，不自动发现关系。只验证这些声明的结构和一致性，不声称验证来源真实性或完整性。

比较两个有效快照：内容或集合变化、新增/删除节点和边均触发重验，沿两版声明边取保守并集，保留每个目标/确定性的一个规范路径见证（不是所有因果路径）。所有确认的有类型边均参与多跳；候选边、SEMANTIC、MODEL_CANDIDATE/未核实来源和未知 observation 只能扩大 uncertain，不能升级为已确认事实。SEMANTIC 或 MODEL_CANDIDATE 的 CONFIRMED 边直接拒绝。集合不完整及显式未知范围即使未变也要求重验。

definite 和 uncertain 可重叠，affected 为并集（含删除节点）；preserved 仅是当前图中不在并集的节点，不代表事实有效。删除节点另列 removed。锁冲突取受影响节点前后锁字段并集，不改正文、不解锁、不输出可写补丁。结果始终 read_only、can_adopt=false、execution_authorized=false、authority_verified=false。

共享来源按各消费边的 observation 比较。仅来源节点自身 revision 变化而该消费 observation 完全未变且 known 时，不把其他消费者历史误作变化；observation 自身变化仍直接触发对应消费者。真正由别的依赖传播到节点后继续沿其下游传播，不用未变 observation 截断多跳。原 schema2 图可只读转为 before/current 新快照，必须核原 hash、逐 observation 绑定及原 affected/preserved；保留原图 hash 引用，不重签或重写旧历史。

observation ID 不能跨源或消费边重绑；source_kind 变化参与影响判断，同一边在两版中的确定性不同时保留两版路径见证。旧schema2解析固定原作用域，不调用当前编译器重新生成历史。本片不执行适用日期或来源事实验证，不以声明的 COMPILED/HUMAN_CONFIRMED 推导真实权威。

独立字面 oracle 覆盖链、分叉、汇合、多跳各类型边、候选和未知范围、锁、集合增删、scope、环/悬空/重复/界限、输入不变及旧图兼容。仅定向核验新内核和必要旧图纯计算，不运行数据库、浏览器、真实模型或普通发行分支；所有分窗和失败分别保留。只称 F3-T03 工程子集，整体 AT25/26 不签收。
