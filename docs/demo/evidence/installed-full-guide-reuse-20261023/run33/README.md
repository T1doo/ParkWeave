# run33：新实例安装态 LOCAL/NO_MODEL A办理与B独立复用

受测源码 `c83e93dc3bafe55a00f5c2531e8a9e9eedf5002c`，tree `92b43fe8f75c777df07d58805e584a5e22764328`，parent `271d6565a259bfad9ef32b8eadf6c8a8344f9a87`。[官方run33/attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39902843301)，job `120248065681`，唯一有界执行限定 **PASS**，无自动重跑。root invocation `51eed5572b4843ae87f3a63749404b6f`，A/B分别 `d71c1009037f18fdf711000848ff35d4` / `f796f947e19a37b0d443a4ec530ddfe9`；没有恢复run32任何在途操作。源提交仅改新驱动诊断I/O统计和冻结绑定、font/workflow33及3项指纹；产品、tests、旧驱动／监督器未改。

同一新建隔离合成实例，从空业务表开始，原安装态 `/demo` 选择会话文件并显式选人。A原DOM首办→专员REVIEW→企业CONFIRM→NO_MODEL候选ADOPT→P1显式VERIFY→3次资源预览/HELD及LOCAL明确PROPOSE/APPROVE/交付→P2 VERIFY→专员OFFER→执行者ACCEPT→P3 VERIFY→执行者人工SUBMIT→企业ACKNOWLEDGE→P4 VERIFY→原REVALIDATE/LOCAL_RECORD_CLOSED→P5 VERIFY→读取目标／下载TXT。ACK原响应step是LOCAL_ACKNOWLEDGED；5次VERIFY是企业各自明确操作，没有自动VERIFY或用关闭替代VERIFY。

A原Case `841fda14-bc25-44f4-8dd5-b975f9e7927a`、Run `36857351-0efd-44b9-b931-40967b1551e2`、preparation `2eb73939-abbf-48db-9b39-fe8e33aaf2a7`、plan `a6394ef0-b425-4715-88a5-dd28509e9d52`。五步VERIFIED、五目标LOCAL_OUTPUT_VERIFIED；原需求整体Case仍false，资格NOT_EVALUATED／外部NOT_SUBMITTED／线下NO_EVIDENCE。只是当前合成本地产物核验成立，不是实际外部办理成功或正式AT35。

A完整成功、正常关闭原窗口/context和受控Chrome后，根时钟89.979秒才准入B，预留145秒。B是全新390px浏览器段，重新选原会话文件和角色，从空目标材料开始原入口复制A原目录，再新增本次独立诉求；原REVIEW/CONFIRM各有独立key、SQL事件、actor及完整响应一致性。新evidence ID、version1、来源/目标全文hash一致、requires_independent_review=true；Case/Run/preparation/plan/candidate/诉求与A不同。没有继承A核验、分派或回执；B计划P1 PENDING、P2–P5 BLOCKED，目标P1 AWAITING_OWNER_VERIFICATION、其余WAITING_DEPENDENCY，Case仍false。B没有VERIFY／资源／接单／取消等操作。

B原Case `5f491715-e4cc-433a-9300-bf5a71df6297`、Run `72f29ea9-33d7-4706-a67f-cab5f572cc07`、preparation `0fbaf728-260a-47bd-87a7-4bfcb253f45c`、plan `1fed4872-23fc-4a40-8f23-fdde84fb3d46`。B之后切回A仅只读，A完整目标与声明的11项计划字段相同、下载TXT逐字相同、命名SQL投影相同。B新增独立业务行明确排除，不称全DB不变或权限全覆盖；没有重启API/PG、重新setup、续期或补权。

实际39 DOM POST=A30+B9，API准备写入0；其中4无key纯预览、35唯一key写入。39条均有原2xx响应（2×202、13×201、24×200），原请求正文/hash、key、响应及相应方法断言保留。315浏览器GET=296×200+19×403，19次全部fact-clarifications拒绝，未算成功或绕过；另21readiness，总336GET。两段354条浏览器请求的partial均有响应和observer返回，未完成HTTP/诊断动作0；账本每条business_outcome仍为UNKNOWN设计值，不能拿它当服务端成功计数，业务结论来自原响应与明确断言。

两份公开TXT：A `A-local-verified-case.txt` 17104B，SHA256 `682f9e8bcc641350a186675431ffc8c97b7148bcdae7fe86fd324e3210d9da36`；B `B-unfinished-case.txt` 14512B，SHA256 `b1c46fff5edead61b7a240b377698a9915b3453133c6767c4ac42ac24572031f`。B后的A第三次下载仅保留为private文件，结果记录file=null；其完整hash/目标/计划与第一份A相同。共3次实际下载，公开2文件。全TXT按原完整导出白名单验证，source_trace/result/pack完整指纹均核。

4张原PNG在内部artifact.zip：01LOCAL批准，02SUBMIT后待ACK时点，03A1200px已核验目标上段，04B390px未完成目标上段。作者和独审逐张亲看。03/04不展示全部5卡/TXT全文，04也不是复用事件图；对应完整事实另据JSON、SQL及TXT，不借裁图代签整页或所有中文码点。当前可见中文可读、警示和disabled门保留。

实际A浏览器段78.793秒，B37.647秒，根工作含清理128.424秒、附件扫描128.531秒。270工作／360发布／每段原90/85秒／原15/30秒等待／job10分钟／依赖3分钟、40POST/400GET/2业务worker均未扩。A已返回写入1663次、失败0，总save3.043267秒、已知成功fsync0.973021秒、最大save0.051990秒；B756次、失败0，分别1.011890秒／0.407629秒／0.006490秒。均在原钟内，未扣除预算。partial只描述当前写之前的1662/755次，明确一次延迟；final分phase摘要在最后写返回后记录完整累计，无追写。未完成I/O与失败写入未返回的fsync子时长不可解释为零；本次成功不能解释[run32](../run32/README.md)旧超时原因或补回其未知计数。

两段partial均COMPLETE/PASS、worker_final=true，seq1663/756；最后完成CLOSE，无在途动作／checkpoint错误。源码/run/phase/invocation/序号/hash与原最终报告通过一致性门。两段各7自有绑定进程全部退出，worker0、scope完整、无清理信号／错误；两个业务worker exit0。API/PG/wrapper exit0、监听REFUSED、两个context及原窗口/浏览器均关闭，cleanup_errors空。只一代API/PG，不是冷启。自有临时目录保留，未证明或声称目录删除。

wheel 1010975B，SHA256 `b8fcc1794d7f084e90ba10415f8ab8ebc44211daaae5ea83f80216456965fa98`；191包文件与受测Git及安装manifest逐字一致，setup/API/两个worker各有前后隔离证明，无工作树/PYTHONPATH回退。wheel构建/安装零依赖下载；hosted bootstrap沿现有锁依赖与已批准固定官方Noto/OFL另列，字体二进制未进附件。17项本地离线检查仅针对诊断、I/O与绑定，不是额外CI或浏览器成绩；761原始指纹不是tests，未重复collection/大套件。

终态联合result PASS、官方job/allsteps success及worker/supervisor exit0；stdout PENDING_FINALIZATION仅观察值，规范化去最终扫描字段后与result逐字结构一致。summary正文未独立读取，完整日志无upload aborted标记，不冒称正文独验。只有一次attempt1，没有放宽断言、补ACK、补权、真实模型或新执行窗口。

[完整官方日志](ci-original.log)1619450字符／1680962B，SHA256 `6cde347bee2947dc16b7bfd43e20846ba0b3ac2e8de14cffe885583c7185b10b`，API原工具全文36段存盘回读逐字一致，独审另取全文核一致。官方ZIP1827865B、9成员展开3246763B，SHA256 `b5da44539f99be7c8bfc01024ff845f2946149574cc57e2887a4d5a1bf7a42c2`，小于原10文件8MiB界。外层[证据ZIP](evidence.zip) 2152486B，SHA256 `32bb21bf3830dcc11774f1af09fe775cf04b0ed3be35ad4842b7fb000f7babf1`，保留未改官方ZIP、同份全文日志、三API、冻结驱动／发布映射／离线检查／实际独审／visual-review／安装核验／账本与原件核对／checksums。解压后运行`python verify_run33.py`仅离线校验原件，不运行frozen-driver或候选脚本。初次原件核对把同路径无key预览当唯一而拒绝歧义，后加原body_sha256精确关联；原运行数据未改，非CI失败或新CI。

原run32 FAIL及实际未知保留。当前只签安装态合成LOCAL/NO_MODEL A本地产物链、B独立复制与审核采纳、A命名投影保全；不签完整原需求履约、B全部办理、正式source、LIVE、正式AT35、Windows/native、PG冷启、全DB/全像素或C0。
