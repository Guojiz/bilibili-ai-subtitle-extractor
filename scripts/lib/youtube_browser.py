"""YouTube adapter via local browser (WebBridge).

Design (independent of any commercial extension source code):
  player loads captions → real timedtext URL includes session tokens (e.g. pot)
  → read that response → parse events → unified cues.

CLI HTTP alone often gets empty timedtext bodies; browser context fixes that.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from .clean import cues_to_paragraphs, paragraphs_to_text
from .models import Cue, ExtractResult, TrackInfo
from .webbridge_client import WebBridge, WebBridgeError
from .youtube import _parse_timedtext_payload, _parse_video_id


def extract_youtube_browser(
    url: str,
    *,
    prefer_lang: str = "",
    session: str = "subtitle-extract",
    settle_seconds: float = 5.0,
) -> ExtractResult:
    video_id = _parse_video_id(url)
    if not video_id:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube_browser",
            url=url,
            error="Could not parse YouTube video id",
        )
    watch_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        wb = WebBridge(session=session)
        wb.wait_ready()
        wb.navigate(watch_url, group_title="字幕提取")
        time.sleep(settle_seconds)

        meta = wb.evaluate(_JS_META)
        title = (meta or {}).get("title") or ""
        track_count = int((meta or {}).get("trackCount") or 0)
        if track_count <= 0:
            return ExtractResult(
                ok=False,
                platform="youtube",
                adapter="youtube_browser",
                url=watch_url,
                title=title,
                error="No captionTracks on page",
                method="webbridge",
            )

        # Prefer human track for target language inside page, enable CC, collect timedtext.
        prefer = prefer_lang or "en"
        payload = wb.evaluate(_JS_PULL % {"prefer": json.dumps(prefer), "video_id": json.dumps(video_id)})
        if not isinstance(payload, dict):
            return ExtractResult(
                ok=False,
                platform="youtube",
                adapter="youtube_browser",
                url=watch_url,
                title=title,
                error=f"Unexpected evaluate payload: {type(payload)}",
                method="webbridge",
            )

        if payload.get("error"):
            # One more settle + retry
            time.sleep(3)
            wb.evaluate(_JS_ENABLE)
            time.sleep(2)
            payload = wb.evaluate(
                _JS_PULL % {"prefer": json.dumps(prefer), "video_id": json.dumps(video_id)}
            )
            if not isinstance(payload, dict) or payload.get("error"):
                return ExtractResult(
                    ok=False,
                    platform="youtube",
                    adapter="youtube_browser",
                    url=watch_url,
                    title=title,
                    error=str((payload or {}).get("error") or "browser pull failed"),
                    limits=list((payload or {}).get("limits") or []),
                    method="webbridge",
                )

        raw = payload.get("raw") or ""
        cues = _parse_timedtext_payload(raw)
        if not cues and payload.get("cues"):
            # page already parsed
            cues = [
                Cue(
                    start=float(c.get("start", 0)),
                    end=float(c["end"]) if c.get("end") is not None else None,
                    text=str(c.get("text") or ""),
                )
                for c in payload["cues"]
                if (c.get("text") or "").strip()
            ]

        if not cues:
            return ExtractResult(
                ok=False,
                platform="youtube",
                adapter="youtube_browser",
                url=watch_url,
                title=title,
                error="Browser timedtext had no usable cues",
                limits=list(payload.get("limits") or [])
                + ["Open CC manually once if player blocked auto enable"],
                method="webbridge",
            )

        kind = "auto" if payload.get("kind") == "asr" or payload.get("isAuto") else "human"
        if payload.get("kind") == "asr":
            kind = "auto"
        paragraphs = cues_to_paragraphs(cues)
        plain = paragraphs_to_text(paragraphs)
        return ExtractResult(
            ok=True,
            platform="youtube",
            adapter="youtube_browser",
            url=watch_url,
            title=payload.get("title") or title,
            language=prefer_lang or payload.get("languageCode") or "",
            track=TrackInfo(
                language=payload.get("languageCode") or "",
                kind=kind,  # type: ignore[arg-type]
                source="local browser player timedtext (with session tokens)",
                label=payload.get("label") or "",
            ),
            cues=cues,
            plain_text=plain,
            method="webbridge_timedtext",
            limits=list(payload.get("limits") or []),
        )
    except WebBridgeError as e:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube_browser",
            url=watch_url,
            error=str(e),
            limits=[
                "Start Kimi WebBridge daemon + browser extension",
                r'Windows: & "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" start',
            ],
            method="webbridge",
        )


_JS_META = r"""
(() => {
  const pr = window.ytInitialPlayerResponse;
  const tracks = (((pr||{}).captions||{}).playerCaptionsTracklistRenderer||{}).captionTracks||[];
  const title = (pr && pr.videoDetails && pr.videoDetails.title) || document.title || '';
  return {title, trackCount: tracks.length};
})()
"""

_JS_ENABLE = r"""
(() => {
  const p = document.getElementById('movie_player');
  try { if (p && p.loadModule) p.loadModule('captions'); } catch (e) {}
  try { if (p && p.playVideo) p.playVideo(); } catch (e) {}
  try { if (p && p.toggleSubtitlesOn) p.toggleSubtitlesOn(); } catch (e) {}
  return {hasPlayer: !!p};
})()
"""

# prefer and video_id injected via % formatting with json.dumps
_JS_PULL = r"""
(async () => {
  const prefer = %(prefer)s;
  const videoId = %(video_id)s;
  const pr = window.ytInitialPlayerResponse;
  const tracks = (((pr||{}).captions||{}).playerCaptionsTracklistRenderer||{}).captionTracks||[];
  if (!tracks.length) return {error: 'no tracks'};

  const isAuto = (t) => {
    const k = (t.kind || '').toLowerCase();
    const name = (t.name && (t.name.simpleText || (t.name.runs||[]).map(r=>r.text).join(''))) || '';
    return k === 'asr' || /auto|自动/i.test(name);
  };
  const langScore = (t) => {
    if (!prefer) return 0;
    const p = prefer.toLowerCase();
    const lang = (t.languageCode || '').toLowerCase();
    if (lang === p || lang.startsWith(p) || p.startsWith(lang)) return 2;
    if (p.slice(0,2) && lang.startsWith(p.slice(0,2))) return 1;
    return 0;
  };
  tracks.sort((a,b) => {
    const aa = isAuto(a) ? 1 : 0, ba = isAuto(b) ? 1 : 0;
    if (aa !== ba) return aa - ba;
    return langScore(b) - langScore(a);
  });
  const chosen = tracks[0];
  const label = (chosen.name && (chosen.name.simpleText || (chosen.name.runs||[]).map(r=>r.text).join(''))) || '';

  const p = document.getElementById('movie_player');
  try { if (p && p.loadModule) p.loadModule('captions'); } catch (e) {}
  try {
    if (p && p.setOption) {
      p.setOption('captions', 'track', {
        languageCode: chosen.languageCode,
        kind: chosen.kind || undefined,
      });
    }
  } catch (e) {}
  try { if (p && p.playVideo) p.playVideo(); } catch (e) {}
  try { if (p && p.toggleSubtitlesOn) p.toggleSubtitlesOn(); } catch (e) {}

  await new Promise(r => setTimeout(r, 2500));

  const resources = (performance.getEntriesByType('resource') || [])
    .map(e => e.name)
    .filter(u => /timedtext/i.test(u));

  // Prefer player-issued URLs that include pot / signature for THIS video
  const ranked = resources
    .filter(u => u.includes('v=' + videoId) || u.includes('v%%3D' + videoId))
    .concat(resources)
    .filter((u, i, arr) => arr.indexOf(u) === i);

  const tryUrls = [];
  for (const u of ranked) tryUrls.push(u);
  // Also try baseUrl with fmt=json3 as secondary
  try {
    const bu = new URL(chosen.baseUrl);
    bu.searchParams.set('fmt', 'json3');
    tryUrls.push(bu.toString());
  } catch (e) {}

  const limits = [];
  for (const u of tryUrls) {
    try {
      const r = await fetch(u, { credentials: 'include' });
      const text = await r.text();
      if (!text || text.length < 50) continue;
      let cues = [];
      try {
        const j = JSON.parse(text);
        for (const ev of (j.events || [])) {
          if (!ev.segs) continue;
          if (ev.aAppend === 1 && !ev.dDurationMs) continue;
          const t = ev.segs.map(s => s.utf8 || '').join('').replace(/\n/g, ' ').trim();
          if (!t) continue;
          const start = (ev.tStartMs || 0) / 1000;
          const end = ev.dDurationMs != null ? start + ev.dDurationMs / 1000 : null;
          cues.push({ start, end, text: t });
        }
      } catch (e) {
        limits.push('non-json timedtext skipped');
        continue;
      }
      if (cues.length) {
        return {
          title: (pr && pr.videoDetails && pr.videoDetails.title) || document.title || '',
          languageCode: chosen.languageCode || '',
          kind: chosen.kind || '',
          isAuto: isAuto(chosen),
          label,
          raw: text,
          cues,
          usedUrl: u.slice(0, 160),
          limits,
        };
      }
    } catch (e) {
      limits.push(String(e));
    }
  }
  return {
    error: 'no non-empty timedtext for this video',
    trackCount: tracks.length,
    resourceCount: resources.length,
    limits: limits.concat([
      'Player may need pot-bearing timedtext; try wait longer or enable CC once',
    ]),
  };
})()
"""
