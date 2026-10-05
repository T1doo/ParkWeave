# 园合 ParkWeave

独立园区企业服务项目。设计原件及动态入口：[docs/Plan.md](docs/Plan.md)。本次为F1有界工程增量，只有合成身份、严格诉求契约、持久Run/Operation/outbox和可信本地建单；未通过完整F1、PR0或赛事验收。

浏览器有“服务/协同/资源”三个入口。创建诉求返回202+run_id；独立worker在PostgreSQL短事务内创建Case、核验本地回执并写outbox。Run可SUCCEEDED（LOCAL_CASE_CREATED），Case仍NEEDS_INPUT，外部受理NOT_SUBMITTED、线下履约NO_EVIDENCE。不能把本地建单称作办成全部诉求。

所有数据为SYNTHETIC；模型没有启用，不存在真实模型调用或开发模型兜底。唯一动作case.create/1，无资格裁决、预约、文件导入、Shell/SQL/生成代码执行或外部动作。普通目标文字仅作为数据保存并通过textContent显示。

## 已测试的Linux工程路径

本云环境Python 3.12.14、PostgreSQL 16.2、依赖精确清单见requirements-linux-evidence.txt。这是Linux证据，目标Windows 11 x64精确版本、安装权限和原生服务测试均BLOCKED。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-linux-evidence.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
# 显式合成测试服务器：本机8765；API与worker为独立进程
.venv/bin/python scripts/linux_fixture_server.py
```

测试依赖pgserver只提供临时Linux PostgreSQL，不能当作Windows安装器。测试创建临时数据库并删除；harness使用独立`.runtime/smoke-pg`保留合成状态，Ctrl+C停止API/worker/测试数据库。不连接用户电脑或Sim2Act。

访问http://127.0.0.1:8765，在页面输入`.runtime/synthetic-sessions.json`里的一个合成会话。该文件由显式setup生成，随机token不打印、不提交；三个身份属于两个园区、三个企业。刷新页面需重新输入会话。新会话不是园区真实登录；当前仅支持企业经办合成角色，其他角色与字段级Grant仍待实现。

浏览器测试需agent-browser 0.38.2及Linux `/usr/bin/chromium`；运行`python scripts/browser_smoke.py`前需harness存活。截图仅留在忽略的.runtime目录，非交付要求。

## 目标原生部署接口（尚未Windows验证）

安装并配置独立PostgreSQL数据库`parkweave`及迁移owner；配置独立应用角色`parkweave_app`，由安装者设置仅本机认证。项目不查找隐藏凭据，不生成持续账号凭据。迁移/seed使用owner，API/worker只用应用角色。

```text
PARKWEAVE_DSN=<显式提供的迁移角色连接配置>
python -m parkweave.cli migrate
在该独立数据库由owner执行 src/parkweave/roles.sql（应用角色须先存在）
python -m parkweave.cli seed-synthetic
PARKWEAVE_DSN=<显式提供的应用角色连接配置>
python -m uvicorn parkweave.api:configured_app --factory --host 127.0.0.1 --port 8765
另一个进程：python -m parkweave.worker
```

应用角色仅SELECT身份表及SELECT/INSERT/UPDATE业务表，无DDL、身份UPDATE或DELETE权限。CLI撤权需owner执行`python -m parkweave.cli revoke --principal fixture-a`。授权锁协调只支持该CLI撤权路径；未来身份管理必须遵守同一事务锁协议，禁止绕过它直接修改身份表。

API默认本机8765，与Sim2Act端口不得重用。数据/会话/日志位于独立.runtime，禁止生产数据；本增量没有模型账号、调用预算或共享配额协调器，所以真实调用始终禁用。关闭网页不影响存活worker；停止进程/关机后本地执行停止。无公开部署。

限制及测试范围：[docs/F1/TestSpecification.md](docs/F1/TestSpecification.md)。Windows Doctor/Setup/Start/Status/Stop/Test.ps1、多角色授权、事实冲突、真实模型预算、外部结果不明、长任务心跳和资源事务将在后续独立增量实现；不得把当前子集通过外推为完整AT PASS。

F1 ENG-002增加了测试专用FAULT_INJECTION持久账本及计划重复/规模/引用边界。它不注册API动作，Store.migrate不会安装fault-schema.sql；只有隔离测试库显式安装。模拟远端与操作账本分事务，回执丢失后按操作ID核对，未知不重发；不是外部系统集成或线上效果。新增映射与限制见F1/TestSpecification.md，完整AT仍NOT_RUN。
