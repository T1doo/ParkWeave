# 普通事项零回执交接：有限交付

源码 `b56c53720332e14c043c6b5580de049bfe361bad`，接续 `2c74bf70e1f7b03b01cd636f212f6945cae64f3f`，正常开发分支 `dev/ordinary-pending-handoff-20261020`。原远端基线 `32f4e356c4b3ffa19a4b41d0570732420c7d951e` 为祖先，根为唯一仓库写入者，独审只读源码；不改main、不强推。

原 V1 产品§5.5、F2-T04/T07要求专员说明原因调整执行方。本片关闭普通 CURRENT_PREPARATION 的一个实际断点：A已接单但从无提交回执时，专员先明确撤回，再由原表单另选已有合法B；B本人接单创建新UUID步骤后才能人工回执、由企业核对。旧邀请、ACCEPT/CREATE和步骤不改写，旧A不能作用于新代次；不授予Run权限、不续首次300秒截止。全部历史步骤逐一证明唯一CREATE、零结果并精确匹配已撤回邀请；有过任何提交/补正/重开、孤儿、损坏或未知历史均拒绝。默认/legacy/隔离/demo范围保持。实施前边界见[合同](OrdinaryPendingReceiptHandoffContract-20261020.md)。

冻结源码实测五完整相关模块 **152 PASS / 0 FAIL / 0 SKIP，236.484秒**；875个追踪输入与HEAD原始blob匹配，跑后零漂移。目录更新后真实publisher消费者 **2 PASS**，不与业务窗口相加。原HTML在NodeVM提供DOM机制、实际普通HTTP/worker/owned PG中完成明确撤回→另派→丢响应同key恢复→B接单/回执/企业ACK，3次API进程与1次worker；这不是实际浏览器。保留单场景的归档复验与旧窗口，不增加独立覆盖计数。

独立审查精确绑定上述源码，**5个独立owned PG场景5 PASS**（5.960秒），无P1/P2阻断；另强化同一正例（1 PASS，2.436秒）核对P3/P4在WITHDRAW/OFFER阶段不选旧step、B接单后只选新step，仍为5个独立场景。重复CREATE、双重绑定和删除旧step的负例均拒绝且业务计数/权限快照不变。见[独审原件及命令](evidence/ordinary-pending-handoff-20261020/independent/review.json)。

实际全局collection **9356项/395文件**；四片 **2342/2309/2368/2337** 精确多重集一致，原9340个稳定key全部保留、新增16，395文件原分片不变。全局AST目录 **3537 IDs / 453571字节**，无缺项/额外项，不改任何上限；原世代保留。更新[精确manifest](evidence/eng057-job-shards.json)只绑定当前collection，不声称Windows执行通过。

[机器结果、失败窗口与边界](evidence/ordinary-pending-handoff-20261020/result.json)、[原HTML真实HTTP轨迹](evidence/ordinary-pending-handoff-20261020/original-page-chain.json)及原始JUnit/日志均保留。基线需求FAIL、开发期两处旧oracle失败、错误消费者selector、归档时owned临时目录拒绝各自单列；不拼接为一次全仓PASS。冻结875文件索引SHA256 `6ad1c030ee890dd3bc2bdfe4f3300b473b1e8d519d1144629df7b44c88a1d938`。

本片不签收完整F2/F3/原AT或现实履约。完整Windows安装、OWNER_MUTATION_PAUSED、原生026–032/roles/seed及owner/DACL具体授权门保持；未运行Windows CI、真实浏览器、真实模型或部署，无新增费用。正式ServiceRelease主体/来源/版本、真实办理与独立履约仍未验；有过提交结果的交接仍按原门拒绝。下一独立原计划候选是已选employees断言provenance与MANUAL修订组合，须先冻结兼容合同、保留人工锁及明确重验，不能凭当前交接局部通过签收。
