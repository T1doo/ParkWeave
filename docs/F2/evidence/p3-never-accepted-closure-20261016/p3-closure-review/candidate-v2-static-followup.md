# Candidate-v2 WIP 静态复查补充

STATIC_ONLY / NOT_TESTED。source-v1报告和两个阻断原件保留；本次读新candidate，不把进行中的private core/native测试计作冻结证据。等待固定v2 manifest后再次hash绑定。

两个已报阻断在当前代码中已静态修正：

- native beforeguard现在除实际8表snapshot等值外，独立要求唯一root/evenrev2..62/全terminal且无receiptpointer，events连续且odd原OFFER/REOFFER、even DECLINE/WITHDRAW对应唯一offer；真实actor/payload/原五fence、SQLxmin原DML三元序列、currentpointer和实际terminal状态均核。未泛化旧zero guard或清marker。后五effect仍拒，原link/receipt同事务deferred绑定保留。
- 新资格validator直接核birth/identity/prefix与closure结构，不再伪造KNOWN_NOT_STARTED/epoch0 DTO调用旧validator。独立profile/schema3与原zero/complete-five路径保持。

暂未发现新的确定正常API阻断。该结论仅静态；native拒绝用例、真实并发/rollback、多代terminal及新ACCEPT后coldGET仍须实际固定源码执行。native SQL主要证明实际closed/neverACCEPT与原trace事实；原请求fingerprint/material/P1P2证明由实际Python `_replay`精确验证，不能宣传数据库单独实施全部应用授权。

最终冻结独审约定：`.runtime/p3-closure-review/frozen-v1/review-result.json`，status仅在实际测试全部通过且blocking_findings为空时LIMITED_PASS，绑定frozen_sha/freeze_manifest_sha256/utc/精确argv-JUnit-log与前后imports/source/runner/alltracked；完成后独立seal及writer-cessation.json STOPPED_NO_FURTHER_PRIMARY_WRITES。当前未运行测试、未seal或停写。
