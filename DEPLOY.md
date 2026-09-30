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
| 阿里云 OSS / 腾讯云 COS | 中，按量付费 | 几毛钱/月 | 最快 |

`_headers` 文件里的缓存策略 Netlify 和 Cloudflare Pages 会自动识别，GitHub Pages 会忽略它。

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
