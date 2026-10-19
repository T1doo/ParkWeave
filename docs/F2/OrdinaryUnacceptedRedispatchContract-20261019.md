# 普通资料事项未接单终止后的明确另派

起点 `ac9988489a3a495eac47a8b5def824b5d133d60a`。原 V1 产品 §5.5 要求专员说明原因调整责任方，F2-T04/T07要求协同办理闭环。现普通 `CURRENT_PREPARATION` 中，执行者 DECLINE 或接单前 WITHDRAW 后，一次 OFFER 门使同一 Case 无法另派已有合法执行者；旧 Run 授权的交接不是此路径。此为有意保守范围的功能扩展，不能仅删拒绝门。

## 用户路径

原负责专员读取原事项与完整分派历史，在当前资料仍确认、当前原身份/用途权限及 P1/P2/业务 fence 满足时，选择另一位已有同域 READ 的 service_executor、填写原因，明确提交原 OFFER 接口。新邀请使用独立 offer UUID 和原 dispatch 下一 revision，记录 REOFFER 与原事件/outbox；不创建主体、Grant、Run assignment、permit或批准。新方本人 ACCEPT 后独立 SUBMIT，owner 独立 ACK；旧执行者不能查看或作用于新邀请。

仅显式普通 `CURRENT_PREPARATION` 可另派，默认/legacy、原隔离 CaseStep 及 `LOCAL_DEMO_CURRENT_PREPARATION` 保持原协议。历史首 OFFER、旧终态、原原因、回执及通知不改写。已存在任何 ACCEPT 或任何 receipt 的事项拒绝此路径，包括接单后 WITHDRAW、历史指针清空、已有回执或履约；不开放已接单交接、迁移、资源释放或重建事项。

## 有界协议

- 新邀请必须紧接同一 dispatch 的 DECLINE 或接单前 WITHDRAW。完整前驱 OFFER/REOFFER→终态链、原 actor/key/fingerprint、精确 offer UUID、严格整数 revision、资料绑定及 marker 均须可证；缺行、断链、未知或损坏历史拒绝。
- 每代次保持原已确认资料修订/hash、目录hash/xmin及owner/reviewer代际，仅重新核对新执行者当前代际；改变原资料/目录或这些授权代际须走原修订流程，本片不借另派绕过。历史旧执行者撤权不妨碍负责专员核对历史或选择新方。旧 executor 的 key、通知、迟到 ACCEPT、重复终止不能指向新 offer；旧代次key不能混投影为当前代次成功，返回明确409。
- 所有新代次逐字继承首次 OFFER 的原 UTC 截止，绝不续期。首截止前和事务最终权限/来源/期限检查均保留。最多31次邀请；新邀请前 dispatch revision最多60，保留新方 ACCEPT 与负责专员 WITHDRAW 的版本空间。没有自动重试或到期自动重派。
- 原 OFFER expected_dispatch_revision CAS、原 key 幂等、父记录/参与方锁与短事务、原 `_event` 失效/同事务 outbox 均复用。ACCEPT→receipt CREATE 和只读恢复绑定本代次确证的 offered revision、offer UUID、actor、key；CREATE仍为 receipt revision1。
- 旧合法通知先证明历史 source，再按当前 recipient 操作权投递/抑制或显示历史，不能把它当坏 proof 永久留 PENDING。真正损坏/未知 proof 继续隔离，不为清队列而 SUPPRESS。旧执行者不获得新通知/详情权限。
- 原页沿分派表单另选已有执行者并说明原因，明确显示原截止不延长；不使用 legacy `can_reassign`/`sendHandoff`，不复用“新版材料重新接单”的语义。身份、导航、offer代次及迟到响应隔离保持。

## 验证与边界

先以自有合成 PG 和原普通工厂验证两种终止后的另派→接单/回执/企业核对、原 key/冷读/恢复、通知与历史、旧执行者隔离及权限表不变；负例覆盖从未终止/已接单/回执、原截止/锁等待、权限撤销、旧代次、并发 CAS、历史损坏、隔离/legacy不变。完整原 HTML 配实际普通 HTTP/PG的点击路径独立验证；真实 Chrome 与合成响应必须准确另列，不将 DOM替身称真实浏览器。

当前只授权开发和隔离合成测试，不执行真实分派、赋权、批准、来源发布、模型或部署。Windows/正式AT、真实主体/来源/业务及现实履约仍未验。原正式来源专用适配与实际运行输入缺口分别保留，不阻塞本独立必要实现。各失败/成功窗口、源码与实际测试范围分别保存，不相加冒充全仓通过。
