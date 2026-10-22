# NO_MODEL 四步骤来源变更与重新批准：限定交付

冻结源码 `24d59c4bd668e258a819b2f62d707242e38851a8`，远端父基线 `6c7b57fd13b48fc2bd0f118381c61e9e77c6b451`。对应原 F2-T03/T05，仅 CURRENT_OWNER / LOCAL / SYNTHETIC，未连接外部正式来源。

首次 ADOPT 前，服务端对实际选定的完整步骤封存独立版本的“差异观察基线”，包含原 Case/Run、材料/目录、精确步骤合同、有限来源、八表无业务记录核明及来源 epoch；原 candidate 消费与初始 ADOPT 再绑定计划、步骤 ID、原依赖快照与基线。权限缺失、未知或损坏不会当成空记录。记录、producer、validator 与图各有严格版本，旧 V1 历史沿原哈希，不在读取时补录。

观察只供比较来源差异，**不充作 VERIFY，不写 verified_sources，不改变 PENDING**。已核验 P1/P2 继续以原 VERIFY 事件为准。后来明确来源 ADOPT 可更新差异值，但不会洗掉尾步仍依赖原观察的资格限制；每次实际写前仍核全部计划代次和八表未开始、动态权限、epoch、锁、传播与事务最终检查。新图只映射既有 ordinary CaseStep 的精确未开始来源，其他 scope 与未知字段继续拒绝。初始及后续历史只用原事件前缀重建，不借当前 bridge、catalog 或业务表回填。

实际最终窗口 **30 PASS / 0 FAIL / 0 ERROR / 0 SKIP，JUnit 121.673 秒（pytest 121.68 秒），exit 0**，17 份源码/测试/目录文件与冻结 blob 一致且窗口内未变。新模块16项，另原 NO_MODEL 完整链/冻结 producer/权限、旧图历史、原来源 ABA 及两种漏模式冷读，共14项；不与早期39P或上一片171P累计。

真实回环 HTTP / PostgreSQL 从新 Run、独立 worker、原材料 REVIEW/CONFIRM 开始：两项目标实际生成原固定 **P1–P4** 候选→首次 ADOPT→P1/P2办理及首次 LOCAL 批准交付→实际新增合成资源及其 grants→明确局部 ADOPT→新 HELD 资源明确 PROPOSE/APPROVE→关联 revision2、资源确认与一次 CONSUME 同事务。此时 P3/P4 仍 PENDING、无 VERIFY；两代资源占用、原消费历史、P1/手工锁和原回执保留。原键 GET 恢复与新 Store 冷读均真实调用，未冒称网络故障注入。其后另行实际 OFFER/ACCEPT、P3 VERIFY、SUBMIT/ACKNOWLEDGE、P4 VERIFY，冷 Store 仍可恢复两代旧资源回执，不因后来业务污染历史证明。

[actual-no-model-chain.json](actual-no-model-chain.json) 保留精确 UUID、原基线/seal及两代回执；[final.xml](final.xml) / [final.log](final.log) 为最终窗口。原网页 NodeVM 使用完整已发 HTML、既有 fake DOM 和实际 API preview/plan响应，核新图显示/采纳预览及非法版本、来源、candidate、scope、facet错配；[original-page-schema2.log](original-page-schema2.log) 记录19项断言，**不是浏览器验收**，oracle无业务写请求。

反例包括跨 Case candidate、改/删 seal与基线来源、严格版本/producer、旧缺基线不回填、初始与来源 ADOPT 的撤权 ABA、初始及来源保存后异常事务回滚与原键重试、第二次 ADOPT 在真实 OFFER/P3 BEGIN 后拒绝。旧代次 BEGIN、未知数据库权限和精确来源形态为明确标注的纯单元控制；不冒称新的权限环境验收。旧漏 mode 的 New Store/configured_app仍拒绝新写、恢复原回执。

失败原件和因果均保留，各窗口不累计：first 0P1F（V2目标结果 producer消费者漏接）；targeted 7P4F（P3/P4来源字段未映射及ABA错误类型）；graph-diagnosis 0P1F；graph-v2 11P；boundary 39P；final-branches 2P；page-consumer 1P。最终首次调用误将 basetemp放工作区，原系统临时目录门在session PG setup拒绝：3P27ERROR，27项业务未执行；未改产品保护，恢复原系统临时目录后本次30P。该失败目录已无 postmaster.pid；未删除未知锁或进程。

`validation.json` 列各窗口、实际模块、源码绑定、原件/公开副本哈希与脱敏次数。私有原件保存在指定环境 scratch，成功链原件另保全至 actual-private；失败 traceback 的临时 fixture session及截断前缀已在公开副本脱敏，非逐字原件时明确列原件血缘。`checksums.sha256` 覆盖全部公开证据。

精确 collection：9478 cases /401 files，S1–S4=2393/2310/2435/2340，稳定 case-key多重集完全相等，696份 raw fingerprint绑定冻结源码；五份原 collection JSON在ZIP无损保留。catalog 3601 AST ID /462141字节，既有4096/524288上限未变。**collection不是测试执行、Windows或浏览器通过。**

本片未跑真实浏览器、安装 wheel、新CI、P5/TXT或正式AT35，不转签旧run12；未开放已开始业务迁移、计划替换或自动批准。普通外部五证明仍缺实际外部合同/样本；Windows owner/DACL/原生迁移及真实模型/整体验收继续未验。上一片171P的等价正常发布状态已在其README和publication-completed.json修正，原历史PENDING回执保留。

源码等价发布映射：原受测 `24d59c4bd668e258a819b2f62d707242e38851a8` → GitHub 源码对象 `6b61be4ec3df34ce5aaca51b37004e9bb686165c`，整树均 `15feb1e0a898c4170ec59d76d888ab41687303d6`。既有连接不能设原author/date，未冒称原SHA上传；30P属于原24d整树，元数据等价未重跑。[publication-map.json](publication-map.json) 保留源对象创建阶段原回执；最终分支正常快进及完整证据HEAD由最终回读回执另列。[独审记录](independent-review.json) 是内部限定只读复核，不是外部业务来源证明。
