# Bilibili AI Subtitle Extractor

> 让任何具备浏览器或 API 操作能力的 AI Agent，都能从 B站视频中读取已有字幕，并整理成可读文本。人工字幕 / UP 主字幕优先，B站 AI 字幕作为没有人工字幕时的后补方案。

**Bilibili AI Subtitle Extractor** is an agent-agnostic recipe for reading existing Bilibili subtitles through browser/API access. Prefer creator-provided or human-made subtitles first, and use Bilibili AI subtitles only as a fallback when no better subtitle track exists.

它不是 ChatGPT 专用 Skill，也不依赖某一个固定客户端。ChatGPT、Claude、Codex、本地 Agent、浏览器自动化工具，甚至一个只会发 HTTP 请求的执行环境，都可以按这个流程完成 B站视频转文字。

## 这个项目解决什么

很多 AI 在拿到 B站视频链接后，会直接尝试：

- 下载视频
- 调用 ASR 转录音频
- 使用通用视频理解工具
- 试图用 yt-dlp 处理所有情况

但对 B站来说，更轻、更稳的办法通常是：**先检查 B站已经提供的字幕数据**。

读取字幕时不要机械优先选择 AI 字幕。更合理的顺序是：

1. 先确认用户需要哪一种语言的字幕。
2. 如果 B站已经有目标语言的人工字幕 / UP 主字幕，优先使用它。
3. 如果没有人工字幕，再使用 B站提供的 AI 字幕。
4. 如果已经有质量较好的目标语言字幕，不要再绕去拿另一种语言字幕重新翻译一遍。

这个仓库把流程写成一份清晰的 Agent Recipe，让 AI 不必绕远路。

## 适用场景

当用户给出 B站视频链接，并提出类似需求时，适合使用本流程：

- 提取字幕
- 提取文字
- 视频转文字
- 获取视频内容
- 整理视频文稿
- 翻译或润色字幕
- 根据视频字幕做总结、笔记、双语学习材料

## 核心原则

1. **优先使用 Bilibili 已有字幕数据**
2. **人工字幕 / UP 主字幕优先，AI 字幕作为后补**
3. **先确认目标语言，不要盲目选择字幕轨道**
4. **已有目标语言字幕时，不要重复翻译另一种语言字幕**
5. **不要优先下载视频**
6. **不要优先跑 ASR**
7. **不要把它写死成某个平台专用 Skill**
8. **如果视频简介里有章节或时间轴，要一起利用**

## 为什么暂时只做 Bilibili

YouTube 的字幕逻辑在概念上相似，但 YouTube 的登录、人机验证和反自动化机制更强，不适合在一个通用 Agent Recipe 里承诺稳定适配。

Bilibili 的字幕接口相对更容易通过浏览器/API 自动化访问，因此本项目先专注 B站。

## 快速流程

1. 从视频链接中解析 `BV` 号
2. 调用 B站视频信息接口，获取 `aid`、`cid`、标题、简介、时长
3. 调用弹幕视图接口，读取字幕列表
4. 根据用户目标语言选择最佳字幕：人工 / UP 主字幕优先，AI 字幕后补
5. 下载字幕 JSON
6. 合并短句，分段，利用简介中的章节整理为可读文本
7. 输出给用户，或保存为 TXT / Markdown

详细执行步骤见：[`SKILL.md`](./SKILL.md)

可复制命令见：[`examples/curl-workflow.md`](./examples/curl-workflow.md)

## 与已有工具的区别

这个项目不是一个大而全的字幕下载器。

它更像一张给 AI 的路线图：告诉 Agent 在面对 B站链接时，应该先去哪里拿字幕、如何选择字幕语言、如何判断人工字幕与 AI 字幕、如何整理、哪些坑不要踩。

如果你需要完整 CLI、批量下载、多格式导出，可以使用更成熟的字幕下载工具。

如果你需要让 AI 在对话中快速读取 B站视频内容，这个仓库会更轻。

## 贡献与合作

欢迎提交 Issue、PR 或新的执行样例，尤其是：

- 不同语言字幕轨道的选择规则
- 多分 P 视频处理
- 字幕字段变化记录
- 更好的整理脚本
- 其他 AI Agent / 浏览器自动化环境的适配说明

## 注意

Bilibili 的接口和字幕字段可能变化。本项目提供的是一个优先路径，而不是永久保证。实际执行时，Agent 应根据返回 JSON 灵活检查字段。