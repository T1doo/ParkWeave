# AT21 准备度三值：有限合成用例回执

固定 AT-21 本次有限合成实例 **PASS**，覆盖原三条 oracle：独立三值表一致、无证据不通过、界面／输出不冒称官方审批结论。受测冻结 **`ee9b2056a16988609b311b58955a5c788ee2fef0`**，基线 `2fa14ffd2af776a536d826e4ce9c5d2e6a790a04`，分支 `dev/f3-at21-synthetic-readiness-20261018`。生产 src tree `9b21f97b8e25fd9a589e41bb9a3068d7943e0734` 与基线完全相同；domain 和 synthetic_rule_readiness 也与原 `5e339a247e33d1a4b6cb4c106e54af1ea22b5439` 字节相同。本片只补测试观察、旧测试替身能力和回执，不重写算法或新增合同框架。

[实例回执](evidence/at21-synthetic-readiness-20261018/runtime/AT21-case-receipt.json)保留固定定义、初态／预算／重置说明、三项判断和限制；固定规格及42项绑定模板仍 NOT_RUN，未将此实例回填成通用 runner 或全项目通过。项目仍 IN_PROGRESS。

## 原 oracle 的实际证据

| Oracle | 实际观察 | 结论与边界 |
| --- | --- | --- |
| 三值结果符合独立真值表 | 复用原 foundation 字面 AND／OR 表，9对输入分别核两操作，共18格；补经原 `synthetic_rule_readiness.evaluate` AST 的同18格。新期待值与原独立字面表实核相等，未调用生产算法计算期待值。 | PASS，仅所有二元 TRUE／FALSE／UNKNOWN 组合，不推广为任意嵌套或真实政策语义。 |
| 无证据不通过 | 组合表12次缺证据叶均为 UNKNOWN／MISSING_EVIDENCE，evidence=[]。实际缺事实 preparation 的初态 fact_assertions=0／Run assignment=0，原 ASGI 与原页面求值均 UNKNOWN，purpose=NOT_DECLARED。 | PASS。OR(TRUE,UNKNOWN)=TRUE 符合原表，因为另一支有证据；缺证据叶本身始终不变 TRUE，不错误要求整棵表达式均 UNKNOWN。 |
| 不显示官方审批结论 | 原 TRUE 页面节点增强观察；新增 FALSE 和缺证据 UNKNOWN。三态都读取真实 owned PG／ASGI 结果，经完整原 HTML 的原 `loadPreparation` 和读取 handler 渲染。实际结果、来源原因、完整文案同时核，避免只看“资格 UNKNOWN”产生假阳性。 | PASS。三态均显示“资格 UNKNOWN / NOT_EVALUATED”“未经真实性核验”；状态明确“仅开发模拟，SYNTHETIC_REVIEWED不代表正式审核。”后端双层 formal_review/business_publication=false、case_goal_completed=false。 |

[实际执行摘要](evidence/at21-synthetic-readiness-20261018/runtime/actual-execution-summary.json)列18行结果及三态全文／来源。每条 NodeVM 页面链收到9个 ASGI GET 回应、0 POST；这是 Node stdio→TestClient ASGI 桥，**不是真实浏览器或普通网络 API 进程全链**。页面直接调用原 loadPreparation／handler，未验证点击导航、CSS布局或真实浏览器可见性。

SYNTHETIC 来源、原 fixture Run 的 MODEL_MOCK、纯求值 NO_MODEL、原 CandidateEngine 的 mock SAVE／SUBMIT／REVIEW／PUBLISH 及 ASGI／NodeVM 执行类型分列。mock 审核与发布、安装身份／Grant／目录和资料／事实写入均是隔离初态，不能变成正式审批、目录发布或普通批准。真实模型调用0。FALSE 与 UNKNOWN 观察段分别核16类 business、7类 authority 表及独立 journal 字节不变；TRUE 原节点核全部 public 表及原 authority snapshot 不变。初态写入不混成 GET-only；未宣称初始化全过程只读。

## 实际窗口与失败保全

| 窗口 | 实际结果 | 精确范围 |
| --- | --- | --- |
| 首冻结 `db868ac5612b8d3dc84b6ce1dc67a6a9969a9196` | 5唯一：2 PASS／3 FAIL／0 ERROR／0 SKIP，14.350717秒 | 两真值表通过；三页面链均在规则读取前，旧 Element 替身的 classList.remove 缺失失败。 |
| 最终冻结 `ee9b2056a16988609b311b58955a5c788ee2fef0` | **5 PASS／0 FES**，15.397526秒；pytest13.14秒 | 原真值表1＋新 evaluate 表1＋增强原 TRUE1＋新 FALSE／UNKNOWN2；4条原依赖 warning，exit0。 |
| 同冻结独立私有镜像 | **3 PASS／0 FES**，10.876525秒；pytest7.24秒 | 原表、新 evaluate 表、实际 UNKNOWN 页面；逐ID与主5全重叠，不加总。TRUE／FALSE 原输出仅另作静态核对。 |

首窗三个原 TypeError、Node stderr／交通、原 JUnit 与源码冻结保持。[完整原失败](evidence/at21-synthetic-readiness-20261018/runtime/first-original-failures.json)。仅从现存 manual_goal_recheck_actual.js 复制完整633字节 stateful classList constructor，SHA256 `476b091342f0a1f144e6ea191b8ba0eb78ea208fd724b97b5d8b7fefe5d42ec6`；原业务／负例／等待预算不变，Node语法检查通过。这是旧测试替身修复，不能称产品算法缺陷，也不能解释此前连接／启动 UNKNOWN。

两根窗及独窗均759输入共享／私有镜像 PRE／POST零漂移；根、独各84个实际 pytest ParkWeave 模块从等字节 mirror/src 导入，in-process ASGI包含其中。主最终观察到的111成功连接均close、0失败；首窗76成功连接均close，3次有界失败采样保留；独观察到的34成功连接均close。自有 Node和pytest已wait结束，PGDATA删除；根两个退出的 postmaster 留有 PPID1 zombie条目，已如实记录且未操作，不能写“无任何进程条目”。原connect2s／DROP statement5000ms／Node桥45s＋wait5s不变，无自动重试。

[独立终审](evidence/at21-synthetic-readiness-20261018/runtime/independent-final-review.json) raw SHA256 `064e82a4dff708df5ad928281fc246812b66ad2b77412c9b70a6903fd1c870f7`，开放P1／P2／阻断0。前置 staged whitespace 检查曾因新测试多一末尾空行exit2；准备脚本曾因Git引用转义中文路径失败、后续freeze缺失，均在pytest前、0tests。原失败脚本和记录保留，后改用NUL路径；这些不混入pytest失败数。归档临时目录收集还曾对0tests的runner调用读取不存在的basetemp而KeyError，原脚本与记录保留；仅为该调用跳过不存在的临时目录收集，原拒绝文件仍归档。

## 原 runner 拒绝与未验项

原 `run_acceptance.py --ids AT-21 --source-head ee9b2056a16988609b311b58955a5c788ee2fef0` 单独执行一次：**exit1／SOURCE_BINDING／GIT_BLOB_UNAVAILABLE，0 tests**，0.387659秒。[原报告](evidence/at21-synthetic-readiness-20261018/runtime/original-runner-report.json)及调用stdout／stderr保留。当前356个根test文件4,444,602字节，超过原4,194,304上限；原cap、绑定算法、全仓／shards行为及消费者未改。上述直接pytest窗口与有限实例回执**不冒充 runner 成功、selected依赖闭包证明或完整回归**。

真实官方规则来源／审核发布、普通正式 provider／批准接线、真实园区资格与效果、真实模型、Windows原生正式AT及真实浏览器均未验。此有限合成 AT21 无需先取得真实来源合同；其他 AT22–35仍按各自适用类型与oracle分别待验，不能从本片推断。没有新增真实身份、Grant、分派、目录发布、批准、凭据、费用、安全网络权限、部署、main或强推操作，也未恢复暂停的Windows创建／ACL工作。

[继承核验](evidence/at21-synthetic-readiness-20261018/runtime/inherited-evidence-proof.json)实核基线33,335个 evidence Git blob原字节零变化，未知锁保持。[归档清单](evidence/at21-synthetic-readiness-20261018/manifest.json)保留新旧窗口与raw/public哈希，归档129对raw/public、25处临时合成会话候选脱敏，13个JUnit标识实例保持；严格JSON／JSONL／XML与SHA／长度检查通过，无PGdata或私有bootstrap导出。普通分支最终交付SHA及实际远端差异由本地 `.runtime/at21-synthetic-readiness-20261018/delivery-and-remote-verification.json` 和最终回报提供，不在本报告预填网络成功。

源码／测试／脚本及本次Markdown的定向diff-check为0；完整暂存检查exit2，仅首窗原pytest失败log/XML的18处尾空白，保留原字节。[交付检查](evidence/at21-synthetic-readiness-20261018/delivery-checks.json)为raw/public配对表之外的衍生metadata；原检查输出在本地runtime保全，未修剪失败日志来消警。
