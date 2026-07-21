// ==UserScript==
// @name         AI Subtitle Extractor
// @namespace    https://github.com/Guojiz/ai-subtitle-extractor
// @version      0.3.0
// @description  Platform-agnostic page inject: export existing captions (YouTube/Bilibili/general discovery). Works with Tampermonkey and agent-browser. Standalone. Not affiliated with commercial translate extensions.
// @author       AI Subtitle Extractor contributors
// @match        *://*/*
// @grant        none
// @run-at       document-start
// ==/UserScript==


/**
 * Page-side subtitle export core (platform-agnostic inject payload).
 *
 * Load via:
 *   - agent-browser open --init-script scripts/page_inject/export_core.js <url>
 *   - agent-browser eval --stdin < scripts/page_inject/export_core.js
 *   - Tampermonkey userscript (same file body)
 *   - WebBridge evaluate (paste body)
 *
 * API:
 *   await window.__ovsExportSubtitle({ lang?: string })
 *   window.__ovsReady === true
 *
 * Original MIT code for this repository. Not affiliated with commercial extensions.
 */
(function () {
  "use strict";
  // Always re-bind export API so updated inject payloads take effect.
  // Network hook remains single-install via __ovsNetHooked.

  const GAP_SEC = 1.5;
  const MAX_CHARS = 260;

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function looksCjk(text) {
    let n = 0;
    for (const ch of text) {
      if (ch >= "\u4e00" && ch <= "\u9fff") n++;
    }
    return n >= Math.max(1, (text.length / 4) | 0);
  }

  function joinParts(parts, cjkHeavy) {
    return (cjkHeavy ? parts.join("") : parts.join(" ")).trim();
  }

  function mergeCues(cues) {
    const paragraphs = [];
    let current = [];
    let lastTo = null;
    let charCount = 0;
    const cjkHeavy = looksCjk(cues.slice(0, 20).map((c) => c.text).join(""));
    for (const cue of cues) {
      const text = (cue.text || "").trim();
      if (!text) continue;
      const start = +cue.start || 0;
      const end = cue.end != null ? +cue.end : start;
      const gap = lastTo != null ? start - lastTo : 0;
      if (current.length && (gap > GAP_SEC || charCount >= MAX_CHARS)) {
        paragraphs.push(joinParts(current, cjkHeavy));
        current = [];
        charCount = 0;
      }
      current.push(text);
      charCount += text.length;
      lastTo = end;
    }
    if (current.length) paragraphs.push(joinParts(current, cjkHeavy));
    return paragraphs.map((p) => {
      p = p.trim();
      if (!p) return p;
      if (!/[.!?。！？…]$/.test(p)) p += looksCjk(p) ? "。" : ".";
      return p;
    });
  }

  function detectPlatform() {
    const h = location.hostname;
    if (h.includes("youtube") || h.includes("youtu.be")) return "youtube";
    if (h.includes("bilibili.com") || h === "b23.tv") return "bilibili";
    return "general";
  }

  // ---- network cache: generic caption-like responses ----
  // Capture pristine fetch ONCE before wrapping. Never re-bind from window.fetch
  // after a hook is installed (that would capture the wrapper and recurse/break).
  function ensureNativeFetch() {
    if (typeof window.__ovsNativeFetch === "function") return;
    if (typeof window.fetch === "function") {
      window.__ovsNativeFetch = window.fetch.bind(window);
    }
  }

  function pageFetch(input, init) {
    ensureNativeFetch();
    if (typeof window.__ovsNativeFetch === "function") {
      return window.__ovsNativeFetch(input, init);
    }
    return window.fetch(input, init);
  }

  function ensureNetworkHook() {
    ensureNativeFetch();
    window.__ovsNetCache = window.__ovsNetCache || [];

    const interesting = (url) =>
      /timedtext|aisubtitle|\.vtt\b|\.srt\b|ttml|texttrack|\/subtitle/i.test(
        String(url || "")
      );

    const push = (url, body) => {
      if (!interesting(url) || !body || body.length < 40) return;
      window.__ovsNetCache.push({ url: String(url), body, t: Date.now() });
      if (window.__ovsNetCache.length > 24) window.__ovsNetCache.shift();
    };

    // Reinstall fetch wrapper from native each inject so updates apply cleanly.
    if (typeof window.__ovsNativeFetch === "function") {
      const ofetch = window.__ovsNativeFetch;
      window.fetch = async function (input, init) {
        const res = await ofetch(input, init);
        try {
          const url =
            typeof input === "string"
              ? input
              : input && typeof input.url === "string"
                ? input.url
                : "";
          if (interesting(url)) {
            const text = await res.clone().text();
            push(url, text);
          }
        } catch (_) {}
        return res;
      };
    }

    if (!window.__ovsXhrHooked) {
      window.__ovsXhrHooked = true;
      const XO = XMLHttpRequest.prototype.open;
      const XS = XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        this.__ovsUrl = url;
        return XO.call(this, method, url, ...rest);
      };
      XMLHttpRequest.prototype.send = function (...args) {
        this.addEventListener("load", function () {
          try {
            push(this.__ovsUrl, this.responseText || "");
          } catch (_) {}
        });
        return XS.apply(this, args);
      };
    }
  }

  function parseTimedtextJson(text) {
    const cues = [];
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return cues;
    }
    // YouTube json3
    if (Array.isArray(data.events)) {
      for (const ev of data.events) {
        if (!ev.segs) continue;
        if (ev.aAppend === 1 && !ev.dDurationMs) continue;
        const t = ev.segs
          .map((s) => s.utf8 || "")
          .join("")
          .replace(/\n/g, " ")
          .trim();
        if (!t) continue;
        const start = (ev.tStartMs || 0) / 1000;
        const end =
          ev.dDurationMs != null ? start + ev.dDurationMs / 1000 : null;
        cues.push({ start, end, text: t });
      }
      return cues;
    }
    // Bilibili-like body
    if (Array.isArray(data.body)) {
      for (const item of data.body) {
        const t = (item.content || item.text || "").trim();
        if (!t) continue;
        cues.push({
          start: +(item.from ?? item.start ?? 0) || 0,
          end: item.to != null ? +item.to : item.end != null ? +item.end : null,
          text: t,
        });
      }
    }
    return cues;
  }

  function parseVtt(raw) {
    const cues = [];
    const blocks = raw.trim().split(/\n\s*\n/);
    for (const block of blocks) {
      const lines = block.split(/\n/).map((l) => l.replace(/^\uFEFF/, ""));
      let timeLine = null;
      const textLines = [];
      for (const ln of lines) {
        if (ln.includes("-->")) timeLine = ln;
        else if (timeLine && ln && !/^WEBVTT/.test(ln) && !/^\d+$/.test(ln)) {
          textLines.push(ln.replace(/<[^>]+>/g, ""));
        }
      }
      if (!timeLine || !textLines.length) continue;
      const parts = timeLine.split("-->");
      const toSec = (ts) => {
        const p = ts.trim().split(/\s+/)[0].split(":");
        if (p.length === 3) return +p[0] * 3600 + +p[1] * 60 + parseFloat(p[2]);
        if (p.length === 2) return +p[0] * 60 + parseFloat(p[1]);
        return parseFloat(p[0]);
      };
      cues.push({
        start: toSec(parts[0]),
        end: toSec(parts[1]),
        text: textLines.join(" ").trim(),
      });
    }
    return cues;
  }

  function parseAnySubtitleBody(body) {
    const t = (body || "").trim();
    if (!t) return [];
    if (t.startsWith("{") || t.startsWith("[")) return parseTimedtextJson(t);
    if (t.includes("WEBVTT") || t.includes("-->")) return parseVtt(t);
    return [];
  }

  // ---- YouTube adapter ----
  function ytVideoId() {
    try {
      const u = new URL(location.href);
      if (u.searchParams.get("v")) return u.searchParams.get("v");
      const m = u.pathname.match(/\/(shorts|embed|live)\/([\w-]{11})/);
      if (m) return m[2];
    } catch (_) {}
    return null;
  }

  function ytPlayerResponse() {
    return window.ytInitialPlayerResponse || null;
  }

  function ytTracks() {
    const pr = ytPlayerResponse();
    return (
      (((pr || {}).captions || {}).playerCaptionsTracklistRenderer || {})
        .captionTracks || []
    );
  }

  function ytLabel(t) {
    const n = t.name;
    if (!n) return "";
    if (typeof n === "string") return n;
    if (n.simpleText) return n.simpleText;
    if (n.runs) return n.runs.map((r) => r.text || "").join("");
    return "";
  }

  function ytIsAuto(t) {
    return (
      (t.kind || "").toLowerCase() === "asr" ||
      /auto|自动/i.test(ytLabel(t))
    );
  }

  function ytPick(tracks, preferLang) {
    const p = (preferLang || "").toLowerCase();
    const score = (t) => {
      let s = ytIsAuto(t) ? 0 : 100;
      const lang = (t.languageCode || "").toLowerCase();
      if (p && (lang === p || lang.startsWith(p) || p.startsWith(lang))) s += 50;
      else if (p && p.slice(0, 2) && lang.startsWith(p.slice(0, 2))) s += 20;
      return -s;
    };
    return [...tracks].sort((a, b) => score(a) - score(b))[0];
  }

  async function enableYtCaptions(track) {
    const p = document.getElementById("movie_player");
    try {
      if (p && p.loadModule) p.loadModule("captions");
    } catch (_) {}
    try {
      if (p && p.setOption && track) {
        p.setOption("captions", "track", {
          languageCode: track.languageCode,
          kind: track.kind || undefined,
        });
      }
    } catch (_) {}
    try {
      if (p && p.playVideo) p.playVideo();
    } catch (_) {}
    try {
      if (p && p.toggleSubtitlesOn) p.toggleSubtitlesOn();
    } catch (_) {}
    const btn = document.querySelector(
      ".ytp-subtitles-button, button[aria-label*='字幕'], button[aria-label*='ubtitle' i], button[aria-label*='Captions' i]"
    );
    if (btn && btn.getAttribute("aria-pressed") === "false") {
      try {
        btn.click();
      } catch (_) {}
    }
  }

  async function extractYoutube(preferLang) {
    ensureNetworkHook();
    const vid = ytVideoId();
    if (!vid) throw new Error("youtube: no video id");
    const tracks = ytTracks();
    if (!tracks.length) throw new Error("youtube: no captionTracks");
    const chosen = ytPick(tracks, preferLang);
    await enableYtCaptions(chosen);
    await sleep(2800);

    let cues = [];
    let method = "";

    const cache = (window.__ovsNetCache || [])
      .slice()
      .reverse()
      .filter((x) => /timedtext/i.test(x.url) && x.url.includes(vid));
    for (const item of cache) {
      const c = parseAnySubtitleBody(item.body);
      if (c.length) {
        cues = c;
        method = "hooked_timedtext";
        break;
      }
    }

    if (!cues.length) {
      const resources = performance
        .getEntriesByType("resource")
        .map((e) => e.name)
        .filter((u) => /timedtext/i.test(u) && u.includes(vid));
      for (const u of resources) {
        try {
          const text = await pageFetch(u, { credentials: "include" }).then((r) =>
            r.text()
          );
          const c = parseAnySubtitleBody(text);
          if (c.length) {
            cues = c;
            method = "performance_timedtext";
            break;
          }
        } catch (_) {}
      }
    }

    if (!cues.length && chosen.baseUrl) {
      try {
        const u = new URL(chosen.baseUrl);
        u.searchParams.set("fmt", "json3");
        const text = await pageFetch(u.toString(), {
          credentials: "include",
        }).then((r) => r.text());
        cues = parseAnySubtitleBody(text);
        method = "baseUrl_timedtext";
      } catch (_) {}
    }

    if (!cues.length) {
      throw new Error(
        "youtube: empty timedtext — enable CC, play a few seconds, export again"
      );
    }

    const pr = ytPlayerResponse();
    const title =
      (pr && pr.videoDetails && pr.videoDetails.title) ||
      document.title.replace(/\s*-\s*YouTube\s*$/i, "");

    return {
      ok: true,
      platform: "youtube",
      adapter: "page_inject",
      url: location.href,
      title,
      language: chosen.languageCode || preferLang || "",
      track: {
        language: chosen.languageCode || "",
        kind: ytIsAuto(chosen) ? "auto" : "human",
        label: ytLabel(chosen),
        source: method,
      },
      cues,
      plain_text: mergeCues(cues).join("\n\n"),
      method,
    };
  }

  // ---- Bilibili adapter ----
  function biliBvid() {
    const m = location.pathname.match(/BV[\w]+/);
    return m ? m[0] : null;
  }

  async function extractBilibili(preferLang) {
    ensureNetworkHook();
    const bvid = biliBvid();
    if (!bvid) throw new Error("bilibili: no BV id");

    const view = await pageFetch(
      `https://api.bilibili.com/x/web-interface/view?bvid=${bvid}`,
      { credentials: "include" }
    ).then((r) => r.json());
    if (view.code !== 0) throw new Error("bilibili view: " + view.message);
    const data = view.data || {};
    const cid = data.cid;
    const title = data.title || document.title;
    const desc = data.desc || "";

    const dm = await pageFetch(
      `https://api.bilibili.com/x/v2/dm/view?oid=${cid}&type=1`,
      {
        credentials: "include",
        headers: { Referer: "https://www.bilibili.com/" },
      }
    ).then((r) => r.json());
    if (dm.code !== 0) throw new Error("bilibili dm/view: " + dm.message);
    const subs = (((dm.data || {}).subtitle || {}).subtitles) || [];
    if (!subs.length) throw new Error("bilibili: no subtitle tracks");

    const isAuto = (s) => {
      const lan = (s.lan || "").toLowerCase();
      const doc = s.lan_doc || "";
      return lan.includes("ai") || /ai|自动/i.test(doc);
    };
    const p = (preferLang || "").toLowerCase();
    const score = (s) => {
      let sc = isAuto(s) ? 0 : 100;
      const lan = (s.lan || "").toLowerCase();
      const doc = (s.lan_doc || "").toLowerCase();
      if (p && (lan.includes(p) || doc.includes(p))) sc += 50;
      return -sc;
    };
    const chosen = [...subs].sort((a, b) => score(a) - score(b))[0];
    let subUrl = chosen.subtitle_url || "";
    if (subUrl.startsWith("//")) subUrl = "https:" + subUrl;

    const bodyJson = await pageFetch(subUrl, {
      credentials: "include",
      headers: { Referer: "https://www.bilibili.com/" },
    }).then((r) => r.json());
    const cues = parseAnySubtitleBody(JSON.stringify(bodyJson));
    if (!cues.length) throw new Error("bilibili: empty subtitle body");

    return {
      ok: true,
      platform: "bilibili",
      adapter: "page_inject",
      url: location.href,
      title,
      language: chosen.lan || preferLang || "",
      track: {
        language: chosen.lan || "",
        kind: isAuto(chosen) ? "auto" : "human",
        label: chosen.lan_doc || "",
        source: "bilibili dm/view + subtitle_url",
      },
      chapters: desc,
      cues,
      plain_text: mergeCues(cues).join("\n\n"),
      method: "bilibili_api",
    };
  }

  // ---- General page discovery ----
  async function extractGeneral(preferLang) {
    ensureNetworkHook();
    const limits = [];
    let cues = [];
    let method = "";

    // 1) hooked network cache
    for (const item of (window.__ovsNetCache || []).slice().reverse()) {
      const c = parseAnySubtitleBody(item.body);
      if (c.length) {
        cues = c;
        method = "hooked_network";
        break;
      }
    }

    // 2) performance resources
    if (!cues.length) {
      const resources = performance
        .getEntriesByType("resource")
        .map((e) => e.name)
        .filter((u) =>
          /timedtext|subtitle|caption|\.vtt|\.srt|ttml|texttrack/i.test(u)
        );
      for (const u of resources.slice(0, 20)) {
        try {
          const text = await pageFetch(u, { credentials: "include" }).then((r) =>
            r.text()
          );
          const c = parseAnySubtitleBody(text);
          if (c.length) {
            cues = c;
            method = "performance_resource";
            break;
          }
        } catch (_) {}
      }
    }

    // 3) HTML5 tracks
    if (!cues.length) {
      const tracks = [...document.querySelectorAll("track")].filter((t) =>
        /captions|subtitles/i.test(t.kind || "")
      );
      for (const t of tracks) {
        if (!t.src) continue;
        try {
          const text = await pageFetch(t.src, { credentials: "include" }).then(
            (r) => r.text()
          );
          const c = parseAnySubtitleBody(text);
          if (c.length) {
            cues = c;
            method = "html5_track";
            break;
          }
        } catch (_) {}
      }
      if (!cues.length && tracks.length) limits.push("html5 track present but unreadable");
    }

    // 4) transcript-like DOM
    if (!cues.length) {
      const nodes = document.querySelectorAll(
        [
          "[class*='transcript' i]",
          "[class*='subtitle' i]",
          "[id*='transcript' i]",
          "ytd-transcript-segment-renderer",
        ].join(",")
      );
      const texts = [];
      nodes.forEach((n) => {
        const t = (n.innerText || "").trim();
        if (t && t.length < 500) texts.push(t);
      });
      if (texts.length >= 5) {
        cues = texts.map((text, i) => ({ start: i, end: null, text }));
        method = "dom_transcript_heuristic";
        limits.push("DOM heuristic — timestamps may be missing");
      }
    }

    if (!cues.length) {
      throw new Error(
        "general: no captions found (network/track/DOM). Play video or open transcript UI, then retry."
      );
    }

    return {
      ok: true,
      platform: "general",
      adapter: "page_inject",
      url: location.href,
      title: document.title || "",
      language: preferLang || "",
      track: {
        language: preferLang || "unknown",
        kind: "unknown",
        label: "",
        source: method,
      },
      cues,
      plain_text: mergeCues(cues).join("\n\n"),
      method,
      limits,
    };
  }

  async function exportSubtitle(opts) {
    ensureNetworkHook();
    const lang = (opts && opts.lang) || "";
    const force = (opts && opts.adapter) || "auto";
    const plat = force === "auto" ? detectPlatform() : force;
    if (plat === "youtube") return extractYoutube(lang);
    if (plat === "bilibili") return extractBilibili(lang);
    return extractGeneral(lang);
  }

  window.__ovsExportSubtitle = exportSubtitle;
  window.__ovsReady = true;
  window.__ovsPlatform = detectPlatform;
  ensureNetworkHook();
})();


// ---- floating UI (userscript only) ----
(function () {
  "use strict";
  const NS = "ovs-export";

  function toast(msg, ok) {
    let el = document.getElementById(NS + "-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = NS + "-toast";
      Object.assign(el.style, {
        position: "fixed",
        right: "16px",
        bottom: "72px",
        zIndex: "2147483646",
        maxWidth: "360px",
        padding: "10px 12px",
        borderRadius: "8px",
        font: "13px/1.4 system-ui,sans-serif",
        color: "#fff",
        boxShadow: "0 4px 16px rgba(0,0,0,.25)",
        opacity: "0",
        transition: "opacity .2s",
        pointerEvents: "none",
      });
      document.documentElement.appendChild(el);
    }
    el.style.background = ok ? "#0a7" : "#c33";
    el.textContent = msg;
    el.style.opacity = "1";
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.style.opacity = "0";
    }, 2800);
  }

  function downloadText(filename, text, mime) {
    const blob = new Blob([text], { type: mime || "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    }
  }

  function safeName(title) {
    return String(title || "subtitle")
      .replace(/[\\/:*?"<>|]+/g, "_")
      .slice(0, 80);
  }

  function toMarkdown(r) {
    return [
      `# ${r.title || "(untitled)"}`,
      "",
      "## Video info",
      "",
      `- Platform: ${r.platform}`,
      `- Adapter: ${r.adapter}`,
      `- URL: ${r.url}`,
      `- Language: ${r.language || "-"}`,
      `- Track kind: ${r.track && r.track.kind}`,
      `- Method: ${r.method}`,
      `- Cue count: ${(r.cues && r.cues.length) || 0}`,
      "",
      "## Transcript",
      "",
      r.plain_text || "",
      "",
    ].join("\n");
  }

  function ensureUi() {
    if (document.getElementById(NS + "-panel")) return;
    if (!document.documentElement) return;

    const panel = document.createElement("div");
    panel.id = NS + "-panel";
    Object.assign(panel.style, {
      position: "fixed",
      right: "12px",
      bottom: "12px",
      zIndex: "2147483645",
      display: "flex",
      flexDirection: "column",
      gap: "6px",
      font: "12px/1.3 system-ui,sans-serif",
    });

    const lang = document.createElement("input");
    lang.placeholder = "lang zh/en";
    Object.assign(lang.style, {
      width: "110px",
      padding: "6px 8px",
      borderRadius: "6px",
      border: "1px solid #ccc",
      background: "#fff",
    });

    const mk = (label, primary) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      Object.assign(b.style, {
        padding: "8px 10px",
        borderRadius: "8px",
        border: "none",
        cursor: "pointer",
        background: primary ? "#2563eb" : "#334155",
        color: "#fff",
        fontWeight: "600",
      });
      return b;
    };

    const btnExport = mk("导出字幕", true);
    const btnCopy = mk("复制正文", false);
    const btnJson = mk("下载 JSON", false);
    let last = null;

    async function run() {
      if (typeof window.__ovsExportSubtitle !== "function") {
        toast("export core not loaded", false);
        return;
      }
      btnExport.disabled = true;
      btnExport.textContent = "导出中…";
      try {
        last = await window.__ovsExportSubtitle({ lang: lang.value.trim() });
        downloadText(safeName(last.title) + ".md", toMarkdown(last));
        toast(`OK · ${(last.cues && last.cues.length) || 0} cues`, true);
      } catch (e) {
        console.error(e);
        toast(String(e.message || e), false);
      } finally {
        btnExport.disabled = false;
        btnExport.textContent = "导出字幕";
      }
    }

    btnExport.onclick = run;
    btnCopy.onclick = async () => {
      try {
        if (!last) await run();
        if (!last) return;
        toast((await copyText(last.plain_text || "")) ? "已复制" : "复制失败", true);
      } catch (e) {
        toast(String(e.message || e), false);
      }
    };
    btnJson.onclick = async () => {
      try {
        if (!last) await run();
        if (!last) return;
        downloadText(safeName(last.title) + ".json", JSON.stringify(last, null, 2));
        toast("JSON 已下载", true);
      } catch (e) {
        toast(String(e.message || e), false);
      }
    };

    panel.append(lang, btnExport, btnCopy, btnJson);
    document.documentElement.appendChild(panel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureUi);
  } else {
    ensureUi();
  }
  setInterval(ensureUi, 2000);
})();
