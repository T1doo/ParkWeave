# 本次两事项合成材料文本

[材料 A](material-A.txt) 与 [材料 B](material-B.txt) 是原 `web.html` 的纯 `materialPackText` 函数在 NodeVM 中处理真实 HTTP readiness 响应后生成的 UTF-8 文本。重启前后分别生成，字节保持一致。它们不含会话、DSN 或凭据。

**浏览器沙箱启动被拒绝，原按钮、Blob、浏览器下载未验。** 这些文件不能当作浏览器下载通过的证据。

| 文件 | bytes | SHA256 |
|---|---:|---|
| material-A.txt | 1832 | `23155ee525bc0de6bbb77ab32e9b0bdb89fc847921e99aa6a892b448ed0ed9ac` |
| material-B.txt | 1851 | `663994da635aab152b15c36e4617ec034f27530df857e12893650d2d43d611a9` |

实际材料写入源码：`ee4d69adb3d39ad4abcdd7e4e84e6733c2add765`；最终重启重读源码：`24f6db12490b7ba7f01099d311af97e926eeddd0`。原产品 `src` 树均相同。元数据见 [manifest.json](manifest.json)，范围与首轮失败见[验证报告](../../docs/F2/MaterialOnlyDemoValidation-20261018.md)。

独立库及会话保留在本次私有目录，服务目前停止。恢复原同一库使用[材料演示说明](../../docs/demo/MaterialOnlyDemo.md)的 serve 命令，不再次 setup。会话无自动过期，后续撤销/清理另行确认。
