# ParkWeave 前端视觉接入

功能基线：`e90e16dd0f2151efde4e7be6de6ebe98ffea43b8`。初始基线：`6c7b57fd13b48fc2bd0f118381c61e9e77c6b451`。独立分支：`dev/ui-polish`。

## 实际产品改动

父级已明确批准两个共享模板的 `<style>` 区写入。本分支正常 merge 最新功能基线，无冲突，再将 CSS **实际接入** `src/parkweave/web.html` 和 `src/parkweave/park_demo_web.html`。最新来源观察脚本与文案完整保留；相对新功能基线，所有非 style 字节逐字相同。后端、控制器、CI、权限、批准及事务逻辑不作视觉修改。

保留绿色园区风格，统一字体、间距、边框与层级。桌面记录使用两列卡片，800px 以下单列；资料编号完整换行。详情摘要与人工批准核对使用不同层级和色彩，原未知/失败文本保持可见。保持原空状态与隐藏条件，不推断成功、不改变按钮可用性、不自动批准。统一 44px 最小按钮高度、键盘焦点、减少动画与强制颜色支持，窄屏输入使用 16px 字体。无需新框架、外部资产或资源加载。

`ui-polish.patch` 是相对 e90e16dd 两个实际模板的精确 Git 差异，已接入，无需重复应用。两个 `.css` 文件仅为方便审阅的同字节副本。

## 实际验证

在整合后的仓库直接执行两个原有完整模块：

```sh
/tmp/parkweave-ui-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_service_instance_cold_web.py tests/test_dispatch_notice_page_offline.py --junitxml=deliverables/ui-polish/offline-junit.xml
```

56 PASS / 1 既有 Starlette 弃用 warning / 5.39 秒。首次仓库入口因缺 psycopg 在 collection 前停止；随后把原仓库固定依赖安装到隔离 /tmp venv，再完整重跑通过。未修改项目依赖或消除既有 warning。早前临时副本 56PASS 不是本次成绩来源。没有重跑后端、数据库或完整项目测试。

CSS 语法与选择器解析通过；六组正文色对计算对比度最低 5.39:1。脚本及样式外全部标记与新功能基线逐字相同，见 `static-validation.json`。`git diff --check` 与补丁 reverse-check 通过。

## 视觉与 CI 边界

在当前整合树上，Chromium 保持 sandbox 启动时因系统 SUID helper 配置错误退出；未改 sandbox、权限或系统设置。`browser-attempt.json` 记录本次实际模板指纹和错误。**本候选视觉未验，没有新截图**；布局、焦点遮挡、实际中文字体、窄屏和真实批准流程仍需受保护浏览器复验。不复用旧 run12 作为本片证据。

已向父级给出原 CI 路径与预算：`readonly-browser-smoke.yml` 单 job 上限 6 分钟，`fictional-park-browser-once.yml` 上限 10 分钟。前者只接受旧精确分支/run6；后者只接受旧分支/run12且执行审批写流，不用于本片。两者均无 workflow_dispatch，driver 也绑定旧分支/运行；本分支没有可直接复用入口。未改 CI、未推原功能分支、未触发任何 hosted job；实际 CI 次数/分钟均为 0。纯视觉 hosted 检查须由父级协调一个适用的有界只读入口。

独审静态通过：189 + 48 条规则解析，23 个代表性禁用按钮级联检查通过；两个禁用态配色问题已修复关闭。无已发现剩余实质展示问题，但不替代真实浏览器视觉验收。完整状态见 `validation.json`，独审范围及结果见 `independent-review.json`。
