# LOCAL 同计划来源变更再批准：限定交付

源码：`f1309ab0baa455970c7909eb1c1d3bb57f786368`；原远端基线：`7a84772a1ae29e1e9c791943769c4cf4ad6d5e1b`。对应原 F2-T03/T05，仅 LOCAL / CURRENT_OWNER / SYNTHETIC，沿用持久账本、原来源 ADOPT 和原资源接口。

## 产品行为

原 registered 计划同稳定 ID、原来源 ADOPT 实际影响 P2 后，用户可对新 HELD 资源与明确期限重新 PROPOSE / APPROVE。新资源确认、关联 revision +1 与新批准的一次 CONSUME 同事务。旧消费、旧资源占用、旧回执、未受影响 P1 及手工锁保留。历史按每份回执精确 scope 选账本并逐代核原 link / snapshot / key / 当代 ADOPT，不借当前 live bridge，也不 fallback 到隔离账本。

持久入册 Case 漏启动模式时，新交付和裸 later bind 拒绝；已消费旧键 GET / 原 POST 仍恢复原回执。拒绝原计划替换、已开始业务的迁移、外部来源与自动批准。notstarted 是原应用父行锁与八表历史的保守写门，不是新颁发资格，不抵抗数据库 owner 删除事实。

## 实际验证

最终一次七模块窗口 **171 PASS、0 FAIL、0 ERROR、0 SKIP，269.756 秒，exit 0**。171 包含新模块16、原 LOCAL35、资源交付42、原隔离审批55、隔离来源再批10、原替换4、页面局部函数9；不与早期窗口累计。11 份产品/测试文件在窗口期间字节未变，并与冻结源码 blob 一致。

真实回环 HTTP / PostgreSQL 正例从新 Run 与独立 worker 开始，原材料独立 REVIEW / CONFIRM，原确定性 planning-preview / ADOPT 精确 P1/P2 两步、两项目标，首次批准交付、实际来源变更 ADOPT、新批准、新交付、丢弃成功响应后原键 GET 恢复、两项产物到 TXT。`actual-chain.json` 含精确 UUID、两代原回执；`record-pack.txt` 是原 HTML handler 经 NodeVM + 真实 HTTP 导出的文本，**不是浏览器截图**。响应丢失是调用者主动丢弃成功对象，不是网络故障注入。实际服务为 create_app 接入普通依赖；不是本片再次安装态验收。

新资源关联为 revision2，两代占用各三项 CONFIRMED；ledger 前三事件不变、同计划 P1/锁不变。另测后续再次来源 ADOPT 不回填前回执证明、无配置新 Store 两代恢复、跨 Case、撤销、陈旧批准、撤 HOLD 权、过期、去 profile、自引用、缺 proof、未知 scope 及消费后异常全事务回滚。OFFER 负例先原专员合法分派，再真实来源 ADOPT，preview 明确命中业务历史门；P3 BEGIN 负例由原专员执行，缺尾部来源基线仍保留，preview 核明确已开始门原因，未称其来源 ADOPT 已成功。

来源变化夹具明确新建一个可见合成资源及其合成 grants；“授权未变”只覆盖这项显式 fixture 变化之后的批准、交付、导出，不是全链/全库不变。

以下均为实际历史窗口，不累计；保留失败及其修复因果：

| 窗口 | 实值 | 耗时 |
| --- | --- | --- |
| red | 0P / 1F / 0SKIP | 2.839s |
| first-green | 1P / 0F / 0SKIP | 5.164s |
| targeted | 10P / 3F / 0SKIP | 45.747s |
| diagnose-mode | 1P / 2F / 0SKIP | 10.743s |
| with-full-chain | 13P / 3F / 0SKIP | 63.619s |
| scoped-chain | 13P / 3F / 0SKIP | 64.085s |
| blockers | 0P / 1F / 0SKIP | 5.943s |
| registered-chain | 2P / 1F / 0SKIP | 18.249s |
| final | 171P / 0F / 0SKIP | 269.756s |

`red` 为修改前明确正例403；`targeted` / `diagnose-mode` 发现并修复历史仅来源链错误要求 live Store，同时修正第三组重叠容量夹具；`with-full-chain` / `scoped-chain` / `blockers` 保留原 NO_MODEL 固定 release / 来源基线与 actor、来源先变导致 prerequisites 失效的真实失败。没有松原来源/角色门。`registered-chain` 的2P1F来自错误地把显式 source fixture 新增 grants 计入“不变”基线，最终改为准确的后续区间。

## 未验与下一缺口

本片正例是 **原 registered 确定性本地计划、无 candidate**，不是 NO_MODEL service-selection producer 链。原 NO_MODEL resource-coordination 固定 release 即使只请求两目标也包含 P1–P4；原来源 ADOPT 要求所有 adopted steps 的 VERIFY 来源基线。五步计划只完成 P1/P2 亦缺尾部基线，全部完成又属于本片拒绝的已开始迁移。该组合目前未解决，未裁剪 release、伪造尾部 VERIFY 或放宽 unknown/锁/来源门。因此不宣称所有 LOCAL 候选计划已支持再批准，不签本片 P1–P5。

本片新功能未跑真实浏览器、未重构 wheel 安装态、未新开 CI；旧 run12 的安装态真实浏览器仍仅覆盖它原来的 SHA。正式外部五证明、Windows 原生、真实模型、正式 AT 与完整项目验收保持未验。

## 证据完整性

`validation.json` 列原始/公开文件的字节与 SHA256、脱敏次数和完整窗口范围。私有原件保留在指定环境 `/workspace/scratch/local-source-reapproval-20261022/`；失败 traceback 含临时 fixture token，公开 log/XML 共48处替换（含截断前缀）。公开副本不冒称逐字原件；成功业务回执/TXT未修改。`checksums.sha256` 覆盖全部公开证据。

实际 global/four-piece collection 为9462 cases /400 files，S1–S4=2393/2310/2419/2340，精确稳定 case-key 多重集相等，685份 raw blob 绑定冻结 HEAD。catalog 3590 AST IDs、460656字节，原4096/524288上限不变；仅刷新新模块映射与完整目录，不删 ID。五份原 collection JSON 以 ZIP 无损保留，hash 与 eng057 manifest 一致。**collection 不是执行通过或 Windows 兼容验收。**

## 当前发布状态

功能测试与只读独审已完成。提交前原 CLI `GH_TOKEN` 失效，认证 fetch 和 gh API 分别报认证错误 /401，**尚未发起 push**；不是策略审批拒绝，也不是产品测试失败。已有 GitHub 连接读取及公开无凭据 fetch 均核远端仍为 `7a84772a1ae29e1e9c791943769c4cf4ad6d5e1b`。本地完整源码 / 证据提交与 Git bundle 保留，待恢复原已授权写入通道后按原分支正常快进推送；不新增凭据、权限或改写原受测提交元数据。本状态详见 publication-status.json；最终本地 evidence SHA 和 bundle hash由交接回执另列。
