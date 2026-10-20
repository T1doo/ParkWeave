# 通知权限拒绝：真实 sandbox 浏览器验证

产品源码固定为父侧已接受的 `df0849dcdd0eb452c509620c75d5a69a9a4eb80e`；整个 `src` tree 为 `5d2a66b3fffc1caabc01109172527522f88c251e`，页面 SHA256 为 `a50f602bbc1bf84f28afbae16b9ff4f5e9bdbe9d951eaa7700d09122bc497301`。本轮不改产品、权限、审批、恢复或取消门。

先查该产品提交和首个 CI 提交均无既有运行；一次正常推送到 `dev/f2-notice-auth-browser-20261020`。沿已成功资源浏览器 run39349292485 复用固定 checkout、固定 Python/Playwright 依赖、标准 ubuntu-24.04、`env -i`、Chrome channel 和原 `verify_sandbox`。公开仓库标准 runner 免费，见 [GitHub 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。job 上限6分钟，安装3分钟、合同1分钟、浏览器2分钟；无部署、artifact/cache、浏览器安装、自定义secret或权限扩张。

真实 Chrome 加载逐字一致的原页面，真实点击原通知按钮。本机 HTTP 夹具只提供现有通知端点的明确合成响应，没有业务 DB／真实身份或权限后端。六场景为401/403头到达但正文停滞时清除旧通知、迟到401/403保留新身份与新通知、正常MARK_READ 200、原409提示。后两类不是业务办理验收。

浏览器网络只准精确loopback原点、方法／路径／次数；只有一次明确MARK_READ POST，无OPEN或业务操作。真实Response.json仅旁观计数，返回原Promise；迟到场景旁观原loadNotice Promise和noticeError完成，保持原返回值，明确等待原链settled后核对新视图。禁止用Response.finished等待故意不完的正文。fixture全部自有线程在finally有界释放／join，未完成正文不会泄漏为后台长期工作。

## 首轮实际失败与修正

[run1/attempt1：39357832353](https://github.com/T1doo/ParkWeave/actions/runs/39357832353)，提交 `4972b1912f5f793d36a22abd030cd9264a710e10`，job `118416665449` 失败。固定依赖安装和3个标准库安全合同均成功；新浏览器job日志已通过现有授权工具读取，没有触碰旧Windows详细日志。

原JSON确认Chrome `155.0.8059.39`、Playwright `1.62.0`，命令行无禁sandbox参数；实际 `chrome://sandbox` 为PID/Network namespace与Seccomp-BPF Yes、adequately sandboxed。401场景的 `private_notice_cleared_before_body=true`、`error_headers_received_body_never_finished=true`；但fixture漏列原页面blur会话时自动GET `/api/run-access/status`，安全断言按设计拒绝，因此整场景FAIL、后5场景未执行。不能记为六项浏览器通过。[首轮原JSON及run/job绑定](evidence/notice-auth-browser-first-20261020.json)完整保留。

只修此精确fixture缺口：原必要只读status GET每身份一次，late两身份共两次；响应明确enabled/can_approve/can_revoke均false。原产品源码不变；不放宽外站、端口、任意路径、写入预算或sandbox断言。3个标准库合同在修补后再通过。独审同时关闭推送前发现的迟到场景完成屏障问题；最终脚本受审范围无开放P1/P2。

唯一修正窗口限定同一workflow的新提交run2/attempt1，保留run1失败，不rerun旧run。当前workflow和脚本只接受run2；后续文档push的run3及以上不分配浏览器job。

## 修正窗口实际通过

[run2/attempt1：39358145888](https://github.com/T1doo/ParkWeave/actions/runs/39358145888)，提交 `77667682c44303cb2851f4647aa2bd5a85502d3f`，job `118417690493` completed/success，全部步骤成功。公开run总时长1分6秒、job1分1秒；实际脚本26.789秒。[完整原步骤JSON及job metadata](evidence/notice-auth-browser-pass-20261020.json)已经通过现有GitHub工具读取并保存，不是从成功状态推算各场景。

Chrome `155.0.8059.39`／Playwright `1.62.0`；实际PID namespace、Network namespace、Seccomp-BPF和总体adequately sandboxed通过，实际命令行无原禁止的sandbox/security开关。六场景全部PASS：401/403在正文未结束、handler仍等待时清除原可见通知；迟到401/403的原读取拒绝与错误处理完整结束后，新身份／新选择不变；正常MARK_READ 200变为已读，409保留原可见详情及固定提示。授权拒绝正文JSON解析次数为0。

六场景共34次实际浏览器请求，30 GET／4明确MARK_READ POST；全在精确loopback预算内，violations／page_errors均0，自动命令0，六组自有HTTP均停止。这里的HTTP响应为明确合成传输oracle，不是真实后端鉴权、撤权或业务写入证据。首窗唯一401局部断言不计作另一个通过场景，不与本窗六项相加。

本地3合同、CI首窗3合同和修正窗3合同分别保留，不合并为9个唯一项。修补脚本／workflow有限静态独审无开放P1/P2；独审没有独立启动浏览器。结果归档后将再次核对源码／脚本指纹与正常开发分支远端，产品src tree保持父侧已接受字节。

Node HTTP Python包装另补 `shutil.which` 和不可用时显式skip。父侧提出的best-effort响应体cancel属于非阻断优化，本轮保持已接受产品字节，未将其混入浏览器验证。

真实业务鉴权、数据库、用户人工操作、Windows正式AT、真实来源／模型和全项目回归均未由本片执行或签收。
