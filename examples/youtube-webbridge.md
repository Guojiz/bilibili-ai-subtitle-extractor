# 站点适配示例：YouTube（+ 访问回退）

本仓库的**产品是通用字幕管线**；本文件是 YouTube 的**站点适配**示例。  
访问失败时使用本地浏览器回退（如 Kimi WebBridge）——回退层对所有站点通用，不单属于 YouTube。

**不是**完整浏览器自动化实现；WebBridge 命令格式以用户环境文档为准。  
通用原则见 [`../SKILL.md`](../SKILL.md)。

## 0. 先确定目标语言

字幕选择顺序：

1. 目标语言的人工字幕  
2. 目标语言的自动字幕（auto-generated）  
3. 仅在用户明确要求翻译时，再读原语言后翻译  

## 1. 优先：直接打开视频页

```text
输入：https://www.youtube.com/watch?v=VIDEO_ID
动作：在 Agent 环境打开页面
成功：继续步骤 2（播放器数据）或步骤 3（转写面板）
失败：跳到步骤 4（WebBridge 回退），不要报告「无字幕」
```

## 2. 优先：让 Agent 自动拿 timedtext（推荐）

设计点：字幕正文在播放器网络请求里，不在 CC 叠加层。

```text
开始网络监听
  → 打开视频
  → 必要时打开 CC（只为触发 timedtext）
  → 捕获 URL 含 timedtext 且 body 非空的响应
  → 解析时间轴 + 文本
```

WebBridge 能力示意（命令名以本地 WebBridge 文档为准）：

```text
network start
navigate → 视频 URL
click / evaluate → 打开字幕（触发请求）
network list / detail → 读 timedtext 响应体
```

轨选择：目标语言优先；非自动识别轨优先于自动识别轨。  
优先原语言轨；需要翻译时由 Agent/下游翻译，而不是依赖播放器侧「自动译轨」（易限流、质量不稳）。

## 2b. 次优：读页面轨列表再 fetch

```javascript
const tracks =
  window.ytInitialPlayerResponse
    ?.captions
    ?.playerCaptionsTracklistRenderer
    ?.captionTracks || [];

// 按目标语言 + 人工/自动规则选轨后：
const data = await fetch(chosen.baseUrl, { credentials: 'include' }).then(r => r.json());
// 正文字段以实际响应为准（常见为 events 结构）
```

若 HTTP 200 但 body 为空：回到步骤 2，使用播放器自己发出的完整 timedtext 请求。

## 3. 打开 Transcript / 转写文稿面板（UI 兜底）

在页面上查找并点击类似入口（文案随语言变化）：

- Show transcript  
- 显示文字稿  
- **转写文稿** / **内容转文字**（中文界面常见）  
- 描述区先点 **...更多**，再找转写入口  
- 若看到 **无法显示字幕**，说明当前视频/地区可能没有可用轨，而不是 WebBridge 失败  

然后：

1. 在语言列表中选择目标语言  
2. 优先非「自动生成」轨道  
3. 读取时间戳 + 文本（如 `ytd-transcript-segment-renderer`）  
4. 合并短行、分段整理  
5. 输出时标明：`字幕来源` 与 `获取方式：transcript panel`

## 4. 回退：Kimi WebBridge 操作本地浏览器

当步骤 1 失败（超时、无法访问、验证码、地区限制等）时：

```text
直接访问失败
  → 检查 Kimi WebBridge 是否可用
  → navigate 到同一视频 URL（用户本地浏览器，已有登录态）
  → 优先 evaluate：captionTracks + timedtext(json3)
  → 失败再 snapshot / 点击「转写文稿」
  → 选择语言（人工优先）
  → 读取完整文稿并整理
  → 标明：获取方式：Kimi WebBridge + player timedtext / transcript panel
```

示意性调用（**伪示例**；真实参数与 session 规则以 WebBridge 技能为准）：

```bash
# 在用户本机打开视频（macOS / Linux 示意；Windows 请用文件体 POST，见 WebBridge 文档）
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"navigate","args":{"url":"https://www.youtube.com/watch?v=VIDEO_ID","newTab":true,"group_title":"字幕提取"},"session":"subtitle-extract"}'

# 读取可访问性树，定位 Transcript 入口
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"snapshot","args":{},"session":"subtitle-extract"}'

# 点击 @e 引用（以 snapshot 返回为准）
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"click","args":{"selector":"@eREF"},"session":"subtitle-extract"}'
```

本仓库**不实现** WebBridge；只约定字幕任务在访问失败时走本地浏览器路径。

## 4. 推荐输出字段

给用户或调用方时至少包含：

1. 视频标题  
2. 平台：YouTube  
3. 目标语言  
4. 字幕来源：人工字幕 / YouTube 自动字幕  
5. 获取方式：直接页面读取 / Kimi WebBridge  
6. 整理后的正文  
7. 若失败：说明直接访问与 WebBridge 各自尝试的结果，而不是只说「没有字幕」

## 5. 明确不做的事

- 不优先下载视频  
- 不优先 ASR  
- 不把 WebBridge 不可用写成「视频无字幕」  
- 不承诺所有 Agent 环境都能直连 YouTube  
