# RUNBOOK · 靶场（srv2 上的 7 台 DVWA 类环境）

> 这份文档解决一件事：**机器重装/容器被删之后，怎么把这 7 台靶场原样装回来。**
> 所有数字都是 2026-10-18 09:34 在 `secagent-srv2`（43.143.114.79，Ubuntu 22.04）上实跑出来的，不是猜的。

## 0. 三条铁律

1. **靶场一律不加 `-p`。** 容器只挂在 `labnet` 内网上，宿主机只用 nginx 反代到 `127.0.0.1:8081~8087`。公网入口为零——这是整个方案能被接受的前提。
2. **容器之间用静态 IP 互认，不用容器名。** 宿主机不解析 docker 容器名（`getent hosts lab-dvwa` 返回空，`127.0.0.11` 的 DNS 只在容器网络命名空间里），所以 nginx 里写死 `172.20.0.1x`。
3. **镜像源必须走腾讯云内网镜像站。** 直连 `index.docker.io` 会超时（实测 `docker search` → `dial tcp 157.240.18.18:443: i/o timeout`），`/etc/docker/daemon.json` 里已配 `"registry-mirrors": ["https://mirror.ccs.tencentyun.com"]`，**别删这一行**。

## 1. 现状（7 台，全部 `Up`）

| 容器 | 镜像 | 大小 | 静态 IP | 宿主机端口 | 标题 / 账号 |
|---|---|---|---|---|---|
| `lab-pikachu` | `area39/pikachu:latest` | 1.2 GB | `172.20.0.10` | 8081 | Pikachu 靶场 |
| `lab-dvwa` | `vulnerables/web-dvwa:latest` | 935 MB | `172.20.0.11` | 8082 | DVWA v1.10 · `admin` / `password` |
| `lab-juice` | `bkimminich/juice-shop:latest` | 531 MB | `172.20.0.12` | 8083 | OWASP Juice Shop（容器内 3000） |
| `lab-webgoat` | `webgoat/webgoat:latest` | 893 MB | `172.20.0.20` | 8084 | WebGoat · `webgoat-user` / `webgoat` |
| `lab-dvna` | `appsecco/dvna:sqlite` | 451 MB | `172.20.0.21` | 8085 | DVNA · `admin` / `admin123`（首次访问自行注册） |
| `lab-dsvw` | `appsecco/dsvw:latest` | 75.5 MB | `172.20.0.22` | 8086 | DSVW（无认证，单文件靶场） |
| `lab-webgoat` 自带 | 同 `lab-webgoat` | — | `172.20.0.20:9090` | 8087 | **WebWolf**（必须带 `/WebWolf/` 上下文路径） |

镜像合计约 **4.1 GB**；根分区 `40G`，当前用 `28G`、剩 `11G`（73%）。**再装同类靶场前先看 `df -h /`。**

`lab-webgoat` 一个容器同时提供 WebGoat（8080）和 WebWolf（9090），所以 7 台靶场只对应 6 个容器。

## 2. 拉取源与已知坑（这是这份文档存在的理由）

| 镜像 | 结果 |
|---|---|
| `webgoat/webgoat:latest` | ✅ 可拉。**坑**：镜像里没有 `curl`/`wget`，自带 healthcheck 永远 `unhealthy` ⇒ 起容器时必须加 `--no-healthcheck`，否则面板永远是红点 |
| `appsecco/dvna:sqlite` | ✅ 可拉（**必须带 `:sqlite` 标签**，`latest` 不存在） |
| `appsecco/dsvw:latest` | ✅ 可拉，只有 75 MB，最省资源 |
| `vulnerables/web-dvwa:latest` | ✅ 可拉 |
| `bkimminich/juice-shop:latest` | ✅ 可拉 |
| `area39/pikachu:latest` | ✅ 可拉（1.2 GB，最大） |
| `raymondluo/bwapp`、`bwapp/bwapp`、`dsvw/dsvw` | ❌ `error from registry: denied`（仓库不存在/已下架） |
| `webpwnized/mutillidae:www` | ❌ `failed commit on ref … unexpected commit digest … failed precondition`（镜像层校验失败，不是网络问题） |

**结论：bWAPP 没有可用镜像，所以第 6 台用 DSVW 顶替。** 如果哪天必须上 bWAPP，只有两条路：自己去 GitHub 拉源码用 `php:apache` 自建，或者换 `webpwnized/mutillidae` 的自建版本。

## 3. 重建步骤（逐条可复制）

```bash
# 0) 内网
sudo docker network inspect labnet >/dev/null 2>&1 || sudo docker network create --subnet 172.20.0.0/16 labnet

# 1) 老六台（无 -p，全部静态 IP）
sudo docker run -d --name lab-pikachu --network labnet --ip 172.20.0.10 area39/pikachu:latest
sudo docker run -d --name lab-dvwa    --network labnet --ip 172.20.0.11 vulnerables/web-dvwa:latest
sudo docker run -d --name lab-juice   --network labnet --ip 172.20.0.12 bkimminich/juice-shop:latest
sudo docker run -d --name lab-webgoat --network labnet --ip 172.20.0.20 --no-healthcheck webgoat/webgoat:latest
sudo docker run -d --name lab-dvna    --network labnet --ip 172.20.0.21 appsecco/dvna:sqlite
sudo docker run -d --name lab-dsvw    --network labnet --ip 172.20.0.22 appsecco/dsvw:latest

# 2) 反代（两层，缺一层就有端口打不开）
#    /etc/nginx/lab-local.conf           → 8081/8082/8083
#    /etc/nginx/conf.d/lab-tunnel-extra.conf → 8084(WebGoat)/8085(DVNA)/8086(DSVW)/8087(WebWolf)
#    且 /etc/nginx/lab-local.conf 首行必须有：include /etc/nginx/conf.d/lab-tunnel-extra.conf;
#    原因：主 nginx.conf 不 include conf.d，不加这一行新文件完全无效
sudo nginx -t && sudo nginx -s reload     # ← 不要用 systemctl

# 3) 校验
for p in 8081 8082 8083 8084 8085 8086 8087; do
  printf "%s " $p
  curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://127.0.0.1:$p/
done
```

**为什么 `nginx -s reload` 而不是 `systemctl reload nginx`**：这台机器的 `nginx.service` 是 **masked** 状态，nginx 实际由 `secagent-static.service` 以 `nginx -g daemon off` 托管；`systemctl reload nginx` 会报 `Failed to reload nginx.service: Unit nginx.service is masked.`

### 期望结果

| 端口 | 期望 |
|---|---|
| 8081 | `200`（Pikachu） |
| 8082 | `302 → /setup.php` 或 `/login.php`（DVWA；首次要跑 setup 建库） |
| 8083 | `200`（Juice Shop SPA） |
| 8084 | `302 → /WebGoat/` |
| 8085 | `302 → /login` |
| 8086 | `200`（DSVW） |
| 8087 | `302 → /WebWolf/` |

## 4. 访问方式（本机）

靶场只在服务器回环上开，所以要在本机建隧道：

```bash
ssh -N \
  -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 \
  -L 8084:127.0.0.1:8084 -L 8085:127.0.0.1:8085 -L 8086:127.0.0.1:8086 \
  -L 8087:127.0.0.1:8087 ubuntu@43.143.114.79
```

Windows 上双击 `F:\7AAA\AI\blog\scripts\打开靶场.cmd` 等价（里面带 `ServerAliveInterval=30`，断线自愈）。

打开后浏览器访问 `http://127.0.0.1:8081` … `http://127.0.0.1:8087`。
**WebWolf 必须访问 `http://127.0.0.1:8087/WebWolf/`**——根路径是 Tomcat 404，nginx 里虽然做了 `location = / { return 302 /WebWolf/; }` 兜底，但直接写全路径最省事。

## 5. 重置靶场

- **DVWA 数据库被玩坏**：`sudo docker restart lab-dvwa` 后访问 `/setup.php` → "Create / Reset Database"。
- **Juice Shop 进度**：进度存在容器内，`docker restart lab-juice` 不一定清；要彻底干净就 `docker rm -f lab-juice` 再按第 3 节重跑。
- **DSVW / DVNA / WebGoat / WebWolf**：默认无持久化状态，重启即恢复。
- **不要**为了重置去 `docker system prune`——那会把 `secagent` 的镜像一起删掉（同机还跑着生产容器）。

## 6. 安全边界（别越线）

- 这些靶场**故意**有洞（命令注入、SQLi、XSS、反序列化）。它们只在 `labnet` 内网 + 服务器回环可达，**任何情况下不要**加 `-p 0.0.0.0:...`、不要把它们放进公网 nginx 的 `server_name`、不要给它们配证书。
- 云镜对 `lab-dvwa` 的 `exec/source/*.php` 报过 3 条 `Php.Trojan.*`（启发式误报：DVWA 自带 `shell_exec('ping '.$target)`）。已在腾讯云控制台按 **文件 MD5** 加白（`a2f686b7…`、`698a1add…`、`f7201702…`），生效主机只勾 `10.0.0.10`。**容器重建后 MD5 不变**（镜像层固定），所以白名单不会失效。

## 7. 变更记录

- 2026-10-17：搭 `labnet`，上 Pikachu(8081)/DVWA(8082)/Juice Shop(8083)；`lab-local.conf` 建立；停用并删除 `lab-gate.service` 公网门禁。
- 2026-10-18 09:34：加 WebGoat(8084)/DVNA(8085)/DSVW(8086)；新建 `conf.d/lab-tunnel-extra.conf` 并在 `lab-local.conf` 首行加 `include`；bWAPP 尝试失败（三个镜像源 `denied`）改用 DSVW。
- 2026-10-18 09:36：WebWolf 上线 8087（同一 `lab-webgoat` 容器的 9090）；`/lab/` 页从六台更新到七台。
