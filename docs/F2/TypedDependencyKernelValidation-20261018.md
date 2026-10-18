# F3-T03 显式有类型依赖图工程子集

基线 `a56ecc0ac12af80f69811edc66dd4808956d376e`；最终受测源码/合同/测试冻结 `26e329aca1353de35edb0b48e7c082462ef6de08`，分支 `dev/f3-typed-dependency-kernel-20261018`。原依据为产品设计 §8、F3-T03、AT25/26。[冻结合同](TypedDependencyKernelContract-20261018.md)限定本片，不签整体 AT25/26；42项原状态不改。

## 实际实现

新增 `parkweave.dependency_graph` 的 `snapshot(raw)`、`preview(before,current)` 和 `from_unified_v1(old_schema2)`。这是可直接调用的纯计算内核，无数据库/文件读取、自动关系发现、HTTP挂载或页面写入口。原 `registered_dependencies.py`、`typed_source_impact.py`、`unified_dependency_propagation.py`、采纳与历史验证代码字节保持；不更换原P1–P5或重做既有共享反查。

显式有界节点/边支持原12类节点及7类边，按版本/稳定身份/scope/集合成员指纹比较，经有类型边多跳计算确定和不确定影响；不是把类型显示后再套固定步骤闭包。候选、SEMANTIC、未核实来源、未知 observation、集合不完整及明确的NODES/CASES/PACKAGE未知范围保守扩大重验。definite/uncertain允许重叠；affected为并集，preserved只是当前图未受本次影响的节点，删除节点及前后锁字段并集单列。结果总是只读且不可采纳/执行，不验证事实或权威，也不执行适用日期核验。

逐消费observation阻止共享来源自身变化误伤未变化消费者；真正从别的依赖到达该节点的影响仍沿下游传播。旧schema2仅作只读转换，逐observation绑定及核对原affected/preserved，保存原图hash，不重编或重签旧历史。旧图没有的新字段（如锁字段）不从当前Case猜补，转换不证明这些字段完整。

调用顺序为：按合同提供显式 `raw` 图 → `before = snapshot(raw)` → 用新revision及明确变化生成 `current = snapshot(new_raw)` → `preview(before,current)`。来源声明只描述调用者给出的关系；即使写COMPILED/HUMAN_CONFIRMED也不产生真实批准。节点类型/Case及边端点/类型/observation身份不得借稳定ID重绑，变化必须明确新身份。

## 原件分窗与独审

| 源码/窗口 | 实际结果 | 来源与统计限制 |
|---|---|---|
| 根初版 `9c08f07677c7c29e20d322fa1b55f97af2c41e0e` | 84唯一PASS，pytest1.33秒，outer3.954596144秒 | 772输入shared/mirror PRE/POST零漂移；不是最终88或独审结果。 |
| 独审首次运行配置窗 | 52节点，51PASS/1FAIL | 外部测试路径选到共享pyproject，模块来源未全命中私有镜像，不签冻结来源；原件保留。 |
| 独审初版有效私有镜像窗 | 53唯一：51PASS/2FAIL，0ERROR/SKIP | 772 mirror PRE/POST零漂移，shared POST匹配冻结，20本地模块origin/hash命中镜像；两项真实P2如下。 |
| 根最终 `26e329aca1353de35edb0b48e7c082462ef6de08` | 88唯一PASS，pytest3.88秒，outer7.787380891秒 | 772 shared/mirror PRE/POST零漂移；25个记录模块命中镜像，范围为parkweave及新测试模块，传递导入的旧测试helper未单独仪表。 |
| 独审最终同SHA私有镜像 | 141唯一PASS＝根88＋自有53，0FAIL/ERROR/SKIP，pytest2.10秒 | 主88与根最终88完全重叠；自有53与有效红窗53重叠。772 mirror PRE/POST零漂移，shared仅保存POST并匹配冻结输入，不能写成shared PRE/POST；29本地模块origin/hash命中镜像。 |

最终主/独实际ID并集141，交集88；不是88+141项新成绩，更不是全仓。53条自有pytest节点、25个独立设计场景/30项拒绝边界合同和新增功能数是不同口径。所有窗口仅纯计算，未请求PG、HTTP或浏览器fixture。根两窗各1条原FastAPI/Starlette弃用warning保留。

独立自有测试在私有外部路径，53个实际nodeid以 `::` 起始，collection另存真实path；逐条call及JUnit名称精确核对，不补造文件前缀或归一化nodeid。其测试字节另行封存；29项来源记录指镜像内项目模块。前述共享PRE/POST不完整的独审限制保留。

独审字面oracle在审实现前已冻结，原SHA256为 `dca269c3706f1459dedd33058490ba21bcf72f0907dae3717e5a684101cc1be6`。主oracle覆盖链/分叉/汇合、每类边多跳、候选、未知范围、两版增删、锁、集合、scope与边界及24个旧schema2转换场景；独审另验来源类别转变的准确版本路径、旧scope/compiler变化等。

真实P2及修补：第一项为去重只看edge hash，丢掉来源类别跨版本变化产生的另一确定性；现将有效确定性纳入去重，保留原/current图各自路径见证。第二项为旧schema2转换读当前SCOPE；现固定原 `BOUNDED_MULTI_SOURCE_V1`，不调用当前compiler。根补两向来源变化/精确路径、冻结旧scope/compiler及边数界限回归，最终88已含。独审两项P2在最终窗消除，最终无开放P1/P2；没有改原hash算法或旧依赖模块。

## 交付与未验范围

日志、JUnit、命令、collection、输入hash、模块来源、独审oracle/测试/报告与失败原件见 [本片证据](evidence/typed-dependency-kernel-20261018/validation.json)。公开件与原件配对核hash；不复制整个镜像或venv。交付提交只追加本报告/证据；实际完整交付SHA、远端全部heads差异、main和目标分支0/0另记本地delivery回执，避免预写网络成功。

源码、合同、测试及报告的空白检查通过；全新增证据检查exit2仅因有效红窗原JUnit/stdout中的6处traceback尾空格，按原字节保留，不修剪失败记录。

没有将新图接入ADOPT、发布、迁移、执行、生产authority或正式来源接线；没有新凭据/权限/费用、真实模型、root/seal/发行重试、main修改/强推或部署。该内核只处理显式版本关系，不证明图完整、一般语义理解、动态发现或现实业务有效。Windows正式AT、真实来源/园区业务及整体AT25/26仍未验，项目未完成。
