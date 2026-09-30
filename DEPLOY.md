# 部署与更新

## 当前部署状态

已部署到 GitHub Pages，永久地址：

**https://ginin0427.github.io/xian-page/**

| 项目 | 值 |
| --- | --- |
| 仓库 | https://github.com/Ginin0427/xian-page |
| 分支 | `main` |
| Pages 来源 | `main` 分支根目录 |
| 本机 git 身份 | Ginin0427 `<Ginin0427@users.noreply.github.com>` |
| 网站体积 | 约 3.1 MB |

## 更新页面（以后每次改图都走这个流程）

```bash
cd /Users/chenyangzi/Documents/Codex/2026-09-30/xian/outputs
python3 tools/build.py     # 重新扫描 assets/ 生成 index.html
git add -A
git commit -m "更新切图"
git push
```

推送后 GitHub 会自动重新构建，1–2 分钟生效。地址不变。

如果只想看本地效果，不用推：

```bash
python3 -m http.server 8000
# 打开 http://localhost:8000
```

## 查看部署状态

```bash
gh api /repos/Ginin0427/xian-page/pages/builds/latest --jq '.status'
# building / built / errored
```

也可以在仓库页面点 **Actions** 标签看每次构建。

## 其他托管方案

| 方案 | 上手难度 | 免费额度 | 大陆访问 |
| --- | --- | --- | --- |
| GitHub Pages（当前） | 中 | 100GB/月 | 一般 |
| Netlify Drop | 最低，拖文件夹 | 100GB/月 | 时好时坏 |
| Cloudflare Pages | 低，拖文件夹 | 不限流量 | 一般 |
| 阿里云 OSS / 腾讯云 COS | 中，按量付费 | 几毛钱/月 | 最快，但需备案域名，见下 |

`_headers` 文件里的缓存策略 Netlify 和 Cloudflare Pages 会自动识别，GitHub Pages 会忽略它。

## 关于「国内访问快」：先说清门槛

**阿里云 OSS、腾讯云 COS 的默认域名不能直接当网页浏览。** 从 2022 年起，用 `xxx.oss-cn-shanghai.aliyuncs.com` 这类默认域名访问 html 文件会被强制下载（`Content-Disposition: attachment`），而不是在浏览器里渲染。这是配合备案政策做的限制，不是配置问题。

所以「国内快」真正的门槛是**备案**，只有两条路：

### 路线一：备案域名 + OSS（长期方案）

| 步骤 | 花费 | 时间 |
| --- | --- | --- |
| 买域名（阿里云万网） | 约 50 元/年 | 立即 |
| ICP 备案（个人） | 免费 | 3–20 个工作日 |
| 创建 OSS Bucket、上传、开静态网站 | 存储+流量几毛/月 | 20 分钟 |
| 绑定域名、开 CDN | CDN 流量另计 | 20 分钟 |

一劳永逸，之后更新还是 `git push` 之后同步一份上去即可。

### 路线二：轻量应用服务器 + IP 访问（不备案）

国内服务器的 **IP 直接访问不需要备案**（80/443 端口会被拦，用 8080 这类端口即可）。成本约 24–40 元/月，需要配 nginx，我可以帮你配。

适合临时或中短期使用，但每月都在花钱，而且要运维。

### 要不要走这条路？

先问自己：**分享对象是不是真的都在国内，而且不能接受 GitHub Pages 的速度？**

- 如果只是发给几个同事偶尔看看 → GitHub Pages 够用，不值得备案
- 如果是给客户长期展示的门面 → 值得走路线一

### 如果决定上 OSS，我可以代做

用阿里云官方 CLI `ossutil` 上传，一条命令同步整个目录：

```bash
ossutil cp -r outputs oss://你的bucket/ --update
```

需要的凭证建议用 **RAM 子账号**，只授予 OSS 权限（比主账号 AccessKey 安全得多），用完直接删掉子账号即可。不要在聊天里发主账号的 AccessKey。

## 常见问题

**推送报 `RPC failed; HTTP 400`**

本机已配好 `http.version=HTTP/1.1` 和 500MB 的 `http.postBuffer`，这是网络链路对分块传输不友好的经典问题。换网络环境后如果复发，检查这两个配置是否还在：

```bash
git config --get http.version
git config --get http.postBuffer
```

**图片更新了但线上还是旧的**

浏览器缓存。GitHub Pages 的图片缓存较短，强制刷新（`⌘⇧R`）即可。若换了文件名，`build.py` 会自动改用新文件，不存在缓存问题。

**仓库体积**

GitHub 单文件上限 100MB，仓库建议控制在 1GB 以内。当前 3.1MB 很安全。原图（PNG）已移到 `../png-originals/`，不在仓库里，避免仓库变重。
