# 固定版本本地合成体验包

下载并解压 [ParkWeave-LOCAL-SYNTHETIC-33bf2efa125e.zip](ParkWeave-LOCAL-SYNTHETIC-33bf2efa125e.zip)，先打开 `docs/demo/LocalSyntheticWalk.html`，再读同目录的启动说明。

- 固定源码提交：`33bf2efa125e5d3b7b59e30b3ea153b9d58a113a`。
- ZIP：940,079 bytes，SHA256 `a6bdbe2846415d585653d92668faca2784328667f06f652c275b8c3b20736b9b`。
- 只含原项目源码、原输入合同、当前操作卡/说明、预检/打包工具和核对表；没有第三方依赖、数据库、私有配置、会话或业务授权。
- 使用已有批准的 Python3.12 环境，从解压包根运行 `python scripts/demo_preflight.py --local-synthetic --json`。缺项返回2即停。当前交付环境四项运行输入均缺失，业务未启动。
- A/B 两次原页面操作、独立材料核对、下载及停点见包内短卡；它是操作路线，未冒称实际完成两次业务。缺本 Run 既有合法 assignment 时止于资料与下载。Windows 正式 AT、真实来源/业务及 AT35 全部未验。

核验与证据见 [交付检查报告](../../docs/F2/LocalSyntheticExperiencePackage-20261018.md)。构建可重复：在仓库中以已有 Python 执行 `scripts/package_local_synthetic_demo.py --commit 33bf2efa125e5d3b7b59e30b3ea153b9d58a113a --output <不存在的新ZIP路径>`，不安装、不联网、不读运行配置。
