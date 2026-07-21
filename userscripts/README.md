# 油猴 Userscript

由**通用页内核**生成，不是另一套逻辑：

```bash
python scripts/build_userscript.py
# → ai-subtitle-extractor.user.js
```

核文件：[`../scripts/page_inject/export_core.js`](../scripts/page_inject/export_core.js)

## 安装

1. Tampermonkey / Violentmonkey  
2. 导入 `ai-subtitle-extractor.user.js`（`@match *://*/*`，通用）  
3. 打开任意视频页 → 右下角导出 / 复制 / JSON  

## Agent 更推荐 agent-browser

油猴适合人机常驻；Agent 批量注入请用：

```bash
npm install -g agent-browser && agent-browser install
python scripts/extract_subtitles.py "<url>" --agent-browser
```

见 [`../scripts/page_inject/README.md`](../scripts/page_inject/README.md)。

## API

```js
await window.__ovsExportSubtitle({ lang: 'zh' })
// adapter 可选: youtube | bilibili | general（默认 auto）
```

## 许可

MIT。与商业翻译扩展无关。  
