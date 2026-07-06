---
name: bilibili-ai-subtitle-extractor
description: 面向任意 AI Agent、浏览器自动化工具或脚本执行环境的 B站 AI 字幕提取流程。当用户提供 B站视频链接并要求提取字幕、视频转文字、获取视频内容、整理文稿、翻译字幕或总结视频时，优先使用本流程。不要优先下载视频，不要优先使用 ASR。只要运行环境能访问网页、操作浏览器或发送 HTTP 请求，就可以执行。
---

# B站 AI 字幕提取流程

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

1. 优先读取 Bilibili 已有字幕数据。
2. 不要优先下载视频。
3. 不要优先调用 ASR。
4. 如果没有字幕，再向用户说明限制，并询问是否需要其他方法。
5. 如果简介里有时间轴、章节、参考资料，应一起提取。
6. 字幕 URL 可能有时效性，拿到后尽快下载。

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

B站 AI 字幕通常隐藏在弹幕视图接口中，不一定出现在普通播放器接口里。

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

优先选择：

- `lan` 为 `ai-zh` 的条目
- 或标题/语言信息显示为中文 AI 字幕的条目

取出其中的：

```text
subtitle_url
```

注意：

- 有些 `subtitle_url` 可能以 `//` 开头，需要补成 `https://`。
- 字幕 URL 可能短时间有效，应立即下载。

## 第 4 步：下载字幕 JSON

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

## 第 5 步：整理为可读文本

B站 AI 字幕通常是 1 到 3 秒一句，不能直接原样输出。

整理规则：

1. 相邻字幕间隔大于 1.5 秒，可视为新句子或新语义块。
2. 很短的字幕片段应合并，避免一行一个碎片。
3. 每 200 到 300 个中文字符分一段。
4. 段末补充合适的句号、问号或感叹号。
5. 去掉明显无意义的语气词碎片，但不要删掉关键信息。
6. 对明显的 AI 字幕错字做轻微校正。
7. 如果 `data.desc` 中包含时间轴章节，可按章节组织文本。
8. 保留关键名词、数字、引用、专有名词和结论。

## 第 6 步：输出给用户

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
- 字幕来源：Bilibili AI 字幕

## 简介 / 章节

...

## 整理后的字幕正文

...
```

## 不推荐的路径

### 不要优先使用 ASR

如果 B站已有 AI 字幕，ASR 既慢又容易引入额外错误。

### 不要优先下载视频

用户通常要的是内容文本，不是视频文件。下载视频会增加时间、存储和失败率。

### 不要把 yt-dlp 当作唯一方案

某些工具在特定环境下可以处理 B站字幕，但可能受到登录状态、反爬、分 P 视频、字幕暴露方式影响。本流程优先使用 Bilibili 字幕 API，因为它更适合 Agent 直接读取。

## YouTube 说明

YouTube 的字幕提取逻辑在概念上相似，但 YouTube 的人机验证、登录状态和反自动化机制更强。

因此本流程暂不承诺适配 YouTube。若要扩展 YouTube，应单独建立流程，不应直接复用本文件并承诺稳定可用。

## 失败处理

如果无法获取字幕，应按顺序检查：

1. BV 号是否正确
2. 视频是否需要登录或地区权限
3. 是否有多个分 P，需要换 CID
4. `data.subtitle.subtitles` 是否为空
5. `subtitle_url` 是否需要补全 `https://`
6. 请求头是否缺少 `User-Agent` 或 `Referer`
7. 字幕 URL 是否已经过期

如果视频确实没有字幕，应诚实告诉用户：当前视频未检测到可用 B站字幕。