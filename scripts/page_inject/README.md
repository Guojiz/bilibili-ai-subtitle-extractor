# Page inject core（通用页内导出）

`export_core.js` 是**与站点无关的注入载荷**，挂上：

```js
await window.__ovsExportSubtitle({ lang: 'en' })  // 可选 adapter: 'youtube'|'bilibili'|'general'
window.__ovsReady === true
```

## 设计

1. 尽早 hook `fetch` / `XHR`，缓存字幕类网络响应（timedtext / subtitle / vtt…）  
2. 已知站走适配（YouTube / Bilibili）  
3. 未知站走 **general** 发现（网络缓存 → performance → HTML5 track → DOM 启发式）  
4. 人工轨优先；输出统一 JSON 形态  

同一份 core 可被：

| 通道 | 用法 |
|------|------|
| **agent-browser** | `open --init-script export_core.js <url>` 再 `eval` 调用 API（推荐注入） |
| **油猴** | `python scripts/build_userscript.py` 生成 userscript |
| **WebBridge** | `evaluate` 粘贴 core，再调用 API |
| **DevTools** | 控制台粘贴 |

## agent-browser 安装

```bash
npm install -g agent-browser
agent-browser install          # Chrome for Testing
# Linux 可能需要: agent-browser install --with-deps
```

文档：https://github.com/vercel-labs/agent-browser

## CLI

```bash
# 强制 agent-browser 注入（任意站点通用）
python scripts/extract_subtitles.py "<url>" --agent-browser --lang en -o out.md

# 有界面
python scripts/extract_subtitles.py "<url>" --agent-browser --headed

# HTTP 失败时自动尝试浏览器（优先 agent-browser）
python scripts/extract_subtitles.py "<youtube_url>" --browser
```

## 与商业扩展

只共享「页内数据通道」这一类设计；实现为本仓库原创 MIT 代码。  
