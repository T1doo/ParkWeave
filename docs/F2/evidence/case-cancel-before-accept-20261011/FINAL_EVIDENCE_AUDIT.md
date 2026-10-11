# 最终证据独审：LIMITED_PASS

限定结论为 **LIMITED_PASS**：首次实际 ACCEPT 前普通成功且已核实 SYNTHETIC Case 取消切片和本次完整相关回归的可审计证据内，无未修复产品或归档审查阻断。本轮仅只读核源码、Git、安装 metadata、原始/导出结果和命令记录，没有再运行测试、访问数据库、修改产品/tests/Git 或启动浏览器。实际完整回归由父任务执行，本审查核验其原始证据。

源码与测试绑定 `557528da70d905859d7fd09dc0b4ed8f5545af51`；证据提交前读到交付 HEAD `f033bd38ade653eea295941dae8e12a12a44c133`。398 路径源码/测试/脚本/配置清单 SHA256 `5571352ab2d645d7739f4e727c2ba1188d169c919c3109bc263aec0c3592100b`；工作区、源码提交与当前交付 HEAD 的这些字节一致，零漂移。原始 run record 的运行前后零漂移字段与当前核验相符。

单一完整相关窗口：**1271 项 = 1270 PASS / 1 SKIP / 0 FAIL / 0 ERROR**，记录进程退出码 **0**。JUnit `1185.519` 秒，进程记录 `1187.209` 秒。原始完整 stdout 的成绩与 JUnit 一致，两个原环境警告（Starlette TestClient/httpx 弃用、XDG_RUNTIME_DIR 回退）保留，新窗没有 atexit 清理异常。

全部 1271 个唯一 classname::name 的 **multiset** 与旧 1227PASS/4FAIL/39ERROR/1SKIP 原窗完全一致。新窗口的36模块按名称排序，argv与实际JUnit模块顺序相符；原窗口顺序不同，各自实际顺序均保留，不声称同argv/同顺序。没有筛除测试或增加选择过滤；全部43个旧坏ID在这一完整新窗均真实PASS。唯一SKIP仍是原 `test_native_windows_file_backend_gate` 条件，原生Windows验收未执行。

原始新 JUnit SHA256 `bdacfa6bcf654cf51b13cab5c7aa4f29767b3ac2f0441454a3f1f69d326f22c8`；原始新 stdout SHA256 `2622d7ea6c989490e2da08d436d1d3fb973c1199b4fb2348ee696cd87c2bb537`。公开运行记录 hash `5979a0d73b29ca52c220af90eb1b3c715a1515e498136bd419a79ea8de89223b`，其原字段只做披露的绝对repo路径替换，所有测试成绩、时间、退出码、版本和原hash保持。公开记录绑定原始命令记录hash，命令包含全部36模块且无测试剔除参数。Python3.12.14、Node v24.19.0、项目0.1.0、setuptools80.9.0及其他记录依赖均与当前只读安装metadata一致。

最终归档61件，archive-manifest SHA256 `92a3e17ea953c55f73ba22ac5908ac6c03f130dd535213964329a51c88c4c147`；旧59清单 SHA256 `8e6a34a30f00e0cb4fd342b9ad32c0db7a41029a453c861b25ecc38733a70246`。旧59 entry metadata及实际导出文件、原私有输入全部hash不变，仅追加 root/full-final-recheck.sanitized.xml 与 .log 两件。逐件原/实际文件/gzip解压payload hash和字节数核对一致。新增JUnit的全部testcase属性（包括name、classname、time）、结果及suite除披露的hostname外全部属性保持，成绩不被改签。新增日志与JUnit异常/输出/skip正文及属性、公开run metadata的指定token/Bearer/password/PG URI/绝对执行路径扫描均为零；公开SHA值和testcase标识按原意保留。最终本报告与JSON可原样公开，不含实际认证值或绝对执行位置。

公开 failure-map SHA256 `4b2871876a15c04e2c56860820d487e13f42d567d7d8d86942c337b64ae15427` 与 README SHA256 `68d31bc764b673a96c1f452e8b54479513b341714493213377defeed90792db2` 已绑定最终状态；43条ID的原结果与新单窗PASS/hash关系准确。39 ERROR的异常类型字段已准确记为RuntimeError，原JUnit wrapper标签另外保留。

必须保留的旧证据限制：**39份旧子API stderr/api.log未持久保存，现不可恢复**。旧原JUnit/stdout直接证明API启动退出；具体未安装项目导致missing import的根因仍是源码、最小环境与后续执行支持的推断。新完整PASS窗口不能恢复或替代旧stderr，也不把该推断变成每项直接traceback证明。旧事实源码的hash匹配重建、精确Oracle diff及linecache/source-frame限制保留，不冒充另行保存的旧原文件。

旧 installed-process-rerun 的原始stdout仍完整保留 pytest摘要后的 PostgresServer._cleanup/shutil.rmtree/FileNotFoundError（原私有路径指向临时pg_wal）；冻结脱敏stdout保留异常和stack，按披露政策将整个临时绝对路径连同basename替换。该旧进程记录退出0；不删异常，不把旧窗改称无清理诊断。旧 ORIGINAL_EVIDENCE_AUDIT 阶段JSON/MD字节保持，继续表明其审查时新完整窗尚在运行。终核检查器的初版因过严要求脱敏路径仍含pg_wal字面值而失败，仅修本目录检查器；初版私有JSON/log已保留，未改原输入/归档/源码/守卫。

全仓测试（这36个相关完整模块之外）、真实浏览器、原生Windows、完整原AT、生产迁移/部署和真实模型/付费调用仍NOT RUN。历史 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 未重试。剩余交付动作由父任务唯一Git写入者完成：提交必要证据、正常独立开发分支push及远端/差异核验。本限定审查无剩余产品阻断。
