"""YouTube adapter: best-effort page/timedtext path (stdlib only).

Full reliability may require a real browser session (see SKILL.md access fallback).
This adapter is original and intentionally small — not a downloader.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from .clean import cues_to_paragraphs, paragraphs_to_text
from .http_util import http_get_json, http_get_text
from .models import Cue, ExtractResult, TrackInfo


def extract_youtube(
    url: str,
    *,
    prefer_lang: str = "",
    use_browser: bool = False,
) -> ExtractResult:
    if use_browser:
        from .youtube_browser import extract_youtube_browser

        return extract_youtube_browser(url, prefer_lang=prefer_lang)

    video_id = _parse_video_id(url)
    if not video_id:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube",
            url=url,
            error="Could not parse YouTube video id",
        )

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    limits: list[str] = []

    try:
        html = http_get_text(
            watch_url,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
    except Exception as e:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube",
            url=watch_url,
            error=f"Failed to fetch watch page: {e}",
            limits=[
                "Agent runtime may be blocked; use local browser / WebBridge fallback per SKILL.md",
            ],
        )

    pr = _extract_player_response(html)
    title = ""
    if pr:
        title = (
            ((pr.get("videoDetails") or {}).get("title"))
            or ((pr.get("microformat") or {}).get("playerMicroformatRenderer") or {}).get(
                "title", {}
            ).get("simpleText")
            or ""
        )

    tracks = _caption_tracks(pr)
    if not tracks:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube",
            url=watch_url,
            title=title,
            error="No captionTracks found in page player data",
            limits=[
                "Video may have no captions, or page requires browser/cookies",
                "Try WebBridge timedtext capture per SKILL.md",
            ],
        )

    chosen, kind = _select_track(tracks, prefer_lang=prefer_lang)
    base = chosen.get("baseUrl") or ""
    if not base:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube",
            url=watch_url,
            title=title,
            error="Selected track has empty baseUrl",
        )

    # Prefer json3 when possible
    fetch_url = base
    if "fmt=" not in fetch_url:
        fetch_url += ("&" if "?" in fetch_url else "?") + "fmt=json3"

    try:
        raw = http_get_text(fetch_url, headers={"Referer": "https://www.youtube.com/"})
    except Exception as e:
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube",
            url=watch_url,
            title=title,
            error=f"timedtext fetch failed: {e}",
            limits=["Prefer capturing the player-issued timedtext request in a browser"],
        )

    cues = _parse_timedtext_payload(raw)
    if not cues:
        limits.append(
            "timedtext returned empty body — common without full player tokens; "
            "use browser network capture (SKILL.md Y2-A)"
        )
        return ExtractResult(
            ok=False,
            platform="youtube",
            adapter="youtube",
            url=watch_url,
            title=title,
            language=prefer_lang or chosen.get("languageCode") or "",
            track=TrackInfo(
                language=chosen.get("languageCode") or "",
                kind=kind,
                source="youtube captionTracks (fetch empty)",
                label=_track_name(chosen),
            ),
            error="timedtext response had no usable cues",
            limits=limits,
            method="http_page_timedtext",
        )

    paragraphs = cues_to_paragraphs(cues)
    plain = paragraphs_to_text(paragraphs)
    return ExtractResult(
        ok=True,
        platform="youtube",
        adapter="youtube",
        url=watch_url,
        title=title,
        language=prefer_lang or chosen.get("languageCode") or "",
        track=TrackInfo(
            language=chosen.get("languageCode") or "",
            kind=kind,
            source="youtube watch page captionTracks + timedtext",
            label=_track_name(chosen),
        ),
        cues=cues,
        plain_text=plain,
        method="http_page_timedtext",
        limits=limits,
    )


def _parse_video_id(url: str) -> Optional[str]:
    s = (url or "").strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    if "://" not in s:
        s = "https://" + s
    parsed = urlparse(s)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        vid = parsed.path.strip("/").split("/")[0]
        return vid or None
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]
    m = re.search(r"/(shorts|embed|live)/([\w-]{11})", parsed.path)
    if m:
        return m.group(2)
    return None


def _extract_player_response(html: str) -> Optional[dict[str, Any]]:
    # ytInitialPlayerResponse = {...};
    m = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;", html, flags=re.S)
    if not m:
        m = re.search(
            r"var\s+ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;",
            html,
            flags=re.S,
        )
    if not m:
        return None
    blob = m.group(1)
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # Sometimes truncated by non-greedy match; try brace scan
        start = html.find("ytInitialPlayerResponse")
        if start < 0:
            return None
        brace = html.find("{", start)
        if brace < 0:
            return None
        data = _load_balanced_json(html, brace)
        return data


def _load_balanced_json(text: str, start: int) -> Optional[dict[str, Any]]:
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _caption_tracks(pr: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not pr:
        return []
    return (
        ((pr.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get(
            "captionTracks"
        )
        or []
    )


def _track_name(t: dict[str, Any]) -> str:
    name = t.get("name")
    if isinstance(name, dict):
        if name.get("simpleText"):
            return str(name["simpleText"])
        runs = name.get("runs") or []
        return "".join(r.get("text", "") for r in runs)
    return str(name or "")


def _select_track(
    tracks: list[dict[str, Any]], *, prefer_lang: str
) -> tuple[dict[str, Any], str]:
    def is_auto(t: dict[str, Any]) -> bool:
        kind = (t.get("kind") or "").lower()
        label = _track_name(t).lower()
        return kind == "asr" or "auto" in label or "自动" in label

    def score(t: dict[str, Any]) -> tuple[int, int, str]:
        auto = 1 if is_auto(t) else 0
        lang = (t.get("languageCode") or "").lower()
        p = (prefer_lang or "").lower()
        lang_hit = 0
        if p:
            if p == lang or lang.startswith(p) or p.startswith(lang):
                lang_hit = 2
            elif p[:2] and lang.startswith(p[:2]):
                lang_hit = 1
        # prefer human (auto=0), then lang match, then language code stable
        return (auto, -lang_hit, lang)

    ranked = sorted(tracks, key=score)
    chosen = ranked[0]
    return chosen, ("auto" if is_auto(chosen) else "human")


def _parse_timedtext_payload(raw: str) -> list[Cue]:
    raw = (raw or "").strip()
    if not raw:
        return []
    # JSON3
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        events = data.get("events") or []
        cues: list[Cue] = []
        for ev in events:
            segs = ev.get("segs")
            if not segs:
                continue
            if ev.get("aAppend") == 1 and not ev.get("dDurationMs"):
                continue
            text = "".join((s.get("utf8") or "") for s in segs).replace("\n", " ").strip()
            if not text:
                continue
            start_ms = float(ev.get("tStartMs") or 0)
            dur = ev.get("dDurationMs")
            end = (start_ms + float(dur)) / 1000.0 if dur is not None else None
            cues.append(Cue(start=start_ms / 1000.0, end=end, text=text))
        return cues

    # VTT-ish fallback
    if "WEBVTT" in raw[:20] or "-->" in raw:
        return _parse_vtt(raw)
    return []


def _parse_vtt(raw: str) -> list[Cue]:
    cues: list[Cue] = []
    blocks = re.split(r"\n\s*\n", raw.strip())
    for block in blocks:
        lines = [ln.strip("\ufeff") for ln in block.splitlines() if ln.strip()]
        if not lines or lines[0].startswith("WEBVTT"):
            continue
        time_line = None
        text_lines: list[str] = []
        for ln in lines:
            if "-->" in ln:
                time_line = ln
            elif time_line is not None:
                text_lines.append(re.sub(r"<[^>]+>", "", ln))
        if not time_line or not text_lines:
            continue
        m = re.match(
            r"(\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(\d{2}:)?\d{2}:\d{2}\.\d{3}",
            time_line,
        )
        if not m:
            continue
        parts = time_line.split("-->")
        start = _ts_to_sec(parts[0].strip().split()[0])
        end = _ts_to_sec(parts[1].strip().split()[0])
        cues.append(Cue(start=start, end=end, text=" ".join(text_lines).strip()))
    return cues


def _ts_to_sec(ts: str) -> float:
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)
