#!/usr/bin/env python3
"""Build userscripts/ai-subtitle-extractor.user.js from page_inject/export_core.js + UI shell."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "scripts" / "page_inject" / "export_core.js"
OUT = ROOT / "userscripts" / "ai-subtitle-extractor.user.js"

HEADER = """// ==UserScript==
// @name         AI Subtitle Extractor
// @namespace    https://github.com/Guojiz/ai-subtitle-extractor
// @version      0.3.0
// @description  Platform-agnostic page inject: export existing captions (YouTube/Bilibili/general discovery). Works with Tampermonkey and agent-browser. Standalone. Not affiliated with commercial translate extensions.
// @author       AI Subtitle Extractor contributors
// @match        *://*/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

"""

UI_SHELL = r"""
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
"""


def main() -> None:
    core = CORE.read_text(encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HEADER + "\n" + core + "\n" + UI_SHELL, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
