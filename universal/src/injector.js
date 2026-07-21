/*
 * Universal Subtitle Extractor — 页面层（Page World / MAIN world）
 * 职责：
 *   1. Hook fetch / XMLHttpRequest，嗅探字幕响应（借鉴沉浸式翻译 video-subtitle/inject.js 的思路）
 *   2. 主动提取：Bilibili 官方 API 流程、YouTube captionTracks、HTML5 textTracks
 *   3. 解析各种字幕格式为统一 cue 模型 {start, end, text}
 *   4. 轨道注册到 window.__USE__，供 AI Agent / 浏览器自动化读取（无 UI）
 * 本文件可直接作为 MV3 扩展的 MAIN world content script，也可加油猴头作为 userscript。
 */
(function () {
  'use strict';
  if (window.__USE_INJECTED__) return;
  window.__USE_INJECTED__ = true;

  var TAG = 'universal-subtitle-extractor';
  var CMD = TAG + '-cmd';

  function send(type, data) {
    try {
      window.postMessage({ source: TAG, type: type, data: data }, '*');
    } catch (e) { /* 跨域对象不可克隆时忽略 */ }
  }

  function log() {
    var args = ['[USE]'].concat([].slice.call(arguments));
    try { console.log.apply(console, args); } catch (e) {}
  }

  /* ------------------------------------------------------------------ *
   * 时间戳解析：支持 hh:mm:ss.mmm / mm:ss.mmm / ss.mmm / SRT 逗号格式 / 偏移时间(1.5s, 200ms)
   * ------------------------------------------------------------------ */
  function parseTime(str) {
    if (str == null) return 0;
    str = String(str).trim().replace(',', '.');
    var m = str.match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?$/);
    if (m) {
      return (parseInt(m[1] || '0', 10) * 3600) +
             (parseInt(m[2], 10) * 60) +
             parseFloat(m[3] + '.' + (m[4] || '0'));
    }
    m = str.match(/^(\d+(?:\.\d+)?)(s|ms)$/);
    if (m) return m[2] === 'ms' ? parseFloat(m[1]) / 1000 : parseFloat(m[1]);
    m = str.match(/^(\d+(?:\.\d+)?)$/);
    if (m) return parseFloat(m[1]);
    return 0;
  }

  function cleanText(s) {
    return String(s == null ? '' : s)
      .replace(/<[^>]+>/g, '')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&nbsp;/g, ' ')
      .replace(/\{\\an?\d+\}/g, '')
      .trim();
  }

  /* ------------------------------------------------------------------ *
   * 各格式解析器 → [{start, end, text}]
   * ------------------------------------------------------------------ */
  function parseVTT(text) {
    var cues = [];
    var blocks = String(text).replace(/\r/g, '').split(/\n{2,}/);
    for (var i = 0; i < blocks.length; i++) {
      var lines = blocks[i].split('\n').filter(function (l) { return l.trim() !== ''; });
      var ti = -1;
      for (var j = 0; j < lines.length; j++) {
        if (lines[j].indexOf('-->') !== -1) { ti = j; break; }
      }
      if (ti === -1) continue;
      var m = lines[ti].match(/(\S+)\s*-->\s*(\S+)/);
      if (!m) continue;
      var t = lines.slice(ti + 1).join('\n');
      cues.push({ start: parseTime(m[1]), end: parseTime(m[2]), text: cleanText(t) });
    }
    return cues;
  }

  function parseTTML(text) {
    var cues = [];
    try {
      var doc = new DOMParser().parseFromString(text, 'text/xml');
      var ps = doc.getElementsByTagName('p');
      for (var i = 0; i < ps.length; i++) {
        var p = ps[i];
        var begin = p.getAttribute('begin');
        var end = p.getAttribute('end');
        var dur = p.getAttribute('dur');
        var start = parseTime(begin);
        var stop = end != null ? parseTime(end) : (dur != null ? start + parseTime(dur) : start);
        var html = p.innerHTML.replace(/<br\s*\/?>/gi, '\n');
        var tmp = doc.createElement('div');
        tmp.innerHTML = html;
        var t = cleanText(tmp.textContent || '');
        if (t) cues.push({ start: start, end: stop, text: t });
      }
    } catch (e) {}
    return cues;
  }

  function parseBilibili(json) {
    var body = json && json.body;
    if (!Array.isArray(body)) return null;
    return body.map(function (c) {
      return { start: Number(c.from) || 0, end: Number(c.to) || 0, text: cleanText(c.content) };
    }).filter(function (c) { return c.text; });
  }

  function parseYoutubeJson3(json) {
    var events = json && json.events;
    if (!Array.isArray(events)) return null;
    var cues = [];
    events.forEach(function (ev) {
      if (!ev.segs || typeof ev.tStartMs !== 'number') return;
      // aAppend 事件是上一条的追加碎片（无独立时长），不跳过会产生重复/乱序 cue
      if (ev.aAppend === 1 && !ev.dDurationMs) return;
      var t = ev.segs.map(function (s) { return s.utf8 || ''; }).join('');
      t = cleanText(t.replace(/\n/g, ' '));
      if (!t) return;
      cues.push({ start: ev.tStartMs / 1000, end: (ev.tStartMs + (ev.dDurationMs || 0)) / 1000, text: t });
    });
    return cues.length ? cues : null;
  }

  // 通用 JSON 启发式：递归找「数组元素带 起止时间+文本」的结构
  function parseGenericJSON(json, depth) {
    depth = depth || 0;
    if (depth > 6 || json == null) return null;
    var bilibili = parseBilibili(json);
    if (bilibili && bilibili.length) return bilibili;
    var yt = parseYoutubeJson3(json);
    if (yt && yt.length) return yt;
    if (Array.isArray(json)) {
      if (json.length && json.every(function (c) {
        return c && typeof c === 'object' &&
          (c.from != null || c.start != null || c.begin != null) &&
          (c.content != null || c.text != null || c.line != null);
      })) {
        return json.map(function (c) {
          return {
            start: parseTime(c.from != null ? c.from : (c.start != null ? c.start : c.begin)),
            end: parseTime(c.to != null ? c.to : (c.end != null ? c.end : c.stop)),
            text: cleanText(c.content != null ? c.content : (c.text != null ? c.text : c.line))
          };
        }).filter(function (c) { return c.text; });
      }
      for (var i = 0; i < Math.min(json.length, 10); i++) {
        var r = parseGenericJSON(json[i], depth + 1);
        if (r && r.length) return r;
      }
      return null;
    }
    if (typeof json === 'object') {
      var keys = Object.keys(json);
      for (var k = 0; k < keys.length; k++) {
        var r2 = parseGenericJSON(json[keys[k]], depth + 1);
        if (r2 && r2.length) return r2;
      }
    }
    return null;
  }

  // 内容嗅探：判断文本像哪种字幕格式并解析
  function parseByContent(raw, url) {
    if (!raw) return null;
    var text = raw;
    var trimmed = text.trim();
    if (!trimmed) return null;
    var cues = null, format = null;
    if (/^WEBVTT/.test(trimmed)) {
      format = 'vtt'; cues = parseVTT(trimmed);
    } else if (/<tt[\s>]/.test(trimmed.slice(0, 2000)) || /<\/tt>/.test(trimmed)) {
      format = 'ttml'; cues = parseTTML(trimmed);
    } else if (/^\d+\s*\r?\n\s*\d{1,2}:\d{2}:\d{2}[,.]\d+/.test(trimmed)) {
      format = 'srt'; cues = parseVTT(trimmed);
    } else if (trimmed[0] === '{' || trimmed[0] === '[') {
      try {
        var json = JSON.parse(trimmed);
        cues = parseGenericJSON(json);
        if (cues) format = url && url.indexOf('timedtext') !== -1 ? 'youtube-json3' : 'json';
      } catch (e) {}
    } else if (trimmed.indexOf('-->') !== -1) {
      format = 'vtt?'; cues = parseVTT(trimmed);
    }
    if (cues && cues.length >= 2) return { format: format, cues: cues };
    return null;
  }

  /* ------------------------------------------------------------------ *
   * 字幕 URL 判定：通用正则 + 站点规则表（站点规则思路借鉴沉浸式翻译配置）
   * ------------------------------------------------------------------ */
  var GENERIC_URL_RE = /\.(vtt|webvtt|srt|ttml2?|dfxp|ass|ssa)(\?|#|&|$)|\/api\/timedtext|aisubtitle\.hdslb\.com|\/subtitles?\/|\/captions?\/|text_?tracks?|transcription\.json/i;
  var GENERIC_CT_RE = /(vtt|subrip|ttml|dfxp|caption|subtitle)/i;

  function shouldSniff(url) {
    if (!url || typeof url !== 'string') return false;
    return GENERIC_URL_RE.test(url);
  }

  function guessLang(url) {
    var m = String(url || '').match(/[?&](?:lang|tlang|hl|language|locale|srclang)=([a-zA-Z-]{2,10})/);
    if (m) return m[1].toLowerCase();
    m = String(url || '').match(/[.\/_-](zh[-_](?:CN|TW|Hans|Hant)?|en[-_](?:US|GB)?|ja|ko|es|fr|de|ru|pt|ar|th|vi|id)(?=[.\/?&_-]|$)/i);
    if (m) return m[1].toLowerCase().replace('_', '-');
    return '';
  }

  /* ------------------------------------------------------------------ *
   * 轨道注册表：AI Agent 通过 window.__USE__ 读取（见文件末尾 API）
   * ------------------------------------------------------------------ */
  var REGISTRY = new Map(); // id -> track
  var PAGE_META = {};
  var trackListeners = [];

  function notifyTrack(track) {
    trackListeners.forEach(function (cb) { try { cb(track); } catch (e) {} });
  }

  var reported = {}; // id -> cue 数量
  var SOURCE_PRIORITY = { api: 4, tracktag: 3, texttrack: 2, network: 1 };

  // 内容签名：同一份字幕可能从多个路径被发现（网络嗅探 + textTracks + track 标签）
  function signature(t) {
    var last = t.cues[t.cues.length - 1];
    return t.cues.length + '|' + Math.round(last ? last.end : 0) + '|' +
      (t.cues[0] ? t.cues[0].text.slice(0, 30) : '');
  }

  function reportTrack(track) {
    if (!track || !track.cues || track.cues.length < 2) return;
    track.id = track.id || ('net:' + track.url);
    var prev = reported[track.id];
    if (prev && prev >= track.cues.length) return; // 同 URL 只更新为更全的版本
    // 内容去重：已有同级/更高优先级来源的相同字幕时跳过
    var sig = signature(track);
    var ids = Array.from(REGISTRY.keys());
    for (var i = 0; i < ids.length; i++) {
      var ex = REGISTRY.get(ids[i]);
      if (!ex || ids[i] === track.id) continue;
      if (signature(ex) === sig) {
        if ((SOURCE_PRIORITY[ex.source] || 0) >= (SOURCE_PRIORITY[track.source] || 0)) return;
        REGISTRY.delete(ids[i]);
        delete reported[ids[i]];
      }
    }
    reported[track.id] = track.cues.length;
    track.foundAt = Date.now();
    REGISTRY.set(track.id, track);
    send('track', publicTrack(track));
    notifyTrack(publicTrack(track));
    log('捕获字幕轨道:', track.label || track.url, '(' + track.cues.length + ' 条)');
  }

  // 上报/对外时不带 cues 全文，避免 postMessage 传大对象
  function publicTrack(t) {
    return {
      id: t.id, site: t.site, url: t.url, lang: t.lang, label: t.label,
      format: t.format, source: t.source, isAI: !!t.isAI,
      cueCount: t.cues.length, duration: t.cues.length ? t.cues[t.cues.length - 1].end : 0
    };
  }

  function handleResponse(url, text, contentType) {
    if (!shouldSniff(url) && !GENERIC_CT_RE.test(contentType || '')) return;
    var parsed = parseByContent(text, url);
    if (!parsed) return;
    reportTrack({
      site: location.hostname,
      url: url,
      lang: guessLang(url),
      label: '网络嗅探 · ' + (parsed.format || '?'),
      format: parsed.format,
      source: 'network',
      cues: parsed.cues
    });
  }

  /* ------------------------------------------------------------------ *
   * Hook fetch / XHR（借鉴沉浸式翻译 inject.js 的 hook 方式）
   * ------------------------------------------------------------------ */
  (function hookFetch() {
    var orig = window.fetch;
    if (typeof orig !== 'function') return;
    window.fetch = function () {
      var args = arguments;
      var input = args[0];
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      var promise = orig.apply(this, args);
      if (shouldSniff(url)) {
        promise.then(function (res) {
          try {
            var clone = res.clone();
            var ct = clone.headers.get('content-type') || '';
            clone.text().then(function (t) { handleResponse(url, t, ct); }).catch(function () {});
          } catch (e) {}
        }).catch(function () {});
      }
      return promise;
    };
    window.__USE_ORIGINAL_FETCH__ = orig;
  })();

  (function hookXHR() {
    var origOpen = XMLHttpRequest.prototype.open;
    var origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__useUrl = typeof url === 'string' ? url : (url && url.href) || '';
      return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
      var xhr = this;
      var url = xhr.__useUrl;
      if (shouldSniff(url)) {
        xhr.addEventListener('load', function () {
          try {
            if (xhr.status < 200 || xhr.status >= 300) return;
            var text = null;
            if (!xhr.responseType || xhr.responseType === 'text') {
              text = xhr.responseText;
            } else if (xhr.responseType === 'arraybuffer' && xhr.response) {
              text = new TextDecoder('utf-8').decode(xhr.response);
            }
            if (text) handleResponse(url, text, xhr.getResponseHeader('content-type') || '');
          } catch (e) {}
        });
      }
      return origSend.apply(this, arguments);
    };
  })();

  /* ------------------------------------------------------------------ *
   * 主动提取器：Bilibili（沿用 bilibili-ai-subtitle-extractor 仓库的 API 流程，
   * 在页面上下文执行，自动带 Cookie，人工/UP主字幕优先，AI 字幕后补）
   * ------------------------------------------------------------------ */
  function jget(url, credentials) {
    return (window.__USE_ORIGINAL_FETCH__ || window.fetch)(url, { credentials: credentials || 'include' })
      .then(function (r) { return r.json(); });
  }

  function absUrl(u) {
    if (!u) return u;
    if (u.indexOf('//') === 0) return location.protocol + u;
    if (u.indexOf('/') === 0) return location.origin + u;
    // 页面为 HTTPS 时强制升级，避免 Mixed Content 拦截（B站字幕接口常返回 http://）
    if (location.protocol === 'https:' && u.indexOf('http://') === 0) return 'https://' + u.slice(7);
    return u;
  }

  async function scanBilibili() {
    var m = location.pathname.match(/\/video\/(BV\w+)/);
    if (!m) return false;
    var bvid = m[1];
    var p = parseInt(new URLSearchParams(location.search).get('p') || '1', 10);
    try {
      var view = await jget('https://api.bilibili.com/x/web-interface/view?bvid=' + bvid);
      var data = view && view.data;
      if (!data) { send('status', { level: 'warn', msg: 'B站视频信息获取失败' }); return true; }
      var page = (data.pages && data.pages[p - 1]) || data;
      PAGE_META = { site: 'bilibili', title: data.title, desc: data.desc, duration: data.duration, bvid: bvid, page: p };
      send('meta', PAGE_META);

      var dm = await jget('https://api.bilibili.com/x/v2/dm/view?oid=' + page.cid + '&type=1');
      var subs = (((dm || {}).data || {}).subtitle || {}).subtitles || [];
      if (!subs.length) {
        send('status', { level: 'info', msg: 'B站：该视频未检测到字幕' });
        return true;
      }
      // 人工/UP主字幕优先，AI 字幕后补
      subs = subs.slice().sort(function (a, b) {
        var aiA = /^ai/.test(a.lan || '') ? 1 : 0;
        var aiB = /^ai/.test(b.lan || '') ? 1 : 0;
        return aiA - aiB;
      });
      for (var i = 0; i < subs.length; i++) {
        var s = subs[i];
        try {
          var url = absUrl(s.subtitle_url);
          // 字幕 CDN 返回 ACAO:*，带 Cookie 会被浏览器拒绝，必须 omit
          var json = await jget(url, 'omit');
          var cues = parseBilibili(json);
          if (cues && cues.length) {
            reportTrack({
              site: 'bilibili',
              url: url,
              lang: s.lan || '',
              label: (s.lan_doc || s.lan || '字幕') + (/^ai/.test(s.lan || '') ? ' · AI' : ' · 人工'),
              format: 'bilibili-json',
              source: 'api',
              isAI: /^ai/.test(s.lan || ''),
              cues: cues
            });
          }
        } catch (e) { log('B站字幕下载失败', e); }
      }
    } catch (e) {
      send('status', { level: 'warn', msg: 'B站字幕接口请求失败：' + e.message });
    }
    return true;
  }

  /* ------------------------------------------------------------------ *
   * 主动提取器：YouTube（captionTracks，借鉴沉浸式翻译 youtube 处理器
   * 使用 #movie_player.getPlayerResponse() 的思路）
   * ⚠️ EXPERIMENTAL / 待测试：json3 解析与 captionTracks 全链路已通过
   * mock 页面端到端测试（tests/test_youtube.py），真实 YouTube 页面
   * 尚未验证（开发环境无法访问 YouTube）。
   * ------------------------------------------------------------------ */
  function ytPlayerResponse() {
    try {
      var player = document.querySelector('#movie_player');
      if (player && typeof player.getPlayerResponse === 'function') {
        var pr = player.getPlayerResponse();
        if (pr) return pr;
      }
    } catch (e) {}
    return window.ytInitialPlayerResponse || null;
  }

  // 直取 captionTracks.baseUrl 常返回空 body（YouTube 要求带播放器上下文
  // 的请求）。此时程序化打开 CC，让播放器自己发 timedtext 请求，
  // 由网络嗅探层（fetch/XHR hook）捕获真实字幕响应。
  function ytEnableCaptions(track) {
    try {
      var p = document.querySelector('#movie_player');
      if (p && p.loadModule) p.loadModule('captions');
      if (p && p.setOption && track) {
        p.setOption('captions', 'track', { languageCode: track.languageCode, kind: track.kind || undefined });
      }
    } catch (e) {}
    try {
      var btn = document.querySelector('.ytp-subtitles-button, button[aria-label*="字幕"], button[aria-label*="ubtitle" i], button[aria-label*="Captions" i]');
      if (btn && btn.getAttribute('aria-pressed') === 'false') btn.click();
    } catch (e) {}
  }

  async function scanYouTube() {
    if (!/youtube\.com|youtube-nocookie\.com/.test(location.hostname)) return false;
    if (!/^\/(watch|shorts\/|embed\/|live\/)/.test(location.pathname)) return false;
    try {
      var pr = ytPlayerResponse();
      var renderer = pr && pr.captions && pr.captions.playerCaptionsTracklistRenderer;
      var tracks = (renderer && renderer.captionTracks) || [];
      var title = pr && pr.videoDetails && pr.videoDetails.title;
      if (title) {
        PAGE_META = { site: 'youtube', title: title, duration: Number(pr.videoDetails.lengthSeconds) || 0 };
        send('meta', PAGE_META);
      }
      if (!tracks.length) {
        send('status', { level: 'info', msg: 'YouTube：该视频未检测到字幕轨道' });
        return true;
      }
      var got = 0, empty = 0;
      for (var i = 0; i < tracks.length; i++) {
        var t = tracks[i];
        try {
          var url = t.baseUrl + (t.baseUrl.indexOf('fmt=') === -1 ? '&fmt=json3' : '');
          var text = await (window.__USE_ORIGINAL_FETCH__ || window.fetch)(url, { credentials: 'include' }).then(function (r) { return r.text(); });
          if (!text || !text.trim()) { empty++; continue; } // baseUrl 直取常见空 body
          var cues = null, format = 'youtube-json3';
          try { cues = parseYoutubeJson3(JSON.parse(text)); } catch (e) {}
          if (!cues) { cues = parseTTML(text); format = 'srv-xml'; }
          if (cues && cues.length) {
            got++;
            var label = (t.name && (t.name.simpleText || (t.name.runs || []).map(function (r) { return r.text; }).join(''))) || t.languageCode || '字幕';
            reportTrack({
              site: 'youtube',
              url: t.baseUrl,
              lang: (t.languageCode || '').toLowerCase(),
              label: label + (t.kind === 'asr' ? ' · AI' : ' · 人工'),
              format: format,
              source: 'api',
              isAI: t.kind === 'asr',
              cues: cues
            });
          }
        } catch (e) { log('YouTube 字幕下载失败', e); }
      }
      if (!got) {
        ytEnableCaptions(tracks[0]);
        send('status', { level: 'info', msg: empty
          ? 'YouTube：baseUrl 直取返回空，已自动打开 CC，改由网络嗅探捕获播放器的字幕请求'
          : 'YouTube：字幕下载失败，已自动打开 CC，改由网络嗅探捕获播放器的字幕请求' });
      }
    } catch (e) {
      send('status', { level: 'warn', msg: 'YouTube 字幕提取失败：' + e.message });
    }
    return true;
  }

  /* ------------------------------------------------------------------ *
   * 兜底：HTML5 textTracks + <track> 标签
   * ------------------------------------------------------------------ */
  function scanTextTracks() {
    var found = false;
    var videos = document.querySelectorAll('video');
    videos.forEach(function (video, vi) {
      try {
        var tracks = video.textTracks || [];
        for (var i = 0; i < tracks.length; i++) {
          (function (track, idx) {
            function collect() {
              try {
                if (!track.cues || !track.cues.length) return;
                var cues = [];
                for (var c = 0; c < track.cues.length; c++) {
                  var cue = track.cues[c];
                  var t = cleanText(cue.text || '');
                  if (t) cues.push({ start: cue.startTime, end: cue.endTime, text: t });
                }
                if (cues.length >= 2) {
                  reportTrack({
                    site: location.hostname,
                    url: 'texttrack://' + vi + '/' + idx,
                    lang: (track.language || '').toLowerCase(),
                    label: 'textTracks · ' + (track.label || track.language || ('轨道' + (idx + 1))),
                    format: 'texttrack',
                    source: 'texttrack',
                    cues: cues
                  });
                }
              } catch (e) {}
            }
            if (track.cues && track.cues.length) { collect(); found = true; }
            else if (track.mode === 'disabled') {
              try { track.mode = 'hidden'; } catch (e) {}
              track.addEventListener('load', collect);
              setTimeout(collect, 4000);
            } else {
              track.addEventListener('load', collect);
              setTimeout(collect, 4000);
            }
          })(tracks[i], i);
        }
        // <track src> 标签直接抓取
        video.querySelectorAll('track[src]').forEach(function (el, idx) {
          var src = absUrl(el.getAttribute('src'));
          if (!src || reported['tracktag:' + src]) return;
          reported['tracktag:' + src] = 1;
          (window.__USE_ORIGINAL_FETCH__ || window.fetch)(src, { credentials: 'include' })
            .then(function (r) { return r.text(); })
            .then(function (text) {
              var parsed = parseByContent(text, src);
              if (parsed) {
                reportTrack({
                  site: location.hostname,
                  url: src,
                  lang: (el.srclang || '').toLowerCase(),
                  label: '<track> · ' + (el.label || el.srclang || ('轨道' + (idx + 1))),
                  format: parsed.format,
                  source: 'tracktag',
                  cues: parsed.cues
                });
                found = true;
              }
            })
            .catch(function () {});
        });
      } catch (e) {}
    });
    return found;
  }

  /* ------------------------------------------------------------------ *
   * 扫描调度：加载后扫描、URL 变化（SPA）重扫、响应隔离层命令
   * ------------------------------------------------------------------ */
  var lastUrl = location.href;
  var scanTimer = null;

  function scanAll() {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(function () {
      var handled = false;
      if (/bilibili\.com$|\.bilibili\.com$/.test(location.hostname)) {
        scanBilibili(); handled = true;
      }
      if (/youtube\.com$|\.youtube\.com$|youtube-nocookie\.com$/.test(location.hostname)) {
        scanYouTube(); handled = true;
      }
      scanTextTracks();
      send('scanned', { url: location.href, active: handled });
    }, 1200);
  }

  function onUrlChange() {
    if (location.href === lastUrl) return;
    lastUrl = location.href;
    reported = {};
    REGISTRY.clear();
    PAGE_META = {};
    send('reset', { url: location.href });
    scanAll();
  }

  // SPA 导航检测：pushState/replaceState/popstate + 轮询兜底
  (function watchNavigation() {
    ['pushState', 'replaceState'].forEach(function (name) {
      var orig = history[name];
      history[name] = function () {
        var r = orig.apply(this, arguments);
        setTimeout(onUrlChange, 300);
        return r;
      };
    });
    window.addEventListener('popstate', function () { setTimeout(onUrlChange, 300); });
    window.addEventListener('yt-navigate-finish', function () { setTimeout(onUrlChange, 300); });
    setInterval(onUrlChange, 2000);
  })();

  // 隔离层命令
  window.addEventListener('message', function (ev) {
    if (ev.source !== window) return;
    var d = ev.data;
    if (!d || d.source !== CMD) return;
    if (d.type === 'scan') scanAll();
  });

  // 首次扫描
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scanAll);
  } else {
    scanAll();
  }

  /* ------------------------------------------------------------------ *
   * 导出器：SRT / VTT / 整理后的纯文本（合并碎片，按语义分段）
   * ------------------------------------------------------------------ */
  function pad(n, w) { n = String(n); while (n.length < w) n = '0' + n; return n; }
  function fmtTime(sec, sep) {
    sec = Math.max(0, Number(sec) || 0);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
    var ms = Math.round((sec - Math.floor(sec)) * 1000);
    if (ms === 1000) { ms = 0; s += 1; }
    return pad(h, 2) + ':' + pad(m, 2) + ':' + pad(s, 2) + sep + pad(ms, 3);
  }

  function toSRT(cues) {
    return cues.map(function (c, i) {
      return (i + 1) + '\n' + fmtTime(c.start, ',') + ' --> ' + fmtTime(c.end, ',') + '\n' + c.text;
    }).join('\n\n') + '\n';
  }

  function toVTT(cues) {
    return 'WEBVTT\n\n' + cues.map(function (c) {
      return fmtTime(c.start, '.') + ' --> ' + fmtTime(c.end, '.') + '\n' + c.text;
    }).join('\n\n') + '\n';
  }

  // 整理为可读文本：间隔 > 1.5s 视为新语义块；每 200~300 字分段
  function toText(cues, opts) {
    opts = opts || {};
    var gap = opts.gap != null ? opts.gap : 1.5;
    var paraLen = opts.paragraphLength || 260;
    var withTime = !!opts.timestamps;
    var paras = [], cur = '', curStart = 0, prevEnd = 0;
    cues.forEach(function (c) {
      var t = c.text.replace(/\s+/g, ' ').trim();
      if (!t) return;
      var needBreak = cur && ((c.start - prevEnd > gap) || cur.length >= paraLen);
      if (needBreak) {
        paras.push(withTime ? '[' + fmtTime(curStart, '.').slice(0, 8) + '] ' + cur : cur);
        cur = '';
      }
      if (!cur) curStart = c.start;
      cur += (cur && /[\u4e00-\u9fff]$/.test(cur) && /^[\u4e00-\u9fff]/.test(t) ? '' : ' ') + t;
      prevEnd = c.end;
    });
    if (cur) paras.push(withTime ? '[' + fmtTime(curStart, '.').slice(0, 8) + '] ' + cur : cur);
    return paras.join('\n\n');
  }

  /* ------------------------------------------------------------------ *
   * 公开 API：window.__USE__
   * 供 AI Agent / 浏览器自动化直接 evaluate 调用。
   * ------------------------------------------------------------------ */
  function pickBest() {
    var tracks = Array.from(REGISTRY.values());
    if (!tracks.length) return null;
    // 优先级：API/轨道来源 > 网络嗅探；人工 > AI；条数多者优先
    var score = function (t) {
      var s = 0;
      if (t.source === 'api') s += 100;
      else if (t.source === 'texttrack' || t.source === 'tracktag') s += 60;
      else s += 30;
      if (!t.isAI) s += 40;
      s += Math.min(t.cues.length, 20);
      return s;
    };
    tracks.sort(function (a, b) { return score(b) - score(a); });
    return tracks[0];
  }

  function resolveTrack(idOrTrack) {
    if (!idOrTrack) return pickBest();
    if (typeof idOrTrack === 'object') return idOrTrack;
    return REGISTRY.get(idOrTrack) || null;
  }

  window.__USE__ = {
    version: '0.2.0',

    /** 页面元信息（标题/简介/时长，B站含简介章节） */
    meta: function () { return Object.assign({}, PAGE_META); },

    /** 列出已发现的字幕轨道（不含 cues 全文） */
    list: function () { return Array.from(REGISTRY.values()).map(publicTrack); },

    /** 取某条轨道的完整数据（含 cues）；不传 id 则自动选最优 */
    get: function (id) {
      var t = resolveTrack(id);
      return t ? Object.assign({}, t) : null;
    },

    /** 最优轨道 id（人工 > AI，API > 嗅探） */
    best: function () {
      var t = pickBest();
      return t ? t.id : null;
    },

    /** 整理后的纯文本；opts: {timestamps, gap, paragraphLength} */
    text: function (id, opts) {
      var t = resolveTrack(id);
      return t ? toText(t.cues, opts) : null;
    },

    srt: function (id) {
      var t = resolveTrack(id);
      return t ? toSRT(t.cues) : null;
    },

    vtt: function (id) {
      var t = resolveTrack(id);
      return t ? toVTT(t.cues) : null;
    },

    /** 等待直到至少发现 n 条轨道（默认 1 条），超时返回当前数量 */
    waitFor: function (n, timeoutMs) {
      n = n || 1; timeoutMs = timeoutMs || 15000;
      return new Promise(function (resolve) {
        if (REGISTRY.size >= n) return resolve(REGISTRY.size);
        var timer = setTimeout(function () { done(); }, timeoutMs);
        function done() {
          clearTimeout(timer);
          trackListeners = trackListeners.filter(function (cb) { return cb !== onTrack; });
          resolve(REGISTRY.size);
        }
        function onTrack() { if (REGISTRY.size >= n) done(); }
        trackListeners.push(onTrack);
      });
    },

    /** 手动触发重新扫描（主动提取 + textTracks；网络嗅探持续进行无需触发） */
    scan: function () { scanAll(); return true; },

    /** 清空当前注册表 */
    reset: function () { REGISTRY.clear(); reported = {}; return true; },

    /** 直接解析一段字幕文本（vtt/srt/ttml/json 自动识别），返回 {format, cues} */
    parse: function (text, url) { return parseByContent(text, url || ''); }
  };

  log('页面层已注入，API: window.__USE__');
})();
