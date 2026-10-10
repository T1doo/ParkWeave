# P1隔离预览的提交保护与快照边界（实现前冻结）

基线 `a0bfbf1ed78485bf4c9fb50a32bbc688cfbb698b`。仅修复原P1隔离预览来源采样到SQLite提交之间的竞态；不扩P2–P5、正式写入、权限、发布或分布式事务。版本2不可变产物、独立proof、原body/key/CAS和冷热恢复合同保留，不迁移历史。

## 来源与既有写入者

| 参与来源 | 既有写入者/协议 | 本次提交保护边界 |
| --- | --- | --- |
| 当前企业身份、READ/EXECUTE/PREPARE、同scope | Store.auth/lock_principal；Store.revoke_capability、owner身份/Grant管理必须用同principal独占advisory key | 当前actor共享principal锁先于资料父行，保持至SQLite提交/原PG事务结束；锁等待后重新认证，提交前再次检查原权限，无新Grant |
| Case/Run/原目标、请求版本、资料revision、两槽ID/version/hash；父行内fact/draft/plan/异议及本地状态 | 原preparation.command/request_intents.save与Case适配器均取同preparations父行；Case状态另有Case行锁 | 原父行FOR UPDATE和既有Case锁保持至SQLite提交。原材料/请求写入必须等待；改变后原CAS拒绝，旧历史不改 |
| 原服务目录ID/version/source及合作发布history/head | catalog_publication.command/安装先取精确catalog source-key独占锁，再目录行/DDL；历史owner直接SQL不参与此协议 | 在任何目录读取之前取同精确key共享锁，保持至SQLite提交；合作发布/撤回/安装等待。未合作owner直写始终仅快照语义，禁止冒称受保护 |
| 已获派专员、已有executor身份/Grant/Run访问（含managed lease） | _sources/_party与registered_dependencies沿既有principal共享锁；owner撤权/assign_status、isolated_run_access既有协议 | 复用既有锁；不新增跨所有actor全局锁。已观察的managed检查在SQLite写锁等待后、执行后及INSERT后提交前重验；时间不能被锁冻结，提交后失效仍须GET观察，不能保证持续有效 |
| 资源集合/资源规则、占位/组合/claim/link、容量、目录决定 | registered_dependencies.collections为有界查询；resource_holds/combinations/resource_plan_binding等沿原resource mutex/parent协议 | 仅保留原实际锁覆盖的已有关联；集合新增、缺行、未来写入和未协作owner变更不新建全局锁，明确快照语义 |
| dispatch/offers/receipts/events、本地lifecycle、Case状态 | 原service_dispatches/executor_receipts/case_lifecycle父行及原子表行锁 | 复用原协议，未知或绕过协议写入不宣称原子全来源保护 |
| fact/assessment有效期、resource时窗/lease、动态registry/actions声明 | 原时间采样；进程注册声明无跨进程写入锁 | 仅采样时观察值；末次重采样可拒绝已观察变化，但不是原子提交证明，也不能冻结时间或进程声明 |

本次不改变既有写入者。新增锁顺序：原认证actor共享principal → 原preparations父行FOR UPDATE → 精确服务目录共享source-key（在任何目录关系读取前）→ 原_sources已有principal/dispatch/receipt/resource/Case锁 → SQLite BEGIN IMMEDIATE。合作目录写入者只取同source-key独占→目录行/关系，不反向等待资料父行；身份撤权者principal独占先于任何被管理身份修改。不得锁升级，不以独占目录关系锁代替权限，不增加跨进程锁、全表写权或安全配置。原_sources的既有锁序保持，有限3秒锁超时拒绝；不宣称已证明所有旧适配器的全局无死锁性。

## 提交与对外语义

SQLite获得写锁后重新检查原actor权限与已经观察的managed时效，拒绝等待期间失效。执行后的末次来源采样只拒绝实际观察到的变化；随后INSERT、严格读回proof、再次权限/时效检查、SQLite commit都处于上述合作锁寿命内。故障均保全日志；提交前异常回滚，不保存假成功；提交后丢响应沿原key GETonly核对。

全来源没有共同原子锁。因此GET/POST/重放/恢复历史统一用 `SNAPSHOT_MATCH` 或 `STALE`，不再输出 `CURRENT`。返回 `source_consistency=COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON`、`source_atomicity=false`，页面明确“采样时来源匹配；不保证提交时全部来源不变”。新POST完成后不拿执行前旧current作当前值：重新采样仅用于响应比较；若响应采样失败，已提交不可撤销，原key恢复可读，禁止自动POST。旧不可变正文和proof不重写，历史标签是本次读取的比较结果。

真实HTTP/PostgreSQL/Chromium屏障oracle：末次采样后合作目录/资料/撤权写入等待SQLite commit；非合作来源可真实改变而原结果不得CURRENT；SQLite写锁等待期间managed到期/撤权先提交拒绝，无新产物；INSERT后故障回滚与同key明确重试恢复；提交后断响应冷GETonly保留原产物。全部public逐值比较，只有测试明确原来源改变可变，不把其变化归于预览。普通候选push后冻结源交独审；未审不合dev，main不变。
