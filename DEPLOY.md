# 部署成永久公网链接

静态站点没有后端，任何静态托管都能直接跑。下面按「省事程度」排。

## 方案对比

| 方案 | 上手难度 | 免费额度 | 大陆访问 | 要不要账号 |
| --- | --- | --- | --- | --- |
| Netlify Drop | 最低，拖文件夹 | 100GB/月 | 时好时坏 | 要，邮箱即可 |
| Cloudflare Pages | 低，拖文件夹 | 不限流量 | 一般，晚上较慢 | 要 |
| GitHub Pages | 中，要会 git | 100GB/月 | 一般 | 要 |
| 阿里云 OSS / 腾讯云 COS | 中 | 按量付费，几毛钱 | 最快 | 要，且需实名 |

**给国内同事看的话，纯免费方案都不算稳。** 要稳定快速就得用国内对象存储，用它们自带域名（`xxx.oss-cn-shanghai.aliyuncs.com`）不需要备案；绑自己的域名才要。

---

## 一、Netlify Drop（推荐先试这个）

1. 打开 [app.netlify.com/drop](https://app.netlify.com/drop)
2. 把整个 `outputs` 文件夹拖到页面中间的虚线框里
3. 等几秒，出现形如 `random-name-123.netlify.app` 的网址，此时已经能访问
4. 点页面上的 **Claim your site**，用邮箱或 GitHub 注册/登录，这个网址就永久归你了
5. 想改名字：Site configuration → Change site name → 换成 `your-brand.netlify.app`

**以后怎么更新**：还是打开 drop 页面，把文件夹再拖一次，选覆盖同名站点即可。或者登录后台，在 Deploys 里拖入新的 zip。

`_headers` 文件已经放在目录里，Netlify 会自动识别并套用缓存策略，不用额外配置。

## 二、Cloudflare Pages

1. 打开 [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages → Create → Pages → Upload assets
2. 项目名填一个，把 `outputs` 文件夹拖进去 → Deploy
3. 得到 `your-project.pages.dev`

不用绑卡，流量不限，比 Netlify 的免费额度大。`_headers` 同样支持。

## 三、GitHub Pages

适合要版本管理、要多人协作的情况，步骤最多。

```bash
cd /Users/chenyangzi/Documents/Codex/2026-09-30/xian/outputs
git init
printf 'node_modules/\n.DS_Store\n' > .gitignore
git add .
git commit -m "init"
git branch -M main
git remote add origin git@github.com:<你的用户名>/<仓库名>.git
git push -u origin main
```

然后在仓库页面 Settings → Pages → Source 选 `Deploy from a branch` → 分支 `main`、目录 `/ (root)` → Save。

一两分钟后访问 `https://<你的用户名>.github.io/<仓库名>/`。

注意：仓库是公开的，且单文件不能超过 100MB。图片多的话仓库会变得很重，这种情况更适合用对象存储。

## 四、国内访问要快：阿里云 OSS / 腾讯云 COS

1. 开通 OSS（对象存储），创建一个 Bucket，读写权限设为**公共读**
2. 上传 `outputs` 里的所有文件（保持目录结构）
3. 打开「静态页面」，默认首页填 `index.html`
4. 访问 `https://<bucket>.oss-cn-<region>.aliyuncs.com/index.html`

用自带域名不需要备案，几十 MB 的存储加流量一个月几毛钱。国内打开基本是秒开。

---

## 更新页面的流程

改完图之后本地跑一次，再上传：

```bash
cd /Users/chenyangzi/Documents/Codex/2026-09-30/xian/outputs
python3 tools/build.py
```

确认本地预览没问题，再把整个文件夹重新拖到托管平台覆盖。

因为是覆盖而不是新文件，浏览器可能缓存旧图。`_headers` 里已经设成 1 小时过期，最多 1 小时后所有人都会看到新版；着急的话让对方强制刷新（`⌘⇧R`）。

## 别用临时隧道当长期方案

`cloudflared tunnel --url` 那种 `*.trycloudflare.com` 地址是临时的：随时可能断，重启就换新地址，Cloudflare 官方也说明没有可用性保证。只适合临时给谁看一眼，不能当正式发布。
