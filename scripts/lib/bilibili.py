"""Bilibili adapter: public APIs → unified cues."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

import time

from .clean import cues_to_paragraphs, paragraphs_to_text
from .http_util import http_get_json
from .models import Cue, ExtractResult, TrackInfo


def _api_json(url: str, *, headers: dict | None = None, retries: int = 4) -> dict:
    """Bilibili JSON APIs sometimes return code=-429 in body; retry those."""
    last: dict | None = None
    for attempt in range(retries):
        data = http_get_json(url, headers=headers, retries=1)
        last = data if isinstance(data, dict) else {"code": -1, "message": str(data)}
        code = last.get("code")
        if code == 0:
            return last
        # rate limit or soft errors
        if code in (-429, 429, -412) or "频率" in str(last.get("message") or ""):
            time.sleep(1.8 * (attempt + 1))
            continue
        break
    assert last is not None
    raise RuntimeError(
        f"API error code={last.get('code')} message={last.get('message')} url={url}"
    )


def extract_bilibili(url: str, *, prefer_lang: str = "") -> ExtractResult:
    bvid = _parse_bvid(url)
    if not bvid:
        return ExtractResult(
            ok=False,
            platform="bilibili",
            adapter="bilibili",
            url=url,
            error="Could not parse BV id from URL",
        )

    try:
        view = _api_json(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        )
    except Exception as e:
        return ExtractResult(
            ok=False,
            platform="bilibili",
            adapter="bilibili",
            url=url,
            error=str(e),
        )

    data = view["data"]
    title = data.get("title") or ""
    cid = data.get("cid")
    desc = data.get("desc") or ""
    if not cid:
        return ExtractResult(
            ok=False,
            platform="bilibili",
            adapter="bilibili",
            url=url,
            title=title,
            error="Missing cid in view response",
        )

    try:
        dm = _api_json(
            f"https://api.bilibili.com/x/v2/dm/view?oid={cid}&type=1",
            headers={"Referer": "https://www.bilibili.com/"},
        )
    except Exception as e:
        return ExtractResult(
            ok=False,
            platform="bilibili",
            adapter="bilibili",
            url=url,
            title=title,
            chapters=desc,
            error=str(e),
        )

    subs = (((dm.get("data") or {}).get("subtitle") or {}).get("subtitles")) or []
    if not subs:
        return ExtractResult(
            ok=False,
            platform="bilibili",
            adapter="bilibili",
            url=url,
            title=title,
            chapters=desc,
            error="No subtitle tracks in dm/view (data.subtitle.subtitles empty)",
            limits=["view.subtitle.list is often empty; dm/view was checked"],
        )

    chosen, kind = _select_track(subs, prefer_lang=prefer_lang)
    sub_url = chosen.get("subtitle_url") or ""
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url

    body_json = http_get_json(sub_url, headers={"Referer": "https://www.bilibili.com/"})
    body = body_json.get("body") or []
    cues: list[Cue] = []
    for item in body:
        text = (item.get("content") or "").strip()
        if not text:
            continue
        cues.append(
            Cue(
                start=float(item.get("from", 0) or 0),
                end=float(item.get("to", 0) or 0) or None,
                text=text,
            )
        )

    paragraphs = cues_to_paragraphs(cues, join_without_space=True)
    plain = paragraphs_to_text(paragraphs)
    lan = chosen.get("lan") or ""
    lan_doc = chosen.get("lan_doc") or ""

    return ExtractResult(
        ok=True,
        platform="bilibili",
        adapter="bilibili",
        url=url if "://" in url else f"https://www.bilibili.com/video/{bvid}",
        title=title,
        language=prefer_lang or lan,
        track=TrackInfo(
            language=lan,
            kind=kind,
            source="bilibili dm/view + subtitle_url JSON",
            label=lan_doc,
        ),
        cues=cues,
        plain_text=plain,
        chapters=desc,
        method="http_api",
    )


def _parse_bvid(url: str) -> Optional[str]:
    s = (url or "").strip()
    if re.fullmatch(r"BV[\w]+", s):
        return s
    m = re.search(r"(BV[\w]+)", s)
    if m:
        return m.group(1)
    # short links need redirect; try resolve
    if "b23.tv" in s:
        try:
            from .http_util import http_get

            # urllib follows redirects by default for http_get via urlopen
            # but we only need final URL from a HEAD-like GET of empty
            import urllib.request
            from .http_util import DEFAULT_UA

            req = urllib.request.Request(s, headers={"User-Agent": DEFAULT_UA}, method="GET")
            with urllib.request.urlopen(req, timeout=20) as resp:
                final = resp.geturl()
            m2 = re.search(r"(BV[\w]+)", final)
            return m2.group(1) if m2 else None
        except Exception:
            return None
    return None


def _select_track(subs: list[dict], *, prefer_lang: str) -> tuple[dict, str]:
    def is_auto(s: dict) -> bool:
        lan = (s.get("lan") or "").lower()
        doc = s.get("lan_doc") or ""
        return "ai" in lan or "ai" in doc.lower() or "自动" in doc

    def lang_score(s: dict) -> int:
        if not prefer_lang:
            return 0
        p = prefer_lang.lower()
        lan = (s.get("lan") or "").lower()
        doc = (s.get("lan_doc") or "").lower()
        score = 0
        if p in lan or p in doc:
            score += 10
        if p.startswith("zh") and ("zh" in lan or "中" in (s.get("lan_doc") or "")):
            score += 8
        if p.startswith("en") and ("en" in lan or "英" in (s.get("lan_doc") or "")):
            score += 8
        return score

    human = [s for s in subs if not is_auto(s)]
    auto = [s for s in subs if is_auto(s)]

    def pick(pool: list[dict]) -> Optional[dict]:
        if not pool:
            return None
        ranked = sorted(pool, key=lambda s: (-lang_score(s), s.get("lan") or ""))
        if prefer_lang:
            best = ranked[0]
            if lang_score(best) > 0:
                return best
        return ranked[0]

    chosen = pick(human) or pick(auto) or subs[0]
    kind = "auto" if is_auto(chosen) else "human"
    return chosen, kind
