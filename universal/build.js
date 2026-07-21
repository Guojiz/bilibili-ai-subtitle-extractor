// 构建 userscript：把 src/injector.js 加上油猴头，输出 dist/universal-subtitle-extractor.user.js
const fs = require('fs');
const path = require('path');

const root = __dirname;
const injector = fs.readFileSync(path.join(root, 'src', 'injector.js'), 'utf8');

const version = (injector.match(/version:\s*'([\d.]+)'/) || [null, '0.0.0'])[1];

const header = `// ==UserScript==
// @name         Universal Subtitle Extractor (for AI Agents)
// @name:zh-CN   通用字幕提取器（AI Agent 专用）
// @namespace    https://github.com/Guojiz/ai-subtitle-extractor
// @version      ${version}
// @description  通用视频字幕提取：B站/YouTube 主动提取 + 全站网络嗅探 + textTracks 兜底。结果通过 window.__USE__ API 暴露给 AI Agent，无 UI。
// @match        *://*/*
// @run-at       document-start
// @grant        none
// @license      MIT
// ==/UserScript==

`;

fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
fs.writeFileSync(path.join(root, 'dist', 'universal-subtitle-extractor.user.js'), header + injector);
console.log('built dist/universal-subtitle-extractor.user.js, version', version);

// 扩展：复制 injector.js 到 extension/
fs.mkdirSync(path.join(root, 'extension'), { recursive: true });
fs.copyFileSync(path.join(root, 'src', 'injector.js'), path.join(root, 'extension', 'injector.js'));
console.log('copied extension/injector.js');
