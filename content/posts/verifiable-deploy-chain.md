---
title: "把部署链做成「造不了假」：CI → ACR → digest → 看门狗"
date: 2026-10-13
draft: false
tags: ["部署", "供应链", "Docker", "CI", "可核验", "工程实践"]
categories: ["ai笔记"]
summary: "一个容器跑起来，你怎么知道跑的就是你刚推的那个 commit？这条链上我封了五道闸门：触发即校验、jar 内指纹核对、镜像 digest 而不是 tag、部署前后的硬校验、以及一个会自己回滚的看门狗。"
description: "把发布链做成可核验的：CI 校验工作区与 commit、解包核对 jar 内 git.properties、ACR 用 digest 而不是 tag、部署脚本硬校验 label、健康看门狗自动回滚。全部数字来自 SecAgent 的 RUNBOOK 与真实输出。"
ShowToc: true
---

## 先说问题：你为什么"看不出来"

容器化的发布链有一个特别讨厌的性质：**它出错的时候看起来和成功一模一样。**

`docker ps` 里 `Up (healthy)`、`/api/health` 返回 `status: ok`、
页面能打开 —— 但线上跑的可能是三天前的镜像，因为：

- 你用的是 `:stable` 这种**可变 tag**，某个环节重新推过一次；
- 构建的时候工作区是脏的，jar 里的 commit 和触发构建的 commit **不是同一个**；
- 部署脚本只比对了"tag 变没变"，而**容器存在但没在运行**的情况下它会判"无需变更"然后安静退出。

这三条我在自己这套系统上**全都真的踩到了**。第三条直接造成过一次约 6 分钟的全站 502
（复盘写在[另一篇](/posts/incident-502-postmortem/)里）。

所以这一篇讲的是：**怎么把这条链做成"造不了假"。** 核心思路只有一句 ——

> 每一个环节都留一个**别人能独立核对**的证据，而不是一句"我部署成功了"。

---

## 五道闸门，从源码到线上

```
GitHub（源码）
  │ push main / 打 tag / 手动触发
  ▼
GitHub Actions  .github/workflows/build-image.yml
  │  ① 构建前校验：工作区干净 + HEAD == 触发 commit（不符即中止）
  │  ② mvn test 全量 → mvn -DskipTests package
  │  ③ 解包校验 jar 内 git.properties（commit 必须 == 触发 commit、dirty=false）
  │  ④ docker build -f Dockerfile.runtime \
  │       --label revision=<commit> --label artifact-md5=<md5>
  │  ⑤ 推 ACR 两个 tag：<commit短号>（不可变）与 stable（发布指针）
  ▼
阿里云 ACR
  │  srv1 只持【只读】凭据
  ▼
srv1  systemd timer 每 5 分钟 → scripts/srv1-redeploy.sh
     flock 串行 → 读 stable 的 digest → 与当前运行 digest 比对（相同则安静退出）
     → docker pull <registry>/<repo>@<digest>（不可变产物）
     → 硬校验：label revision 存在且与期望 commit 一致
     → compose 用 digest 重建 → /api/health 要求 status=ok
        且 fingerprintMismatch=false
        且 embeddedGitCommit == revision
        且 artifactMd5 == label
     → 通过才写 last-known-good.json；不通过回滚上一个镜像并报错退出
```

下面逐道说清"它在防什么"。

### 闸门 ①：构建前校验"工作区干净 + HEAD == 触发 commit"

对应的失败模式很朴素：**你推的 commit 和你构建的代码不是同一份。**

多个人同时推、或者 CI 触发之后又有人合了一个 commit，
"构建成功了但产物对不上源码"这件事就发生了 —— 而且它**不会报任何错**。

所以 CI 的第一步不是编译，而是核对：

- `git status --porcelain` 必须为空（工作区干净）；
- `git rev-parse HEAD` 必须等于触发这次构建的那个 commit。

不满足就直接中止。**宁可这一轮不发布，也不要发布一个说不出身世的产物。**

### 闸门 ②：`mvn test` 全量跑完才允许打包

这一条看起来是废话，但它有一个具体的教训：

> 有一次 CI 是**绿的**，线上却起不来 —— 因为单测直接 `new` 了那两个类，
> 根本没加载 Spring 上下文，所以"两个构造器都没标 `@Autowired`"这种
> **启动期才会炸**的问题单测抓不到。

修法不是"以后小心点"，而是补一道**结构门禁**：新增
`SpringBeanConstructorTest`，用反射扫描所有 Spring 组件，
要求"多构造器时**恰好**一个带 `@Autowired`"。它上线当场又抓出了第二个类 ——
这说明这道门禁是有价值的，不是一个安慰剂。

### 闸门 ③：解包核对 jar 内 `git.properties`

镜像 tag 可以被人手动改、可以被重新推。所以真正的硬证据放在**产物内部**：

构建完之后把 jar 解开，读里面的 `git.properties`：

- `git.commit.id` 必须等于触发这次构建的 commit；
- `git.dirty` 必须是 `false`。

这是"这个 jar 是从哪份源码编出来的"唯一不可伪造的答案 ——
因为它在编译期被写进了 jar 里，改它就得重新编译。

### 闸门 ④⑤：镜像打 label，并且**用 digest 发布**

```
docker build -f Dockerfile.runtime \
  --label revision=<commit> \
  --label artifact-md5=<md5>
```

然后同时推两个 tag：

| tag | 性质 | 用途 |
|---|---|---|
| `<commit 短号>` | **不可变** | 溯源：任何一个线上容器都能对应回一个 commit |
| `stable` | 可变，是**发布指针** | 部署脚本只认它 |

部署时**不要用 tag 拉镜像，用 digest 拉**：

```bash
docker pull <registry>/<repo>@sha256:5cdfce96...69e0
```

理由是 tag 可变、digest 不可变。实测里同一组凭据通过 ACR 的**公网地址**与
**VPC 内网地址**读到的 digest **完全一致**（`sha256:5cdfce96…`），
这本身就是一次"两个独立路径互相印证"。

### 部署侧：`flock` 串行 + digest 比对 + 健康硬校验

服务器上每 5 分钟跑一次 `srv1-redeploy.sh`：

```bash
# 只看判断、不动容器（演练/排障首选）
sudo bash /opt/secagent/scripts/srv1-redeploy.sh --dry-run
# 一键回滚到 last-known-good
sudo bash /opt/secagent/scripts/srv1-rollback.sh --dry-run   # 先看
sudo bash /opt/secagent/scripts/srv1-rollback.sh             # 再动
```

三个设计点值得单独说：

**（a）`flock` 串行，不是"尽力而为"。** 锁文件是
`/var/lock/secagent-deploy.lock`，用 **内核级 flock**：进程被杀会自动释放，
不需要"清理陈旧锁"这种逻辑。实测并发行为：

| 场景 | 结果 |
|---|---|
| 锁被占用时 `--lock-timeout 0` | **立刻**退出 2（耗时 0s） |
| 锁被占用时 `--lock-timeout 60` | 等了 10s 拿到锁后继续 |

**（b）digest 相同就安静退出 —— 但这是有代价的。** 它让 no-op 只花一次远端
manifest 查询，所以"5 分钟一次"不浪费：它同时是**最长 5 分钟的发布延迟**，
也是**每 5 分钟一次的漂移检测**。反过来说法也成立：**发布延迟本身就是漂移检测频率。**

**（c）健康校验必须是"硬"的，而且要比对到具体字段。**
`/api/health` 返回的东西里，我要求四件事同时成立：

```
status == "ok"
fingerprintMismatch == false
embeddedGitCommit == 期望的 revision
artifactMd5 == 镜像上的 label artifact-md5
```

这四个字段里有两个是**硬证据**：`embeddedGitCommit` 是 jar 内固化的 commit，
`artifactMd5` 是镜像里那个 jar 的 MD5。而 `buildSha` 只是**环境变量自述**，
接口自己在响应里就标注了"非证据、不参与指纹核对"——
**把自述和证据分开标出来**，是这个接口设计上最值得抄的一点。

---

## 演练：怎么在不换线上容器的前提下验证这套东西

改了发布链却不敢试，等于没改。这套脚本专门为此设计了"不碰容器"的验证方式：

```bash
# ① 纯函数自测（不需要 docker、不碰容器）
bash scripts/srv1-redeploy.sh --self-test
# ② 用任意 tag 当"指针"，只验证读取与比对判断
sudo bash /opt/secagent/scripts/srv1-redeploy.sh --tag civtest --dry-run
# ③ 并发互斥验证：第二个实例必须被 flock 挡住
sudo bash /opt/secagent/scripts/srv1-redeploy.sh --lock-timeout 0
# ④ 回滚脚本的前置条件（无 last-known-good 时必须 fail-closed）
sudo bash /opt/secagent/scripts/srv1-rollback.sh --dry-run
```

实测（2026-10-12，srv1）：

| 项 | 结果 |
|---|---|
| 指针拉到不存在的 tag | 如实报错退出 1（**不是**假装成功） |
| 指针指向存在的 tag | 判"需要部署"，退出 0，**容器未动** |
| 无 `last-known-good.json` 时回滚 | 退出 3（**fail-closed**） |
| `last-known-good.json` 内容非法（digest 形状不对） | 退出 3 |
| 演练全程线上容器镜像 ID | `sha256:1491753002e15cca…aadbd8` **未变**，`Up (healthy)` |

**注意最后一行。** "演练没出事"不是靠运气，是靠一个可核对的事实：
**容器镜像 ID 没变**。任何一次"我只是 dry-run 了一下"都应该能给出这种证据。

---

## 看门狗：补上"部署后起来才不健康"这一格

上面那套能防"部署错版本"，但防不了另一类：**版本对、代码有 bug、容器起不来。**

所以加了一个 `healthwatch`：连续 N 次不健康就自动回滚，
并且回滚点用的是部署成功时写下的 `last-known-good.json`。

它当天就发挥了作用 —— 那次 502 事故里，`healthwatch` 记下了「不健康 1/3」，
成了复盘时间线上的第一个客观事件。完整的四缺陷分析在
[那篇复盘](/posts/incident-502-postmortem/)里。

---

## 那些"看起来更省事"的做法，为什么不能用

| 做法 | 为什么不用 |
|---|---|
| 用 `:stable` tag 直接部署 | tag 可变，攻击面/误操作面同时打开；要用 **digest** |
| 用 `latest` | 更糟，连"上一次是什么"都说不出来 |
| 只看 `docker ps` 判断健康 | 容器"存在但没运行"时它照样能骗过你（真的发生过） |
| 把可推送凭据放到线上服务器 | 线上只应持**只读** registry 凭据；能推就能投毒 |
| 靠"我记得我推了" | 记忆不是证据；`revision` label + jar 内 `git.properties` 才是 |

最后一条在实测里还有一个反向验证：ACR 个人版的 registry API
**拒绝对 tag 执行 DELETE**（即使申请了 `pull,delete` scope 也一样，
`docker manifest rm` 对单架构 manifest 只会报 `No such manifest`）。
也就是说 srv1 上那份凭据"能 push 不能 delete"——
**这件事本身就是"不该把可推送凭据放上去"的又一条理由**，
而它是我在试图清理演练用的测试 tag 时发现的：
**遗留状态是 ACR 里还有两个测试 tag，需要到控制台手工删。** 这一条我写在这里，不假装它不存在。

---

## 小结：可核验清单

想抄这套东西，按下面这条清单逐项落，缺一项都会留一个"看不出来"的缺口：

1. 构建前：工作区干净 + HEAD == 触发 commit；
2. 打包后：解包核对 jar 内 `git.properties`；
3. 镜像上：`revision` 与 `artifact-md5` 两个 label；
4. 发布时：**digest** 而不是 tag；线上只持只读凭据；
5. 部署后：`/api/health` 四个字段硬校验，区分"自述"与"硬证据"；
6. 失败时：fail-closed 退出码（3 = 没有可用回滚点），而不是继续跑；
7. 演练时：给出"线上容器镜像 ID 未变"这种可核对的证据。

> **一句话**：可核验不是"我相信它部署对了"，而是"任何人拿四个字段就能自己核对一遍"。

---

*本文里的端口、路径、退出码、digest 与时间戳都来自本项目的 `RUNBOOK.md` 与真实命令输出，没有估算值。*
