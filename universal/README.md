# Universal Subtitle Extractor（通用字幕提取器 · AI Agent 专用）

> 在 [bilibili-ai-subtitle-extractor](https://github.com/Guojiz/bilibili-ai-subtitle-extractor) 的 B 站 API 流程基础上，扩展为**通用网页字幕提取**。无 UI、无打扰，字幕数据通过 `window.__USE__` API 暴露，供 AI Agent / 浏览器自动化直接读取。
> 通用嗅探与站点规则的思路借鉴了沉浸式翻译（immersive-translate）开源的油猴脚本 `video-subtitle/inject.js` 及其站点配置。

## 提取路径（四层，自动叠加）

| 层级 | 覆盖范围 | 原理 |
|---|---|---|
| 1. 站点主动提取 | Bilibili | `view` → `dm/view` → 字幕 JSON 的官方 API 流程，页面上下文执行自带登录态；人工/UP 主字幕优先，AI 字幕后补 |
| 1. 站点主动提取 | YouTube | `#movie_player.getPlayerResponse()` / `ytInitialPlayerResponse` 的 `captionTracks`，拉取 `fmt=json3` |
| 2. 网络嗅探 | 任意站点 | Hook 页面 `fetch` 与 `XMLHttpRequest`，命中字幕 URL 特征（`.vtt/.srt/.ttml/.dfxp/.ass`、`/api/timedtext`、`/subtitles/`、`aisubtitle.hdslb.com` 等）或字幕 Content-Type 时克隆响应解析 |
| 3. textTracks | 使用原生字幕的播放器 | 枚举 `video.textTracks`，disabled 轨道切 `hidden` 触发加载后读取 cues |
| 4. `<track>` 标签 | 静态声明字幕的页面 | 直接抓 `track[src]` 解析 |

同一字幕从多条路径被发现时自动去重（api > tracktag > texttrack > network）。SPA 站内跳转自动清空并重扫。

## 安装（三选一）

**A. 油猴脚本**（最简单）：先运行 `node build.js` 生成 `dist/universal-subtitle-extractor.user.js`，Tampermonkey / Violentmonkey 新建脚本并粘贴全文。

**B. MV3 扩展**：先运行 `node build.js` 生成 `extension/injector.js`，然后 Chrome → `chrome://extensions` → 开发者模式 → 加载已解压的扩展程序 → 选择 `extension/` 目录。

**C. Playwright / Agent 浏览器注入**（自动化场景，无需装任何东西）：

```python
context.add_init_script(path="universal-subtitle-extractor.user.js")
```

## API：`window.__USE__`

在页面控制台或 `page.evaluate()` 中调用：

| 方法 | 返回 | 说明 |
|---|---|---|
| `list()` | `[{id, site, url, lang, label, format, source, isAI, cueCount, duration}]` | 已发现的字幕轨道（不含正文） |
| `best()` | `id \| null` | 最优轨道（人工 > AI，api > 嗅探） |
| `get(id?)` | track（含 `cues`） | 不传 id 自动取最优；`cues = [{start, end, text}]` 秒为单位 |
| `text(id?, opts?)` | string | 整理后的可读文本，碎片已合并分段；`opts: {timestamps, gap=1.5, paragraphLength=260}` |
| `srt(id?)` / `vtt(id?)` | string | 标准 SRT / WebVTT |
| `meta()` | `{site, title, desc, duration, ...}` | 视频元信息，B 站含简介（章节时间轴在 `desc` 里） |
| `waitFor(n=1, ms=15000)` | `Promise<number>` | 等到至少 n 条轨道，供自动化等待 |
| `scan()` | — | 手动重扫（网络嗅探本身持续进行） |
| `parse(text, url?)` | `{format, cues}` | 直接解析任意字幕文本（vtt/srt/ttml/json3/B站JSON 自动识别） |

AI Agent 典型用法：

```python
page.goto(url)
page.evaluate("window.__USE__.waitFor(1, 20000)")
tracks = page.evaluate("window.__USE__.list()")   # 让用户/Agent 选轨道
text   = page.evaluate("window.__USE__.text()")   # 最优轨道的整理文本
```

## 实测踩过的坑（已修，已合并进根目录 SKILL.md「失败处理」）

1. **Mixed Content**：B 站 `dm/view` 返回的 `subtitle_url` 常是 `http://`，HTTPS 页面内直接 fetch 会被浏览器拦截，必须先升级为 `https://`（curl 无此限制，所以纯 HTTP 流程发现不了）。
2. **`Access-Control-Allow-Origin: *` + 带 Cookie = 浏览器拒收**：B 站字幕 CDN（`aisubtitle.hdslb.com`）返回 `ACAO: *`，请求若带 `credentials: 'include'` 会被 CORS 规则直接拒绝（报 `TypeError: Failed to fetch`，毫无提示）。**字幕文件下载必须 `credentials: 'omit'`**；只有 `api.bilibili.com` 的接口需要带 Cookie。
3. B 站对新会话偶尔返回「出错啦」页并二次跳转，自动化脚本要容忍导航导致的执行上下文销毁。

## 文件结构

```
src/injector.js        # 唯一源码（页面层，IIFE）
build.js               # node build.js 重新构建（生成 dist/ 和 extension/injector.js）
extension/manifest.json
tests/                 # Playwright 实测脚本 + 本地测试页
```

`dist/universal-subtitle-extractor.user.js` 和 `extension/injector.js` 是构建产物，不提交仓库，clone 后运行 `node build.js` 生成。

## 已知限制

- YouTube 的 `captionTracks` 路径按官方播放器结构实现并已通过 json3 解析器单元测试，但本环境无法访问 YouTube，建议在你的网络里实测一个带字幕的视频。
- Netflix 等 DRM 站点需要 hook `JSON.parse` 抓 `timedtexttracks`（沉浸式翻译的做法），暂未实现，欢迎 PR。
- 直播实时字幕（`type: live`）不在本版范围。

License: MIT
