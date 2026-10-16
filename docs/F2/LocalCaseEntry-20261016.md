# 普通用户隔离本地事项入口

本片接续 `dc7f998d7b0fd84142da5633d511a9bc1a8084ba`，对应原 F2-T07 / AT-35 的冷启动可用性缺口。新增独立启动与范围说明，复用原 `configured_app`、`parkweave.worker`、原建单页面与 PostgreSQL。不会把此前测试组合里的完整 P1–P5 当成普通启动已开放。

## 从干净目录启动

仅适用于已有项目依赖的 Linux 开发环境。使用仓库现有 `.venv`；以下命令不安装依赖、不调用模型，也不连接生产。

```bash
PW_REPO=/workspace/ParkWeave
export PYTHONPATH="$PW_REPO/src:$PW_REPO"
mkdir -p /tmp/parkweave-user-start
cd /tmp/parkweave-user-start
"$PW_REPO/.venv/bin/python" -m scripts.local_case_entry setup-synthetic
```

`setup-synthetic` 每次建立一个新的私有 `/tmp/parkweave-local-case-…` 目录，输出 `state_dir`。这一步是显式固定合成初态准备：原临时集群创建证明、原 schema 032 迁移、原 app 数据库角色与 `seed-synthetic` 的三个合成会话。没有分派任何 Run、批准计划、创建 ServiceRelease 或重建跨进程 issued 证明。失败目录保留，不自动修补。

把实际输出路径填入下面命令；不要使用示例省略号作为路径：

```bash
"$PW_REPO/.venv/bin/python" -m scripts.local_case_entry serve \
  --state-dir /tmp/parkweave-local-case-实际输出目录名 --port 8765
```

启动输出 `http://127.0.0.1:8765/local-entry` 及本次自有 API/worker PID。只监听 localhost；端口占用时拒绝，不接管旧监听、不结束他人进程。第一次初始化和后续启动是两条分开的命令。

## 用户实际可做的操作

1. 在本机私下读取输出目录 `.runtime/synthetic-sessions.json` 的 `fixture-a` 会话。不要发到日志、URL、截图或他人消息。
2. 在新入口输入该会话并“只读核对当前范围”。诊断重新检查原身份、READ/EXECUTE 和 `case.create` action grant；提示不会赋权，也不保证下一次提交时权限仍有效。
3. 打开原确认与办理页面，重新输入会话，填写本次目标，核对后点击“创建本地办理记录”。这是原页面真实的一次明确提交，没有虚构第二次预览/确认按钮。
4. 原 API 接收后由原独立 worker 创建 `LOCAL_CASE_CREATED` 记录。Case 为 `NEEDS_INPUT`，外部 `NOT_SUBMITTED`、线下 `NO_EVIDENCE`。记录原运行编号。
5. Ctrl-C 或向本次 launcher 发送 SIGTERM。只停止本次子进程和自有 PG，保留状态。重新执行相同 `serve` 命令，可使用原页面“找回我的本地办理记录”，或在“协同”工作区输入原运行编号并“查看持久状态”。读取不会重新提交。

状态保留在 `/tmp`，操作系统清理、环境销毁或用户删除目录会使其丢失；这不是备份或生产持久存储承诺。会话只进入当前页面内存，启动输出不打印 token 或 DSN。

## 重启与阻断规则

后续启动检查目录所有权/私有权限、原集群标识、schema 032 与原非特权 app 角色；不运行迁移、seed、角色 SQL，不补 Grant、assignment 或批准。撤销身份、撤销 EXECUTE 后仍拒绝，重启不会恢复。schema 不符、非法 marker、另一个 launcher 持锁、已有 PG 进程标记或上次子进程停止未确认时，保留并明确阻断。不要通过修改 marker、复制数据库、手改业务表或清理未确认标记来解锁。

此入口不接入测试文件。`tests/release_new_case_support.py` 的目录 owner 注册/绑定、`assign_status`、`IsolatedPlanApproval` 是另一批显式测试前提，不会被导入或执行。现有 `scripts/review_demo.py` 仍是独立历史证据目录/候选 SQLite；`scripts/linux_fixture_server.py` 的原临时演示行为不变。

完整新事项获派访问、可信目录和批准桥没有现成合法普通运行时接线，本入口显示 `BLOCKED_NO_RUNTIME_ASSIGNMENT_CATALOG_APPROVAL`。不会把本机用户提示、Mock 或原测试通过当作授权。先前完整 P1–P5、六目标及历史证据保持原范围，不会因本入口声明已完成。

Windows、正式 AT-35/完整 F2、真实模型、生产/真实履约未执行；本片不新增费用、真实凭据或安全权限，不部署、不改 main。

## 验证记录

冻结源码：`b5aab9f9a942ae430dd6d302ac645b74bc9b1edc`；开发分支：`dev/f2-local-case-entry-20261016`。仅新增两个 scripts 与一个测试模块，原产品 src 完全不变。704 个源码/测试/配置输入冻结，前后哈希 0 差异。

最终同 SHA 五个完整模块 **61 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，93.61 秒、4 个既有警告：新增本地入口8、原启动器10、原评审目录8、foundation21、worker gateway14。独立同 SHA 完整新增模块 **8 PASS**，37.786 秒，全部与61重叠，不累加。冻结独审 PASS，无剩余实质发现。前批尚余90模块/2251原节点的集合与本批四个旧模块无交集，故仍保留该未执行范围；没有合成全仓通过。

实际 Chromium：新入口鉴权范围→原 intake 单次明确 POST→原 worker `SUCCEEDED / LOCAL_CASE_CREATED / NEEDS_INPUT`；精确停止自有进程→同端口重启→新浏览器上下文原页面 GET 原 run，冷页面 POST=0。业务/身份/Grant/assignment 快照前后相同；跨组织读取拒绝，批准与访问桥仍关闭。撤销身份/EXECUTE、外来目录、symlink、并发锁、占用端口、无效 marker、错集群标识及停止未确认标记均拒绝。停止未确认仅验证预置标记的拒绝，没有制造不可杀进程。

独审发现并修复了 TIME_WAIT 同端口重启、错误的第二确认按钮说明、marker/PG 异常诊断；另修复外来同名私有目录拒绝前不应创建锁文件的问题。开发 v1 因测试 URL 少一个 `/` 为2PASS/1FAIL；v2 3PASS、v3 25PASS及旧冻结60PASS均保留，后续真实完整重跑61通过。独审首次修后复验错误期待字面 `Denied` 的断言失败也单列保留。旧成绩不证明最终新源码。

[原件配对、测试、失败记录与审查归档](evidence/local-case-entry-20261016/public-pairs.json)，[最终审计](evidence/local-case-entry-20261016/final-audit.json)。6153份旧封存原件仅只读复核，哈希0差异；没有重跑旧封存 producer。
