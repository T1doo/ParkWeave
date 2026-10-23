# Windows x64自包含封装候选

目标是用户双击即可用，用户不安装Python、PostgreSQL、SDK或编译器，不输入开发DSN。本目录是云端构建代码，**当前不是可办理的成品或已验Windows安装器**。

`build.py`只读取已下载的锁定资产，不联网、不运行安装器、pip、PE或数据库。它核对源码commit、构建器/校验器/资产锁blob、每件资产及原许可证hash，将内嵌Python、Windows wheel依赖、PG最小进程载荷和原页面/SQL封装进候选。三个启动文件来自同一冻结commit。PG选initdb、postgres、pg_ctl、默认plpgsql/文本搜索/编码转换动态模块及其私有静态依赖，排除pgAdmin、StackBuilder和开发工具；不承诺可选扩展或任意动态模块能力。

云端离线命令（需已有Git/Python，**不是给端用户准备开发环境**）：

```bash
python -B -m unittest scripts.windows_portable.test_payload -v
python -B -m scripts.windows_portable.build --source <完整冻结commit> \
  --assets <已准备资产目录> --lock scripts/windows_portable/runtime-assets.json \
  --output <不存在的新候选ZIP>
```

资产目录须保留锁中相对文件名；命令不下载缺项或接受协议。`runtime-assets.json`记录实际官方Python/EDB/PyPI来源、精确版本/大小/SHA256、26件原许可文件hash及22个Windows运行依赖的28条已核依赖边。原许可证随对应资产进入载荷；这些原文和hash不等于再分发义务、安全或原生运行已签收。pytest、Playwright、SDK和编译器不是运行载荷。

双击`ParkWeave.cmd`仅绝对调用包内解释器，`-I -B`与固定`_pth`隔离用户site/系统Python。入口核完整清单后加载原`lifecycle.py`，只读取原`setup_readiness()`，不调用setup/main/doctor，不创建数据库/角色/会话、不改ACL。当前退出2并显示`OWNER_MUTATION_PAUSED`；即使未来原门READY，也继续拒绝未实现的私有实例bootstrap。`usable_product`始终false，不能称安装成功。

完整性清单检测意外漂移、缺项和多余文件；它不是发布者签名，分发仍须可信来源的外部ZIP摘要。Windows路径检查拒绝越界、ADS、设备名、尾点空格、大小写别名及链接/reparse对象。PE核验仅做AMD64与普通/延迟导入名检查；只匹配模块目录/本进程私有exe目录。API-set名称不证明OS提供，符号/转发导出及真实加载均未验。

已核真实资产仍有明确未完成项：官方Python3.12.10嵌入包已被3.12.15取代，仅供静态检查，不能当安全可发布运行时；PG缺私有Microsoft C++运行库，不从PATH/CWD补缺或执行系统安装。原生SESSION/CONFIG安全创建、schema026–032、角色与seed初始化及真实端用户首次运行/退出重开仍需实现和独立验收。不会把Linux证明、假PE fixture或源码help转签为Windows成品。

本组件14项stdlib离线测试单独运行，PE为明确不可执行fixture；不并入原405文件/9521项历史collection，也不称全回归。真实资产静态检查另列，不累加为测试通过。无新浏览器、PG、Windows、CI或用户电脑运行。
