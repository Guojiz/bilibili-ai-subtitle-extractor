---
name: bilibili-ai-subtitle-extractor
description: 面向任意 AI Agent、浏览器自动化工具或脚本执行环境的 B站字幕读取流程。当用户提供 B站视频链接并要求提取字幕、视频转文字、获取视频内容、整理文稿、翻译字幕或总结视频时，优先使用本流程。先确认目标语言，人工字幕 / UP 主字幕优先，B站 AI 字幕作为没有人工字幕时的后补方案。不要优先下载视频，不要优先使用 ASR。只要运行环境能访问网页、操作浏览器或发送 HTTP 请求，就可以执行。
---

# B站字幕提取流程

本文件不是某一个平台专用的 ChatGPT Skill，而是一份平台无关的 Agent Recipe。

它适用于任何具备以下能力之一的系统：

- 能访问网页
- 能操作浏览器
- 能发送 HTTP 请求
- 能读取 JSON
- 能把短字幕整理成自然段文本

## 触发条件

当用户发送 B站视频链接，并提出以下请求时，优先使用本流程：

- 帮我提取这个视频的字幕
- 把这个视频内容转成文字
- 获取这个 B站视频内容
- 翻译这个 B站视频
- 整理这个视频文稿
- 总结这个视频
- 根据视频字幕做笔记

典型链接形态：

```text
https://www.bilibili.com/video/BVxxxxxxxxxx
https://b23.tv/xxxxx
bilibili.com/video/BVxxxxxxxxxx
```

如果是短链接，先通过浏览器或 HTTP 重定向解析到正式 B站视频链接。

## 总原则

1. 先确认用户需要的字幕语言。用户没有明说时，按用户当前对话语言或任务目的推断；如果是翻译任务且目标语言不明确，先询问目标语言。
2. 优先读取 Bilibili 已有字幕数据。
3. 在同一目标语言下，人工字幕 / UP 主字幕优先，B站 AI 字幕作为后补。
4. 如果已经存在质量较好的目标语言字幕，不要再选择另一种语言字幕重新翻译。
5. 不要优先下载视频。
6. 不要优先调用 ASR。
7. 如果没有字幕，再向用户说明限制，并询问是否需要其他方法。
8. 如果简介里有时间轴、章节、参考资料，应一起提取。
9. 字幕 URL 可能有时效性，拿到后尽快读取。

## 第 1 步：解析 BV 号

从用户给出的链接中提取 `BV` 号。

示例：

```text
https://www.bilibili.com/video/BV1SA7B6iEJg
```

得到：

```text
BV1SA7B6iEJg
```

## 第 2 步：获取视频信息

调用 B站视频信息接口：

```bash
BV_ID="BV1SA7B6iEJg"

curl -s "https://api.bilibili.com/x/web-interface/view?bvid=${BV_ID}" \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
```

从返回 JSON 中读取：

- `data.aid`：视频 AV 号
- `data.cid`：当前分 P 的 CID
- `data.title`：视频标题
- `data.desc`：视频简介，常含时间轴章节
- `data.duration`：视频时长，单位为秒
- `data.pages`：分 P 信息，如果存在多个分 P，应根据用户需求选择对应页面

如果用户没有指定分 P，通常先处理第一个页面。

## 第 3 步：获取字幕列表

B站字幕通常隐藏在弹幕视图接口中，不一定出现在普通播放器接口里。

优先调用：

```bash
CID="<从第2步获取的cid>"

curl -s "https://api.bilibili.com/x/v2/dm/view?oid=${CID}&type=1" \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \
  -H 'Referer: https://www.bilibili.com/'
```

在返回 JSON 中查找：

```text
data.subtitle.subtitles
```

## 第 4 步：选择最合适的字幕轨道

不要默认只找 `ai-zh`。应先根据用户目标语言选择字幕轨道。

选择顺序：

1. 目标语言的人工字幕 / UP 主字幕。
2. 目标语言的 B站 AI 字幕，例如 `ai-zh`。
3. 如果没有目标语言字幕，但有原语言字幕，并且用户明确需要翻译，再读取原语言字幕后翻译。
4. 如果字幕列表为空，告诉用户当前视频未检测到可用 B站字幕。

判断线索：

- `lan`：语言代码，例如中文、英文或 `ai-zh` 这类 AI 字幕标识。
- `lan_doc`：语言说明或字幕标题。
- 字幕名称中是否包含 AI、自动生成、UP主、中文、英文等信息。
- 一般来说，非 AI 的目标语言字幕优先于 AI 字幕。

取出选中条目的：

```text
subtitle_url
```

注意：

- 有些 `subtitle_url` 可能以 `//` 开头，需要补成 `https://`。
- 字幕 URL 可能短时间有效，应立即读取。

## 第 5 步：下载字幕 JSON

```bash
SUBTITLE_URL="<subtitle_url>"

curl -s -o subtitle.json "${SUBTITLE_URL}" \
  -H 'Referer: https://www.bilibili.com/'
```

常见结构：

```json
{
  "body": [
    {
      "from": 0.32,
      "to": 1.74,
      "content": "字幕文本"
    }
  ]
}
```

## 第 6 步：整理为可读文本

B站字幕，尤其是 AI 字幕，通常是 1 到 3 秒一句，不能直接原样输出。

整理规则：

1. 相邻字幕间隔大于 1.5 秒，可视为新句子或新语义块。
2. 很短的字幕片段应合并，避免一行一个碎片。
3. 每 200 到 300 个中文字符分一段。
4. 段末补充合适的句号、问号或感叹号。
5. 去掉明显无意义的语气词碎片，但不要删掉关键信息。
6. 对明显的 AI 字幕错字做轻微校正；人工字幕不要过度改写。
7. 如果 `data.desc` 中包含时间轴章节，可按章节组织文本。
8. 保留关键名词、数字、引用、专有名词和结论。

## 第 7 步：输出给用户

根据运行环境选择输出方式：

- 聊天 / IM 渠道：直接分段发送文字，不要只给文件。
- Web / 桌面环境：可以保存为 `.txt` 或 `.md`，同时给出核心摘要。
- 长视频：先输出标题、简介、章节，再分段输出正文。

推荐输出结构：

```markdown
# 视频标题

## 视频信息

- BV号：...
- 时长：...
- 目标语言：...
- 字幕来源：人工字幕 / UP 主字幕 / Bilibili AI 字幕

## 简介 / 章节

...

## 整理后的字幕正文

...
```

## 不推荐的路径

### 不要优先使用 ASR

如果 B站已有可用字幕，ASR 既慢又容易引入额外错误。只有在确实没有字幕且用户同意时，才考虑其他方法。

### 不要优先下载视频

用户通常要的是内容文本，不是视频文件。下载视频会增加时间、存储和失败率。

### 不要把 yt-dlp 当作唯一方案

某些工具在特定环境下可以处理 B站字幕，但可能受到登录状态、分 P 视频、字幕暴露方式影响。本流程优先使用 Bilibili 字幕接口，因为它更适合 Agent 直接读取。

## YouTube 说明

YouTube 的字幕提取逻辑在概念上相似，但 YouTube 的人机验证、登录状态和反自动化机制更强。

因此本流程暂不承诺适配 YouTube。若要扩展 YouTube，应单独建立流程，不应直接复用本文件并承诺稳定可用。

## 失败处理

如果无法获取字幕，应按顺序检查：

1. BV 号是否正确
2. 视频是否需要登录或地区权限
3. 是否有多个分 P，需要换 CID
4. `data.subtitle.subtitles` 是否为空
5. 是否存在目标语言字幕，或者是否需要换用另一条字幕轨道
6. `subtitle_url` 是否需要补全 `https://`
7. 请求头是否缺少 `User-Agent` 或 `Referer`
8. 字幕 URL 是否已经过期

如果视频确实没有字幕，应诚实告诉用户：当前视频未检测到可用 B站字幕。

## 浏览器内执行的额外坑（页面上下文 fetch 时）

在浏览器页面上下文（扩展 content script、油猴脚本、`page.evaluate`）中执行本流程时，curl 能跑通不代表浏览器能跑通，额外注意：

1. **Mixed Content**：`dm/view` 返回的 `subtitle_url` 常是 `http://` 开头，HTTPS 页面内直接 fetch 会被浏览器拦截。必须先把 `http://` 升级为 `https://`（`aisubtitle.hdslb.com` 支持 HTTPS）。
2. **CORS + 凭证冲突**：B站字幕 CDN 返回 `Access-Control-Allow-Origin: *`。根据 CORS 规则，携带 Cookie（`credentials: 'include'`）的请求会被直接拒收，报错只是笼统的 `TypeError: Failed to fetch`。**下载字幕文件必须 `credentials: 'omit'`**；只有 `api.bilibili.com` 的接口才需要带 Cookie 获取登录态。
3. B站对新会话/自动化会话偶尔返回「出错啦」页并二次跳转，浏览器自动化脚本需容忍导航导致的执行上下文销毁（重试读取即可）。