# 受控合成停表与AT33证据补正

开发分支`dev/f2-synthetic-handling-pause-20261018`，基线`a8fef37edee329b3ef51cb5f8026498fc668785b`；最终受测源码`efd9103ff4a4f4c12b52790052893b533579384b`。交付提交仅另加报告/证据和审计输入格式补正，功能源码、测试、合同与受测SHA一致。

## 实现与权限边界

沿[先行合同](SyntheticPauseClockContract-20261018.md)实现独立`/api/preparations/{id}/synthetic-pause-clock` GET/POST。宿主须明确提供原签发的临时SYNTHETIC数据库证明、原IsolatedDeadlineSources、同Store及既有受派reviewer的有界能力，期限不超过24小时；普通启动不加载，不使用IsolatedPlanApproval批准。仅固定合成理由、显式PAUSE/RESUME，锁后服务器UTC、当前READ/REVIEW_ASSIGNED、原绑定/版本/指纹、连续revision、原key/fp均核对。GET按原key只读恢复；NOT_OBSERVED不证明迟到写不存在，不自动重发。

复用原工作日历/source校验和工作窗遍历，扣除受控半开暂停区间；没有重写规划/ADOPT、资源或Case/Run算法。开放暂停只计算过去工作秒，不猜恢复时刻或截止；恢复后未来日历不足可准确UNKNOWN。每读同时检查结构/hash链、原请求fp、历史PAUSE当时未完成目标和事件时序。显式启用的同事项在原只读接口准确UNKNOWN，避免显示未扣停表的旧截止；同registry换Store也不回退。

独立SQLite日志仅由明确拥有证明的构造器新建，拒绝已有路径/换文件/schema变化，不修旧日志。最多16事项、每项32事件，UPDATE/DELETE触发器拒绝；日志不存token/来源正文/材料。PG身份/父事项锁贯穿SQLite提交，SQLite锁后及追加前重新验权/时刻/来源。应用目录只有SELECT，未增加UPDATE或FOR SHARE权限；目录xmin重核不等于阻止owner绕业务锁并发改目录，也不声称PG/SQLite分布式原子提交。提交后丢响应可能已有事件，只读核原key。新API进程不续权、PG实例重启旧证明拒绝，日志仅保留证据。

本片没有业务PG DML/DDL、真实身份/Grant/分派/目录发布/批准/凭据，也没有真实停表UI或普通provider加载器。测试复用原临时数据库/身份/授权fixture；它们不是正式来源。原raw.pauses拒绝和普通permit/writer默认拒绝保持。恢复既有权限不延长原fixture能力期限。

## 实际测试及独审

| 窗口 | 结果和实际范围 |
|---|---|
| 初开发 | 7 PASS / 14 FAIL，JUnit36.134秒；14失败均在UUID nonce元数据序列化，未执行停表写入。 |
| 修序列化后开发 | 7 PASS / 1 FAIL，JUnit4.894秒，`-x`停止；应用角色无目录FOR SHARE权限。去掉额外锁要求，保留原SELECT/xmin复核，没有增加SQL权限。 |
| 权限修正开发 | 21 PASS，JUnit34.358秒。另单独源盲字面节点1 PASS，JUnit0.538秒；均非最终冻结成绩。 |
| 冻结`3b96be01f6a4cbee214d91f2b28869ef7d543d2e` | 83 PASS / 0 F/E/S，JUnit52.797秒；814输入四图一致、107记录模块均来自私有镜像。独审随后找到3个P2，因此该窗成功不代表无缺陷。 |
| 独审修补开发 | 回退6 PASS/JUnit6.702秒；投影6 PASS/JUnit9.944秒；长暂停恢复1 PASS/JUnit4.095秒。与其它窗重叠，分别保留。 |
| 最终冻结`efd9103ff4a4f4c12b52790052893b533579384b` | **92 PASS / 0 F/E/S**，JUnit59.304秒：新片35、原只读兼容57。814输入在共享目录/私有镜像运行前后四图相等；107个记录的产品/测试等模块全部来自镜像。没有运行全仓、原整项runner、B/C或旧风险窗口。 |
| 独立复核 | 先冻10条源盲oracle；仅静读明确SHA，不import产品，不执行DB/HTTP/锁/浏览器/模型或测试。3b96的3个P2已在最终efd静态复核闭合，无开放P1/P2，记录另见证据，静态项不计动态PASS。 |

最终动态包括实际HTTP/原拥有PG上的暂停、冻结已用秒、恢复、同key回读/异fp拒绝、并发PAUSE一成功一拒绝、当前撤权/错scope/绑定变化/到期拒绝、日志篡改拒绝及原只读兼容。14张原业务/权限快照表行值一致；日志是唯一新增持久写入。时钟回退和长暂停的三个HTTP节点使用**显式隔离观测FAULT**，仅包装本片fixture的观测返回，不调整真实系统/PG时钟；不得当作真实环境时钟故障实测。其它字面日历/历史合法性例是纯计算节点。没有独立动态测试。

3个独审P2已逐项修补并保留旧报告：时钟回退可能写逆序RESUME；开放暂停因未来工作窗不足丢elapsed并阻止恢复；hash链正确却在目标完成后才PAUSE的历史未拒绝。修补分别是全事件与当前观察时序检查、原遍历的private elapsed-only路径、逐历史PAUSE的未完成目标重核。原公开calculate合同与缺源UNKNOWN规则保持；没有编造未来日历或恢复时间。

[最终JUnit](evidence/synthetic-pause-clock-20261018/frozen-efd9103f/results.xml)、[实际HTTP事件](evidence/synthetic-pause-clock-20261018/frozen-efd9103f/actual-http-outcome.json)、[根核对](evidence/synthetic-pause-clock-20261018/root-verification.json)、[最终静态独审](evidence/synthetic-pause-clock-20261018/independent-final-review.txt)、[公开文件配对清单](evidence/synthetic-pause-clock-20261018/publication-files.json)。

各窗按原节点和SHA保留，**不相加**为新增测试数。失败日志、JUnit、控制器、四图、原origin、实际HTTP事件/只读恢复及一份实际日志均有hash配对；失败堆栈中fixture会话字典显示值作公开脱敏，私有原件不变。两个冻结窗共捕获306个实际fixture会话值，仅用于逐值扫描，私有值文件不公开。69份raw/public配对中65份字节相同，4份只脱敏失败堆栈fixture会话字典显示；另2份发布元数据，共71公开文件。43字符形状的4种候选均核为静态属性或原测试文件名，无未知项。原日志/JUnit/stdout的180处空白告警保留，不修剪原件。开发旧失败窗未捕获全部实际会话值，不声称对它们作同等逐值扫描。

## AT33只读补正

原42项盘点漏引[PreviewRulesChangeDelivery-20261014](PreviewRulesChangeDelivery-20261014.md)，不能泛称第二园区B/C没有回执。已对照原export-index和原文件：历史`5e339a247e33d1a4b6cb4c106e54af1ea22b5439`的根659与独立481两个旧窗口均有第二园区B三态及C实际revision节点PASS；本次B/C动态**0**，不将历史数字相加、算新增或迁签当前SHA。

B已有三态、3 Mock角色/3 scoped Mock permit、2发布版本/2绑定epoch。C已有同资源替代时间、revision1→2/buffer300→360、原局部ADOPT及P2–P5重核，保全P1、A历史和旧占用；实际outcome记录0新runtimeGrant/0真实模型。原报告另有6产品文件+643/−17、11新增测试文件、1旧harness修复等成本，不能改写成当前新增成本。两个原JUnit及实际outcome字节均匹配原索引sha；旧风险/失败证据及旧canonical未改。

[42项审计JSON](FixedAcceptanceCloseout-20261018.json)只更正证据映射/当前余项；原36AT+6EX规格及bindings状态不变，正式均NOT_RUN。旧56份输入保留，新补8份按原`bytes/sha256`结构记录，64份实际字节核对一致。完整正式AT33及当前SHA的B/C未复跑，没有重做业务B/C或迁移loader。

## 尚缺的真实输入与未验范围

真实停表仅在其既有来源/政策、工作日历/业务时区/起算及目标、允许的现有主体/理由/适用事项、结束及撤销语义明确后续接，不能从READ/REVIEW推出停表权。该缺口只阻塞对应真实样例，不阻塞其他合成开发；无需为本片新建真实Grant或信任根。普通已有preparation续接仍需真实合法PREPARE/REVIEW_ASSIGNED、preparation_catalog及相应来源修订/预检/采纳接口输入，configured_app provider缺口未因fixture补齐。

未验真实干净Windows11、安装PG/test-owner及已审native创建回执/ACL条件，未验Windows正式AT、真实业务停表或正式AT29/33。未调用真实模型，未做LIVE公平对照/真实规则效果；C0官方模板、准确截止/时区、双赛道边界及视频/QR访问和上传回执仍需实际材料。旧平台风险窗口与HTTP UNKNOWN_OPEN没有重试或关闭。项目未完成。

完整交付SHA、远端0/0和main/旧refs未变以本轮Git回执为准；只推正常开发分支，不改main、不强推、不部署或增加费用/安全网络权限。
