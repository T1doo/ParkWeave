# 普通事项零回执交接

起点 `2c74bf70e1f7b03b01cd636f212f6945cae64f3f`。原 V1 产品 §5.5 / F2-T04、T07要求负责专员说明原因调整执行方。本片只扩展显式 CURRENT_PREPARATION：A接单创建的人工步骤尚无任何提交/结果时，专员先明确 WITHDRAW，再从原分派表单明确另选已有授权B，B本人 ACCEPT 创建独立步骤，之后原 SUBMIT / 企业 ACK 不变。

不是只删 accepted/receipt 拒绝：旧 OFFER→ACCEPT→WITHDRAW 必须以原 actor、key、严格整数revision、fingerprint、receipt CREATE确证。每个历史步骤必须 revision1、AWAITING_RECEIPT、current_receipt_id为空、只有唯一CREATE且无任何service_step_receipts。所有历史receipt必须精确归属已撤回原邀请；缺行、未知指针、孤儿、任何提交/补正/重开过历史均拒绝，不恢复旧写权。不声称零回执等于现实没有发生工作或外部效果；本片仍限原合成人工回执，无adapter执行或真实履约。

沿用原两次明确命令、CAS、幂等key/未知结果恢复、父记录和参与方锁、同事务失效/outbox，不自动撤回、换人、接单或提交。新邀请逐字继承首OFFER截止，不续300秒；每代保留accept/withdraw版本空间，最多31邀请。原资料revision/hash、目录hash、owner/reviewer权限代际必须保持，新方重新核已有同域READ。旧执行者撤权不妨碍专员核历史，新方不获Run assignment。已撤回旧步骤及事件不改写，不复制旧正文/结果。新方若DECLINE或预接单WITHDRAW，仍只可显式另选不同已有执行者；每次均核完整前驱与零回执历史。

默认/legacy、隔离CaseStep、LOCAL_DEMO、生产迁移/roles/seed、OWNER_MUTATION_PAUSED及Windows授权门不变。只用已有Linux owned synthetic fixture进行API/数据库测试及原HTML的NodeVM验证；不操作真实分派/电脑，不启动被拒浏览器或绕sandbox，不调用模型/部署/新增费用。具体真实来源、外部履约、完整Windows安装及原AT整体验收不在本片结论中。

验证必须先保留基线交接FAIL，再验A接单→明确撤回→B邀请→B接单新UUID→人工回执→企业核对、旧A拒写、历史/冷恢复、原截止/撤权/来源变化/未知receipt/并发CAS/事务回滚及默认隔离边界。独审按当前源码与实际日志，不复用旧115P/108P。
