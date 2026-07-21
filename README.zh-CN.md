# AI Subtitle Extractor

[English](./README.md)

**把任意在线视频链接变成干净文稿——读平台已有的字幕。人工轨优先，自动轨后补。不下载视频，不跑 ASR。**

本仓库的核心是 [`SKILL.md`](./SKILL.md) 里的 Recipe：一套通用管线，YouTube 和 Bilibili 是已验证的样板适配。其他站点走通用发现，不声称完整支持。

```text
视频链接
  → 识别站点（或通用发现）
  → 先问目标语言——要翻译就译成用户想要的语言
  → 发现字幕通道（API / timedtext / VTT·SRT / 转写面板 / <track>）
  → 人工轨优先 → 整份时间轴 cues → 可读正文
  → 返回：正文 + 平台 + 语言 + 字幕来源 + 获取方式
  → 访问失败：回退到用户本地浏览器
  → 确实无字幕：如实说明（之后才考虑 ASR）
```

## 验证状态

只声称实际跑通过的。

| 组件 | 状态 |
|---|---|
| YouTube 适配 | ✅ 真实 watch 页实测（经 WebBridge） |
| Bilibili 适配 | ✅ 真实视频实测（完整 SRT/文本导出） |
| 通用嗅探（fetch/XHR hook、`textTracks`、`<track>`） | ✅ 测试套件 + 真实 YouTube 页 |
| WebBridge `evaluate` 注入（主路径） | ✅ 已实测 |
| Playwright `add_init_script` 注入 | ✅ 已实测（全部测试套件） |
| MV3 扩展形态 | ✅ B站实测 |
| 油猴安装形态 | ⚠️ 未单独实测 |
| `scripts/` 的 agent-browser 后端 | ⚠️ 未实测 |
| 其他站点 | 仅通用发现，不声称支持 |

## 快速开始（已实测主路径）

通过 WebBridge 之类的桥驱动用户真实浏览器（带登录态），用户侧零安装：

```text
1. node universal/build.js   → dist/universal-subtitle-extractor.user.js
2. navigate → 视频页
3. evaluate → 注入 .user.js 全文（重复注入有守卫）
4. evaluate → 单次往返提取：
```

```javascript
(async () => {
  await window.__USE__.waitFor(1, 20000);
  return JSON.stringify({
    meta: window.__USE__.meta(),
    tracks: window.__USE__.list(),
    text: window.__USE__.text()
  });
})()
```

## 仓库地图

| 路径 | 内容 |
|---|---|
| [`SKILL.md`](./SKILL.md) | **Recipe（核心资产）**：管线 → 适配 → 回退 → 输出契约 |
| [`universal/`](./universal/) | 可运行的通用提取器（`window.__USE__` API），含测试 |
| [`scripts/`](./scripts/) | 参考 CLI + 页内核（`__ovsExportSubtitle`） |
| [`examples/`](./examples/) | 适配示例：YouTube + 浏览器回退、Bilibili curl |

## 贡献

欢迎站点适配：遵守通用管线与 `Cue` 模型，用公开示例，如实标注「已验证 / 实验性」。见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可

MIT，见 [LICENSE](./LICENSE)。原名 `bilibili-ai-subtitle-extractor`，旧链接自动跳转。
