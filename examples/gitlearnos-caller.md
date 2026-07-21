# 可选调用方示例：GitLearnOS

本项目**可单点使用**（`scripts/extract_subtitles.py` 或按 `SKILL.md` 执行）。  
GitLearnOS 只是可选搭配，不是依赖。

本文件只说明**若作为调用方**时的边界。  
**不要**把 GitLearnOS 的学习代码复制进本仓库。

## 边界

| 系统 | 职责 |
|------|------|
| **本项目**（通用 Recipe） | 任意视频链接 → 统一字幕结果（平台适配在内部完成） |
| **GitLearnOS** | 提交链接、接收字幕，再生成笔记、问题、复习内容等 |

GitLearnOS **只调用**本项目获取字幕，不关心站点细节，也不在本仓库实现学习功能。

## 调用链

```text
用户 / GitLearnOS
  → 提交视频链接 +（可选）目标语言
  → 本项目通用管线：发现通道 → 选轨 → 拉全文 → 整理
       （Bilibili / YouTube / 通用网页 等适配对调用方透明）
       → 必要时本地浏览器访问回退
  → 返回统一字段：标题、正文、平台、语言、字幕来源、获取方式、限制
  → GitLearnOS 继续学习任务
```

## 请求侧（示意）

单点 CLI（无需 GitLearnOS）：

```bash
python scripts/extract_subtitles.py "<video_url>" --lang zh --json -o result.json
```

任意调用方（含 GitLearnOS）也可等价地：

```text
video_url:   用户给出的视频链接
language:    可选
prefer:      人工字幕优先，自动/AI 后补
disallow:    不要优先下载视频；不要优先 ASR
```

## 响应侧（示意）

本项目应返回可供下游使用的结构化结果，例如：

```markdown
# <视频标题>

- 平台：Bilibili | YouTube | other
- 目标语言：...
- 字幕来源：人工字幕 | UP主字幕 | 平台 AI 字幕 | 自动字幕 | 未知
- 获取方式：Bilibili API | 页面 Transcript | Kimi WebBridge | ...
- 限制：无 / 部分缺失 / 需登录 等

## 正文

...整理后的字幕文本...
```

GitLearnOS 拿到正文后，自行决定如何做笔记或出题——**那些步骤不在本仓库文档范围内**。

## 失败时

若本项目返回「未检测到可用字幕」，GitLearnOS 应：

1. 向用户展示本项目给出的失败原因（已检查的路径）  
2. **不要**默认在本仓库流程里启动 ASR 或视频下载  
3. 仅在用户明确同意时，再在 **GitLearnOS 或其它系统** 中讨论备选方案  

## 再次强调

- 本仓库是轻量 Agent Recipe，不是 GitLearnOS 子系统代码树  
- 学习、复习、卡片生成逻辑请留在 GitLearnOS  
- 本仓库只保证：尽量从平台已有字幕拿到文字，并标明来源  
