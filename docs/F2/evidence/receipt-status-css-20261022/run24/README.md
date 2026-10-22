# 回执空提示 CSS：run24 原件与失败边界

- 源码：`773bde665de4883953329d05b4f5c8dc82f7e2bf`，run24 / attempt1。
- 官方执行：https://github.com/T1doo/ParkWeave/actions/runs/39802376995 ，job `119906296876`，最终 **FAIL / exit1**。
- `artifact.zip` 是官方完整 ZIP，3 成员 304506B（两张真实1200px PNG＋result.json），压缩257757B。`ci-original.log` 是官方 job API 解码全文，163150B，归档前与 API 字符串逐字读回核对；不是 CLI 截断导出。run/job API 与 artifact 元数据同时保留。其余 validation、检查脚本、故障注入记录和校验表是派生材料。

## 实际通过的局部

Chrome155.0.8059.84 正常 namespace / PID / Seccomp sandbox。原 HTML 真实渲染，7次回放GET、0 POST、无业务API/数据库/模型。1200px 原空段高度28px、左边框3px；修后高度、margin、padding、border均0且透明，DOM及aria-live=polite保留。两张原图已逐张查看，空绿横条消失；两次截图滚动位置不同，不作像素叠图比较。CSS之外HTML/JS字节一致。

## 失败与未执行

原驱动的字符串 wait_for_function 谓词要求 eval，被 CSP 拒绝；未修改 CSP。另两次 token-change 自动 GET /api/run-access/status 未在夹具建模，返回404，不计成功。Playwright scope 已退出后才尝试截图/close，二者均报Error；只确认回放HTTP监听最终REFUSED，不声称正常浏览器关闭。

非空待核对、恢复成功、清空后、390px与实际可见字形来源均未完成。字体静态集合预检不等于字形渲染验收；aria属性保留不等于读屏播报验证。没有用旧业务片段补成PASS，不是业务恢复、安装态或AT35验收。

## 同轮最小候选修正（尚无浏览器通过）

当前 driver 改函数谓词、精确disabled状态GET响应、在Playwright transport退出前保全失败图并close。CSP、sandbox、原源码绑定、40 GET/0 POST、90秒UI清理、360秒发布及原job权限预算均保留。`driver_fault_checks.py` 使用纯注入验证5种生命周期/故障与2种精确GET处理，7项通过；另静态检查3个谓词，未启动浏览器/监听/模型/CI。该记录不能代替真实CSP执行。

本次授权的一次run24已使用，失败后没有自动重跑，没有重试本地sandbox；workflow与字体仍只绑定24，候选以skip-ci提交保全。

summary未出现upload-aborted日志，但正文未独立读取。Windows原生、正式来源、LIVE及C0原材料门保持独立，未因此完成。
