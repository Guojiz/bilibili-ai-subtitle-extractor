# Scripts（可独立运行）

**Agent / 人类**可直接执行。GitLearnOS 仅可选调用方。

| 组件 | 说明 |
|------|------|
| `extract_subtitles.py` | CLI 入口 |
| `page_inject/export_core.js` | **通用页内核**（agent-browser / 油猴 / evaluate 共用） |
| `lib/agent_browser.py` | 驱动 [agent-browser](https://github.com/vercel-labs/agent-browser) 注入 |
| `lib/bilibili.py` 等 | 站点适配 |

## 安装 agent-browser（推荐）

```bash
npm install -g agent-browser
agent-browser install
```

用于：打开页面 → `--init-script` 注入 core → `eval` 调 `__ovsExportSubtitle`。  
适合**任意站点**的通用注入，不绑死 B 站/YouTube。

## 用法

在仓库根目录：

```bash
# Bilibili HTTP
python scripts/extract_subtitles.py BV1SA7B6iEJg --lang zh -o out.md

# 通用：agent-browser 注入（任意 URL）
python scripts/extract_subtitles.py "https://..." --agent-browser --lang en -o out.md
python scripts/extract_subtitles.py "https://..." --agent-browser --headed

# HTTP 失败时自动上浏览器（优先 agent-browser）
python scripts/extract_subtitles.py "https://www.youtube.com/watch?v=..." --browser

# JSON / cues
python scripts/extract_subtitles.py BV... --json -o out.json --cues-json cues.json
```

### 为何要页内注入

| 环境 | 效果 |
|------|------|
| 纯 HTTP 拼字幕 URL | 常缺会话令牌 → 空 body |
| **agent-browser / 油猴页内** | hook 播放器真实请求 → 可拿全文 |

同一 `export_core.js`，多通道注入；实现原创。

### 退出码

- `0`：成功  
- `1`：失败（见 markdown/JSON 的 `error`）

## 模块

```text
scripts/
  extract_subtitles.py
  build_userscript.py
  page_inject/
    export_core.js
    README.md
  lib/
    agent_browser.py
    bilibili.py youtube.py youtube_browser.py general.py
    detect.py models.py clean.py http_util.py webbridge_client.py
```
