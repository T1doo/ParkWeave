# 最终独立归档审计

**LIMITED_PASS。** 249件冻结原件/导出、34个原失败关联、最终38模块原结果、源码405与旧149归档均通过限定核验，无剩余归档阻断。正常交付commit/push/远端核验由父任务随后完成，本审未操作Git。

源码完整SHA `796b41ad8939ba1d067f84f137a4d2a1861f06d4`；405清单SHA256 `cb47c652372f4aad3076c7adc995e77f505800f4aa1e28d39a94617b0a9d96b5`；原实施前合同SHA256 `a2302d0f69dd20932d78cd21aa64099ddb9a19a273641d715eab61343930c9b4`。当前405字节无漂移；源码commit字节来自父任务只读precommit核验，本审独立核工作区及source/hash字面绑定。

## 实际完整窗口

父任务完整38模块，一窗1560 PASS / 0 FAIL / 0 ERROR / 1 SKIP，exit0，1561唯一ID；原1391个ID全部保留，新增170。进程1562.358秒、JUnit suite1560.155秒、pytest汇总1560.20秒。两个原警告保留，无atexit清理诊断。

原JUnit SHA256 `77073956059174668caca9528dec3ac072f2d5c0bf37a6f34a89db8dd824f054`；原stdout SHA256 `86925add0de4648e3a7a97acce1d04f334e131a96eacabe9b8f43259e8ec5106`。唯一SKIP为原 `tests.test_authorization_files::test_native_windows_file_backend_gate`，明确NOT_RUN Windows11 x64的reparse/ADS/ACL/clean lifecycle。不是全仓/AT/Windows通过结论。

原独审REVIEW签时RUNNING字段和原字节保持。本新报告仅在完整窗口结束后另签。独审第六226 PASS仍对应实际e103cb未提交窗，最终cb47仅十个旧schema测试Oracle变化；产品src/scripts/pyproject、新backend/offline模块/VM相同，不称226在cb47重跑。

## 249件归档保持

manifest SHA256 `6c24677c7a2b27c330d4da2b714f66561ec68ef44ecb962bccec42b413137096`；failure-map SHA256 `3a7c38d7e1fc68ea24b5d183486d532b1655d67138f93f7da918aabdab371a25`。249原件3465991字节、导出3461260字节，0gzip。分类17JUnit、28stdout/报告、149JSON、55精确静态code。逐件原/导出/payload hash与size、按实际policy计算的expected bytes/redaction计数及全部JUnit身份/结果/时间/suite计数一致。

JSON 8440处40/64位hash字面保持；凭据key门及非静态运行文本扫描通过，未发现真实运行凭据。55件静态白名单 `902d0e18361454d70f7d925b441e5b04d800917f7cd986ed28a66d1326435a96` 与独审逐件内容批准完全一致。249原输入没有新增或缺失；后阶段三份父任务支持metadata及本次审计文件明确在249之外。

父任务实际重跑两helpers均exit0，249exports+manifest+failuremap共251文件零变化；本审在内存复算expected bytes，没有写public。前两片149旧文件全集无增删、无字节漂移。

## 原失败与修后关系

34个原FAIL/ERROR、34唯一ID及原异常type保持。根22项由最终38同ID PASS复验；独立12项由第六226同ID PASS复验，含十个产品反例和两个独审Oracle错误。逐条诊断/evidence-grade/修后来源manifest核过。standalone Node原exit1与原probe/原argv修后exit0单独保留，无JUnit ID且不计入226。

## 本次审计诊断原样保留

| 独立程序 / raw日志 | exit | 分类 |
| --- | ---: | --- |
| archive-audit-check.py / archive-audit-check.log | 1 | 自有粗扫描误认相对路径root片段和两份已审合成POISON说明 |
| archive-audit-check-corrected.py / archive-audit-check-corrected.log | 1 | 自有扫描把紧接哨兵的中文解释计入值 |
| archive-audit-check-final.py / archive-audit-check-final.log | 0 | 精确路径边界及两个原hash固定、各单一已审哨兵例外后，全部实质检查通过 |

这些是归档checker Oracle断言，不是业务testcase、访问拒绝或真实泄漏。各程序/raw log/run完整路径名及SHA在本JSON。另保留报告组装stdin exit1的过严“只能新增独审文件”库存断言诊断 `archive-audit-signoff-assembly-inventory.log` / `archive-audit-signoff-assembly-original-run.json`；修正只显式列出三个已知父任务后阶段支持JSON，冻结249原件从未漂移。所有诊断不覆盖、不虚构JUnit ID。

本次archive-audit命名的三个stdlb只读程序已按精确hash批准作为249之外support复制；日志依既有stdout policy脱敏，JSON保留字面hash并处理执行路径/URI/Bearer，单独support-manifest保存原/导出SHA。不重建249或改已签REVIEW。

## 其他真实失败与范围限制

父任务完整cached whitespace检查实际exit2：66条诊断逐行对应冻结导出，18log、18XML、30原diff空上下文。没有trim证据或改Git配置；新写docs/helpers/metadata scoped检查exit0。完整检查仍记录FAIL，原stdout和解释在249外支持文件保留。

旧worker Case_count0仍UNCONFIRMED；旧39API stderr缺口和旧清理异常继续披露。浏览器NOT RUN、0次启动/替代重试，历史ERR_BLOCKED_BY_ADMINISTRATOR未重试。没有再跑业务/PG/ASGI/Node测试、模型、部署、生产迁移、凭据/网络配置或新Grant。没有全仓、完整生命周期、nativeWindows通过结论。

父任务待正常交付commit/push/远端protected及HEAD/洁净/divergence核验；本审不预写成功。结论仅对应有限普通SYNTHETIC纯本地人工取消核对及此原证据保存。

完整249逐件checks、程序/诊断/support hash、签署时README/Evidence/helper hashes在 `ARCHIVE_AUDIT.json`。本报告新增于249冻结之外。
