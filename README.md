# Online Video Subtitle Recipe for AI Agents

> 一份**平台无关**的 Agent 流程：从任意在线视频链接，优先读取平台**已有**字幕 / 文字稿，整理成可读文本。  
> 人工轨优先，自动 / AI 轨后补。不要优先下载视频，不要优先跑 ASR。Agent 应自己执行命令与脚本。

**Online Video Subtitle Recipe for AI Agents** is a lightweight, platform-agnostic recipe. The product is the **shared pipeline**; Bilibili, YouTube, and other sites are **adapters** under that pipeline—not the other way around.

本仓库 GitHub 名为 `ai-subtitle-extractor`（原 `bilibili-ai-subtitle-extractor`，已随通用化改名）。它**不是** B 站专用工具，也不是完整字幕下载软件，而是给 AI Agent 用的**通用字幕获取 Recipe**。

## 项目定位

| 是 | 不是 |
|----|------|
| 跨站点通用的「视频链接 → 文字稿」Agent 流程 | 某一家视频站的官方客户端 |
| 同一套原则 + 可插拔站点适配 | 为单一平台写死的脚本仓库 |
| Agent 可执行的步骤与示例 | 商业浏览器扩展 / 闭源插件的移植 |
| 调用方（如 GitLearnOS）的上游字幕能力 | 学习笔记 / 出题系统本身 |

通用性来自**同一套管线**，而不是堆很多互不相干的站点教程：

```text
任意视频链接
  → 识别站点（或走通用发现）
  → 确认目标语言
  → 发现字幕数据通道（API / 网络字幕资源 / 页面 Transcript / track）
  → 选轨：人工优先，自动后补
  → 拉取完整时间轴文稿（不是屏幕当前一行）
  → 规范成统一片段结构 → 整理可读正文
  → 返回：正文 + 平台 + 语言 + 字幕来源 + 获取方式
  → 访问失败：本地浏览器回退（如 Kimi WebBridge）
  → 确实无字幕：如实说明（再谈 ASR 等备选）
```

## 通用管线（所有站点共用）

无论站点是谁，Agent 都按下面六步思考。站点差异只出现在「发现通道」和「字段映射」。

| 步骤 | 通用问题 | 成功标准 |
|------|----------|----------|
| 1. 入口 | 链接能否解析？短链是否展开？ | 稳定的视频页 / 资源 ID |
| 2. 语言 | 用户要哪种语言？ | 明确目标语言或合理推断 |
| 3. 发现 | 这个站的字幕数据从哪来？ | API / timedtext / VTT·SRT / Transcript UI / `<track>` … |
| 4. 选轨 | 哪一条轨最好？ | 目标语言 + 人工优先 + 自动后补 |
| 5. 拉取 | 如何拿到**整份**时间轴？ | 结构化 cues，而非截图/OCR |
| 6. 输出 | 如何交付？ | 可读正文 + 来源元数据 |

### 统一片段模型（站点适配后的目标形态）

各站点字段名不同，Agent 应先归一再整理：

```text
Cue {
  start: number   // 秒
  end:   number   // 秒（可知时）
  text:  string
}
Track {
  language: string
  kind: "human" | "auto" | "unknown"
  source: string  // 简要说明获取通道
}
```

### 发现通道的优先级（通用）

对**任意**视频页，按代价从低到高尝试：

1. **站点已知适配**（若已有可复现步骤）→ 直接走适配  
2. **结构化资源**：字幕 JSON、timedtext、VTT、SRT、HTML5 `<track>`  
3. **播放器网络**：监听播放器自己加载的字幕请求（参数更完整）  
4. **页面文稿 UI**：Transcript / 文字稿 / 转写 面板  
5. **简介/章节文本**：有讲稿或时间轴时一并利用  
6. **访问回退**：Agent 环境打不开时，用本地已登录浏览器（如 WebBridge）再跑 2–5  
7. **失败说明**：不要假装有字幕；不要默认 ASR / 下载视频  

## 站点适配（Adapters）

适配 = 把「通用管线」落到某个站的发现方式与字段映射。  
**未写适配的站点，默认走「通用网页发现」**，不要声称已完整支持。

| 适配 | 状态 | 在通用管线中的角色 |
|------|------|--------------------|
| **通用网页** | 默认路径 | 任何未知站：检查清单式发现 |
| **Bilibili** | 已验证较完整 | 公开 API → 字幕 JSON → `Cue[]` |
| **YouTube** | 已验证路径 + 访问回退 | 页面轨列表 / timedtext / 转写面板 |
| 其他站 | 欢迎贡献 | 只增加适配说明，不改通用原则 |

仓库历史从 B 站示例起步，但**产品中心是通用管线**；B 站、YouTube 是样板适配，便于 Agent 照着扩到新站。

## 单点使用（通用注入 + CLI）

不依赖 GitLearnOS。核心是**同一份页内 core**，多种通道注入：

### 访问通道（从稳到轻）

| 通道 | 作用 | 安装 |
|------|------|------|
| **agent-browser** | Agent 专用浏览器 CLI：`open` + `--init-script` / `eval` 注入 core | `npm i -g agent-browser && agent-browser install` |
| **油猴** | 用户浏览器常驻注入同一 core | Tampermonkey 装 userscript |
| **HTTP CLI** | 无浏览器（B 站最稳） | 仅 Python 标准库 |
| WebBridge | 操作用户已登录浏览器（可选） | 本机 WebBridge |

页内 API（注入成功后）：

```js
await window.__ovsExportSubtitle({ lang: 'en' })  // youtube | bilibili | general
```

### CLI 示例

```bash
# B 站 HTTP（单点）
python scripts/extract_subtitles.py BV1SA7B6iEJg --lang zh -o out.md

# 任意站点：agent-browser 注入（推荐通用路径）
python scripts/extract_subtitles.py "https://..." --agent-browser --lang en -o out.md

# HTTP 失败时自动上浏览器（优先 agent-browser）
python scripts/extract_subtitles.py "https://www.youtube.com/watch?v=..." --browser
```

源码：

- 注入核：[`scripts/page_inject/export_core.js`](./scripts/page_inject/export_core.js)  
- 油猴生成：`python scripts/build_userscript.py` → [`userscripts/`](./userscripts/)  
- 说明：[`scripts/README.md`](./scripts/README.md)、[`scripts/page_inject/README.md`](./scripts/page_inject/README.md)

## Agent 如何执行

- **通用推荐**：装好 agent-browser 后  
  `python scripts/extract_subtitles.py <url> --agent-browser`  
  （内部：`open --init-script export_core.js` → `eval` 调 `__ovsExportSubtitle`）  
- B 站可直接 HTTP CLI  
- 用户常驻：油猴同一 core  
- 或 WebBridge `evaluate` 注入 core

## 文档入口

| 文档 | 内容 |
|------|------|
| [`scripts/`](./scripts/) | CLI + **agent-browser 注入** + page_inject core |
| [`scripts/page_inject/`](./scripts/page_inject/) | **通用页内导出核**（多通道共用） |
| [`userscripts/`](./userscripts/) | 油猴包装（由 core 生成） |
| [`universal/`](./universal/) | 另一套可运行的通用提取器实现（`window.__USE__` API；主路径：WebBridge `evaluate` 按需注入，另有 Playwright 注入 / MV3 扩展形态；B站、YouTube 均已真实页面实测） |
| [`SKILL.md`](./SKILL.md) | Agent 主流程：通用管线 → 适配 → 回退 → 输出 |
| [`examples/curl-workflow.md`](./examples/curl-workflow.md) | Bilibili curl 样板 |
| [`examples/youtube-webbridge.md`](./examples/youtube-webbridge.md) | YouTube 取数 + 浏览器回退 |
| [`examples/gitlearnos-caller.md`](./examples/gitlearnos-caller.md) | **可选**调用方示意（不是运行依赖） |

## 核心原则

1. **通用管线优先，站点适配其次**  
2. **优先平台已有字幕数据**，不要优先下载视频或 ASR  
3. **人工 / 创作者轨优先**，自动 / AI 轨后补  
4. **整份时间轴文稿**，不要只抄当前叠加层一行  
5. **能脚本化就脚本化**（Agent 执行）  
6. **访问失败 ≠ 无字幕**；先尝试本地浏览器回退  
7. **未验证站点不宣称完整支持**；用通用发现 + 诚实失败  
8. **返回时标明**平台、语言、字幕来源、获取方式  
9. **独立 Recipe**：不绑定、不包含任何商业扩展源码  

## 与 Kimi WebBridge 的关系

WebBridge 只解决「Agent 环境打不开网页」时，操作用户**本地已登录浏览器**。  
它是通用管线里的**访问回退层**，不是某一站点的专用依赖。

## 与 GitLearnOS 的关系（可选）

GitLearnOS 只是**可选搭配**之一，不是本项目的运行前提。

- **单点**：人 / Agent 直接跑脚本或按 SKILL 执行即可  
- **搭配**：任意系统提交链接 → 拿统一字幕结果 → 自己做笔记/复习  

学习功能不写在本仓库。

## 贡献

欢迎补充新站点适配，但请：

- 遵守通用管线与统一 `Cue` / 输出来源字段  
- 使用公开、非敏感示例  
- 写明「已验证」或「实验性」  
- 不要提交 cookies、账号数据、整段盗用的闭源实现  

## 许可

MIT License。详见 [LICENSE](LICENSE)。
