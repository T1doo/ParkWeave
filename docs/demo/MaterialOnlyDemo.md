# 两事项材料演示：本次已批准的独立环境

本入口只用于这一次已明确授权的独立 Linux 合成演示库。使用现有 pgserver 自带二进制和 Python 依赖，不安装、不联网下载。每次 `setup` 都会新建状态，不能将本次授权解释为未来无限创建权限；重启使用同一 `--state-dir`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.material_only_demo setup
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.material_only_demo serve --state-dir <本次输出的私有目录> --port 8765
```

setup 只执行一次；若失败保留目录、日志及现场，不能自动重试新建。普通 API 和 worker 启动不再 setup、迁移或修复权限。前台 Ctrl+C 只停止本次持有的子进程，不删数据库、会话或下载。不接管已有监听器、postmaster 标记、未知锁或进程。该入口不是 Windows 安装方案。

新目录位于 `/tmp/parkweave-material-demo-<唯一值>/`，目录0700，文件按 umask077 创建。`sessions.json` 私下保留企业/专员各一个会话；不要发到聊天、URL、截图或仓库。数据库仅存原认证所需 token 哈希。会话**无自动过期**，停服务或关页面不撤销；后续保留、撤销、清理另行确认。机器销毁或平台清理 `/tmp` 仍可能丢失，不能称永久保存。

数据库只使用私有 Unix socket；HTTP 仅127.0.0.1。initdb 的 postgres 是本次新集群的管理身份，普通 API/worker 使用非管理员、非 owner 的 parkweave_app；没有新系统用户。PostgreSQL角色属于集群级，但本次集群完全独立，不影响其他库/集群的角色。

初始化严格走原 `capture_fixture_cluster` → 本次 CREATE DATABASE → 同进程 receipt → 原 Store.migrate 至 schema32。`creation-observation.json` 只是现场观察归档，不能重建或回放 issued receipt。重启只核系统标识、数据库OID、schema32、源码和 authority 哈希，不重建票据或做迁移。没有使用批量 seed、roles.sql、schema33、IsolatedPlanApproval 或原 fresh-fixture。

初态精确为2个主体、3个 capability_grants（企业 READ/EXECUTE，专员 READ）、1个企业 case.create action_grant、2个 preparation_grants（PREPARE/REVIEW_ASSIGNED）、1条 SYNTHETIC 资料目录；共9行。field_grants、资源、资源授权、Run assignment 均0，不创建执行者或批准。SQL 权限白名单在脚本 `SQL_RIGHTS`，应用不得修改身份、Grant或目录，不给DDL/DELETE；普通 worker仅处理此独立库。

这是普通 `configured_app` 的材料路径，保持 `PARKWEAVE_MODE=LOCAL`。不设置 `LOCAL_SYNTHETIC_DEMO` profile，因为该 profile 的严格合同另需执行者、资源映射与私有 pack/journal。原固定源码包的 profile 预检不会因此变为通过。其他来源/批准 provider 仍关闭。

用户路线复用 [两次输入短卡](LocalSyntheticWalk.html) 的 A/B 双槽材料、专员核对、企业确认及材料文本包步骤；省略候选采纳、资源与 P3–P5。当前会话由本次环境持有人私下读取并输入原页面，不自动填入公开入口。API健康成功不证明用户权限或完整业务完成。

当前环境的 Chromium 在启用沙箱的一次启动中拒绝：SUID sandbox helper 所有者不满足要求。浏览器动作已停止，不关闭沙箱、不更改系统所有者/模式、不加权限、不改安全策略；真实DOM及浏览器下载仍未验。其余已授权 HTTP 材料链、持久化核对可继续。任何 NodeVM 的原客户端文本生成核对必须单列，不能冒称浏览器下载通过。

正式来源、真实业务、正式批准、Windows正式AT、AT35全部仍未验；本次不会把合成资料确认说成资格通过、外部受理或真实履约。
