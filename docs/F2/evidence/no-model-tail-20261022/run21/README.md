# run21：原 P3→P4→P5 安装态真实浏览器闭环

[官方 run21](https://github.com/T1doo/ParkWeave/actions/runs/39777380048)，job `119819665446`，attempt1，受测完整SHA `dbc66b066b592d8eeb2da705472f326893e8fa72`。唯一实际业务浏览器执行：job／全部step成功，最终[result.json](result.json)为PASS，无finalization_errors／violation／page_error；stdout先输出PENDING_FINALIZATION，不将它当终态。step summary正文未独立读取。此前run20无步骤跳过原件[另存](../run20-skipped/README.md)，无浏览器结果，未重跑。

没有修改产品源码：三份既有合成release已支持五步骤。本次独立新输入→NO_MODEL候选→ADOPT→LOCAL明确批准→P1/P2原API前置，随后真实页面六次业务提交：原专员OFFER→原执行者ACCEPT→本人全文SYNTHETIC回执SUBMIT→owner ACK→原REVALIDATE→CLOSE_LOCAL_RECORD。owner通过原API分别显式VERIFY P3、P4、P5；接责、提交、确认、重校验及本地关闭都没有自动VERIFY。原角色／期限保留，无Run assignment或新增权限。

三个因果409：P4未完成拒绝REVALIDATE；P4已VERIFY、P5尚无原重校验证据时拒绝P5 VERIFY；同一当前revision/cycle/snapshot直接CLOSE拒绝。三次前后命名业务投影全等，不是全DB不变。P5合法必要条件是原REVALIDATE，READY可VERIFY；本例额外关闭本地记录后才VERIFY，不能声称必须先关闭。最终五目标LOCAL_OUTPUTS_VERIFIED，Case依然未全部履约，资格NOT_EVALUATED／外部NOT_SUBMITTED／线下NO_EVIDENCE。

实际30POST＝21 API正例＋6 DOM正例＋3预期409，共27成功；113 GET/HEAD＝95主流程＋18就绪尝试，主流程含3次fact-clarifications GET403单列，不当成功、不绕过。六个原页面请求key对应唯一SQL事件／actor／action／完整payload；dispatch公开投影仅隐藏既有内部marker，完整SQL原件仍在result。只保全SQL fingerprint，不称从原请求正文独立重算。ACCEPT／SUBMIT正常成功后原键GET各200 COMMITTED，精确Case／Run／offer／版本／key／主体均核。

两份真实页面下载[未重校验TXT](p5-unverified-case-record-pack.txt)16500B、[五目标显式核验TXT](p5-verified-case-record-pack.txt)16893B。原API完整row／source_trace指纹先验，TXT按完整字面V1导出白名单相等；两份因P5真实状态变化而不同。七个中间目标快照及最终导出如实保留等待／待owner核验／已核验状态。

四张原图：[接责](01-tail-accepted.png)、[回执ACK](02-tail-receipt-acknowledged.png)、[P5重校验前](03-p5-not-revalidated.png)、[390px结果](04-five-goals-verified.png)。前两图中文与回执可读；第三图显示重校验表单，不能据图说更低的关闭按钮可见；第四图显示汇总及部分目标卡片，五目标完整状态由DOM／JSON支持。四视口无横溢，非整页／全部码点／手机实机验收。现有字体集合覆盖684所需码点，真实glyph仅限所观测可见节点。

[官方ZIP](artifact.zip)原9成员、解压3269741B，低于10文件／8MiB上限；wheel仅存在ZIP内，191包文件逐字对应受测Git树，构建／安装零依赖下载、隔离安装路径，不从工作树导入。原批准固定Noto/OFL仅私有runner临时使用，字体不在证据包。业务完成46.66s，46.74s计到附件扫描，不冒称全部最终化时长；原270s工作／360s绝对时钟／10min免费job及请求门保持。

一个API／PG代次，结束实际API与PG exit0、wrapper0、marker消失、监听拒绝，无清理错误；setup PG同样exit0。没有服务冷重启／新context恢复验收，不重复转签run17／18。正式外部来源、Windows原生、真实模型、真实履约与正式AT总验收仍未完成。

[完整原job日志](ci-original.log)、[官方run元数据](run-api.json)、[job元数据](job-api.json)、[artifact元数据](artifact-metadata.json)、[离线原件核验脚本](archive_run21.py)、[限定回执](validation.json)、[源码等价发布映射](source-publication-map.json)、[全部归档校验和](checksums.sha256)。ZIP SHA256 `b8532315c8cc215c28a6d63f862dbde29475636d5647d83370540a4ae58050fb`；完整原日志 SHA256 `7f81441119ea51f2e0cf17decf6ad296d16258867b93d426ac1d73c9e819fef1`。不包含临时下载签名URL或凭据。
