# 企业事项业务进度总览

源码冻结 **e2abaa674b3fefa0dc2423961b4d8303bd752e1d**，独立分支 `dev/f2-owner-case-worklist-20261013`，基于bdcb66bc53415bcf1427e1ab14ecaf8f6eff6e22。根为唯一源码/Git写入者，独审仅写私有测试证据。交付HEAD随后只增加本报告与安全证据，完整SHA及远端一致性由交付响应给出。

原第一版产品§5.6要求展示已采集状态、阻塞原因和回执情况，F2-T04/T07要求可实际办理的协同与工作区路径。已有`/api/runs`只列技术Run状态，`preparation.personal_tasks`仅覆盖未确认资料；确认后的分派、接单、回执和撤销需逐事项查找。本片在原协同工作区增加“我的事项办理进度”，以新只读`GET /api/cases/worklist`分页展示本人有权合成事项的已保存环节、等待角色及原办理入口。未准备、补正、待本人确认、未分派、待接单、分派拒绝/撤回、待回执、回执补正/核对、本地核对、来源变化、本地关闭、撤销及结果核对均保留各自含义。

它整理**录得状态**，不证明材料当前真实有效、资格、业务目标或线下履约。取消优先于其他历史状态，并明确资源释放须原有权角色独立核对；不推定容量已经释放。未知/损坏当前回执绑定为UNKNOWN，只打开原运行记录；当前offer选择其回执世代，多行/非法legacy绑定不会误称待首次分派。最终动作仍由原API重核身份、版本和来源，本入口不提交业务命令、不存正文/token、不自动POST/通知或恢复。

当前READ和PREPARE、enterprise owner、园区/企业及Run/Case绑定均由后端重核。身份锁等待使用READ COMMITTED，已提交撤权重新读取；全部业务元数据来自单条SELECT快照，事务READ ONLY，不调用会隐式失效写的计划读取。最多50项/页，页面20项，UUID游标，无全局总量/完整性或真实SLA推断。页面以textContent呈现原诉求，拒绝错误scope/ID/目标/完成宣称；身份、工作区、运行变化清旧队列，迟到成功/错误和A→B→A均不回写。403强制清私有视图但保留原恢复句柄；原入口GET成功且身份/页面仍当前才滚到对应办理区。

根最终实际相关 **365 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，106.38秒**，包括新38项（含真实owned PG/进程内ASGI、纯单元与离线NodeVM）及原准备、分派、回执、撤销、运行目录、离线页面和诊断兼容；并非全仓或原AT签收。实际业务路径按原命令经补件、独立REVIEW、企业CONFIRM、OFFER/DECLINE/REOFFER、本人ACCEPT、SUBMIT/补正/再SUBMIT/ACK更新队列，原事务快照确认所有成功队列GET无业务写，冷Store/分页/跨租户/撤权和原响应进入实际页面代码均验证。NodeVM执行真实工作队列JS，DOM/fetch及原导航函数为离线double，不能替代浏览器。

独立最终 **2 PG PASS**（撤权与身份锁竞争、非法legacy owner绑定）及 **10 Node checks PASS**（五原导航与滚动、强制403清理、迟到错误/成功、ABA、完成宣称拒绝），分别记录、不合并。旧独立1PASS撤权复验与最终2PG重叠，旧9Node窗保留。导航前根365PASS/111.23秒及此前13/13/34窗各属当时源码，保留且不与最终累加。现有合成fixture初始化沿原机制，产品没有新Grant、权限文件、模型或发布主体改动。

独审原撤权竞争反例 **1 FAIL** 原样留私有runtime；已修旧快照、未决资料阻止403清理、迟到导航错误、非法legacy误投影四项问题。独审脚手架的ImportError、错误整数列注入和注释截取SyntaxError均保留，区别于产品FAIL。含fixture会话repr的四件FAIL日志/XML只公开明确标记的SANITIZED_EXPORT，原件不修改、不进Git；仅移除识别出的凭据repr记录，原/导出bytes与SHA、XML结果、失败断言和正文保留。其他经审安全文件逐字节复制。安全检查是对观察到的fixture repr与Bearer字面值的有界检查，不声称通用秘密证明。

证据位于 `docs/F2/evidence/owner-case-worklist-20261013/`，包含当前/历史窗口、限定独审、原哈希、导出分类和冻结证明；最终归档收尾审查仅runtime、不递归归档。源码差异检查PASS。归档暂存diff --check实际FAIL/rc2，仅legacy脚手架失败的两份脱敏日志/XML共六处原pytest尾空白；格式保留、不裁剪，原检查输出留runtime，不改写为PASS。

两个安全approval仍false/null/null，未创建/运行准备探针或新执行branch。原安全实测1PASS/1FAIL/19NOT_RUN和未知根因不变。历史Chromium data导航ERR_BLOCKED_BY_ADMINISTRATOR保留，不启动浏览器或换工具重试；本片真实浏览器/布局、系统安全环境、Windows、真实模型/正式ServiceRelease/现实履约和完整F1–F3/C0仍NOT RUN或未签收。不部署、不改main或原dev主线、不强推、不配置凭据/网络/系统权限。下一步由父级复核新业务交付；本片完成不解除这些独立门。
