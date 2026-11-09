# 热点 IP 档案快照（`static/api/public/ip/`）

这些 `<ip>.js` 是 **真实接口响应的原样拷贝**，用于让 `/ip/` 页面在隧道很慢时也能秒开热点 IP。

- 生成脚本：`scripts/snapshot-ip-dossiers.py`，**在 srv1 上跑**（`http://127.0.0.1:9900` 直连 API，不经过 Cloudflare 隧道）：

  ```bash
  scp scripts/snapshot-ip-dossiers.py secagent-srv1:/tmp/snap_ip.py
  ssh secagent-srv1 "python3 /tmp/snap_ip.py --limit 20"
  scp secagent-srv1:/tmp/xkip.tar.gz .
  tar -xzf xkip.tar.gz -C /tmp && cp /tmp/xkip/*.js static/api/public/ip/
  ```

- 为什么要快照：`https://demo.xiaokeqing.cn/api/public/ip.js` 经隧道，实测「大于约 1 KB 的响应」只有 ~600 B/s，浏览器里 26 s 也拿不到；而 Vercel 上的静态文件 36 KB 只要 0.9 s。
- 页面取数顺序：**静态快照 `/api/public/ip/<ip>.js` → 同源 `/api/public/ip.js?q=`（Vercel rewrites 反代）→ `data-wb-api` 直连 demo 域**；三级都失败就照实写「读不到」，不补数、不造样例。
- 口径：文件名就是 IP；内容里的 `data.generatedAt` 是**快照时间**，页面必须照实标注来源与时间，不能伪装成实时。
- 刷新：热点 IP 会变，建议每次重大改动或每周手动重跑一次上面的命令并提交（一次约 10 个文件、40–60 KB）。
