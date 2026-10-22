# 回执提示 CSS 四态：run25 限定通过

实际源码 `257341af6b3e57bbb1bb278e4834e7e525e70b22`；[run25 / attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39805195077)，job `119916438725`。完整原HTML/JS在正常sandbox Chrome155.0.8059.39运行，使用明确标记的合成同源GET回放；没有产品API、数据库、模型或业务POST。

## 实际结果

1200px、390px分别完成原页面四态：空提示→原JS待核对提示→原JS恢复成功提示→清空重绘。修前空段28px/左边框3px；修后与再清空均0px、margin/padding/border0且透明，DOM和aria-live=polite仍在。非空段保留原装饰，1200px两提示52.5px、390px两提示77px，文字完整可见未裁剪、当时document无横溢。共9个几何观察（含修前1），不是9条业务测试。

目标提示的四次原CDP观察均含唯一#receipt-submit-status，文字SHA与字符集合精确匹配，缺字/非法字体来源为空。参与的官方原字体SHA256为2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b，原许可/固定commit/大小/blob校验保留。它证明目标及当时视口节点的实际字体参与与原charset覆盖；不证明逐字形到码点归属、整页全部像素或读屏播报。

浏览器同源GET17次，服务端精确GET17次，0POST，unexpected_GET/pageerror/越界均0。浏览器拦同scheme/host/port及GET/次数，服务端只建模精确路径，其他404并使终态失败；没有声称浏览器按路径白名单逐条拦截。browser_close=CLOSED、cleanup_errors=[]、自有HTTP监听REFUSED。UI含清理5.575935秒，发布扫描5.583秒，原90/360秒及10minjob门未扩大。

五张原PNG已逐张查看：01有空绿条，02无空条，03窄屏待核对文字完整，04成功提示完整且显示受控回执，05清空后无装饰空条。前后截图滚动位置不同，不作叠图像素比较；五张图不代表所有状态均各有独立截图，两视口四态由原result几何/文字和CDP记录支持。

## 原件与终态

artifact.zip为官方原ZIP，469452B，SHA256 defe51b1af218e2c7b245916ff19c59f274c6d2915eebb84027b93aabb96cef8，六成员598023B（五PNG+result.json），解包原件逐字一致。ci-original.log为官方job API解码全文241085B，SHA256 05937a05cb97f893af07e70b4ee5c9bdfd1453495d8a359eb64d8e3af1283146，归档后与API字符内容逐字读回相等，包含最终观察及完整job收尾，不是CLI截断导出。run/job API、artifact元数据同时保留；validation、归档校验脚本、checksums及5项纯注入guard记录是派生材料。

result.json为PASS，官方job及浏览器step success/脚本exit0。stdout PENDING_FINALIZATION不当最终PASS。未见summary上传中止日志，但summary正文未独立读取。

原本地sandbox失败、run24 FAIL及其404/截图/close错误原件均原样保留；本轮仅run25一次，无自动连跑。CSS外HTML/JS字节一致，原CSP与sandbox未放松。5项纯注入target守卫检查单列，不累加为浏览器/业务测试；未重跑collection或大suite。

本切片关闭回执空条及四态CSS回放门，不转签AT35、真实业务回执恢复、wheel安装态、服务冷重启、手机实机、Windows原生、LIVE或C0；正式来源与原授权门仍独立。
