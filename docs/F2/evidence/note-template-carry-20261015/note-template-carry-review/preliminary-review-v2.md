# WIP 预审 v2：历史材料绑定阻断

状态 BLOCKED_PENDING_FIX。不是冻结最终独审；尚未启动正式完整模块窗。

NC-R01（epoch version bool/float别名）已由7562的新helper收紧；原RED保留，正式待重验。

NC-R02在精确源7562fb30ad2160ad6f26a49864fc8f46440a91b0的隔离产品副本仍复现：成功carry真实PG/API回执，纯内存将current need_summary替换成从未实际VERIFY的正文并同步sha/epoch ref，或只换outline标签，再重算carry/request/eventfp，完整_recovery_proofs仍接受。3个字面检查里2个错误接受、captured epoch hash阳性拒绝正确；1个pytest FAIL，runner4.621秒。没有向PG写入篡改内容。原件在epoch-fixed-material-binding-v5，精确包导入路径与modulehash可查。

建议仅新carry validator从该事件以前的原VERIFY/ADOPT重建P1 preparation_sha256及当时service_version，用原prep.snapshot对保存的current完整双槽材料逐字段核验。未来合法材料/NOTE变更不能拿live最新源重写旧carry。root已HOLD并要求新SHA全部模块重新跑；旧partial不迁成绩。

旧v2材料继续兼容链已隔离WIP通过1项；必须原REFRESH新卡再重确认。此旧fixture5目标/P1–P5，不代新六目标独测。v3末尾跨合法EDIT/CONT对比字段的口径错误已另留纠正receipt，原件不改。

新formal目录已准备17完整模块、2个历史fixture（其中20个纯篡改检查）、6个新carry真实64/128预算节点；等待父代理最终新SHA及实际模块变化，不提前启动或签PASS。两份source-wip-v1/v2整包私有运行副本必须从公开归档排除，只导出manifest/探针/差分/结果。
