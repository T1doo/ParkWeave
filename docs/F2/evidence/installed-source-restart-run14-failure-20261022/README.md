# 安装态来源再批准冷恢复：run14失败原件与最小修复

[run14](https://github.com/T1doo/ParkWeave/actions/runs/39758724680)，attempt1，源码 `abe7b018b8bedf3865969aa6a771f08cb2af9999`。job 119757241919：依赖、安装态初态与来源预览已执行；浏览器字体oracle在第18节点失败，exit1。21次POST全部为API初态、47次GET/HEAD（28主请求+19readiness）；0次DOM POST。尚未执行来源ADOPT、再批准或冷重启，不转签run13。

`ci-original.log`是GitHub专用job log API返回全文，包含320483字符的结果行和exit1。stdout PENDING_FINALIZATION不是PASS；只按validation中明确规则去封装后与FAIL result逐字段一致。未另行读取step summary正文，不能宣称三者正文均已独读。原API元数据、官方ZIP及其完整5成员均保留；ZIP内有原wheel，另导出两张原图、result及安装日志。两个PNG逐字相同，未修图。

原图中来源证明details处于折叠态。静态目标实际684码点且缺失为空，前17可见节点CDP实际字体均通过；第18个closed details隐藏p因Range rect误入检查，无实际glyph。修复仅排除原生details未绘制内容，首个直接summary及其子节点保留，open详情继续原严格CDP/字体来源/字符覆盖检查。7项最小fixture回归包括历史红例、打开、嵌套、第二summary及无summary，不能冒充真实浏览器；不下载新字体、不削减覆盖或改业务预算。

第一代API/PG/wrapper全部exit0、PG marker消失、API监听拒绝，cleanup_errors空。尚无第二代服务。正常流导航首次预览截图无横溢、中文清晰，但再批准密度调整及冷热视图仍待新浏览器实测。待独审后仅安排新run15/attempt1一次修复验证，仍10min job、270s工作/360s绝对总时钟、40POST/400GET、10文件/8MiB、同一已批准官方字体及正常sandbox；失败保全后停止。无真实模型/正式来源/Windows验收。

修复源码冻结 `39b6bf49e34600dcc0d0d4cfe0e5ee7c0cbc93c5`。全局/四片精确collection为9498cases/404files（2413/2310/2435/2340），718原字节指纹与冻结源码一致；目录3612 AST IDs/463758B，原4096/524288 cap不变。只收集，不是执行9498项测试。
