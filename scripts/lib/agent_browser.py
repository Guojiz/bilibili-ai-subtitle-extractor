"""Drive vercel-labs agent-browser for page inject + export.

Generic access backend: open page, inject export_core.js, call __ovsExportSubtitle.
Requires `agent-browser` on PATH (npm i -g agent-browser && agent-browser install).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .models import Cue, ExtractResult, TrackInfo

CORE = (
    Path(__file__).resolve().parent.parent / "page_inject" / "export_core.js"
)


class AgentBrowserError(RuntimeError):
    pass


def resolve_agent_browser() -> str:
    """Return absolute path to agent-browser CLI (Windows npm .cmd aware)."""
    for name in (
        "agent-browser",
        "agent-browser.cmd",
        "agent-browser.CMD",
        "agent-browser.exe",
    ):
        w = shutil.which(name)
        if w:
            return w
    # Common npm global location on Windows
    appdata = os.environ.get("APPDATA") or ""
    for rel in (
        Path(appdata) / "npm" / "agent-browser.cmd",
        Path(appdata) / "npm" / "agent-browser.exe",
    ):
        if rel.is_file():
            return str(rel)
    return ""


def agent_browser_available() -> bool:
    return bool(resolve_agent_browser())


def _run(
    args: list[str],
    *,
    timeout: float = 120.0,
    input_text: Optional[str] = None,
) -> str:
    env = os.environ.copy()
    cli = resolve_agent_browser()
    if not cli:
        raise AgentBrowserError(
            "agent-browser not found. Install: npm install -g agent-browser && agent-browser install"
        )
    # Replace bare command name with resolved path
    if args and args[0] in (
        "agent-browser",
        "agent-browser.cmd",
        "agent-browser.exe",
    ):
        cmd = [cli, *args[1:]]
    else:
        cmd = args
    try:
        # shell=True on Windows helps .cmd shims; use list form with resolved .cmd
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            shell=False,
        )
    except FileNotFoundError as e:
        raise AgentBrowserError(
            "agent-browser not found. Install: npm install -g agent-browser && agent-browser install"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise AgentBrowserError(f"agent-browser timed out: {args}") from e

    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    if proc.returncode != 0:
        raise AgentBrowserError(
            f"agent-browser failed ({proc.returncode}): {cmd}\n{out[:1500]}"
        )
    return proc.stdout or ""


def extract_with_agent_browser(
    url: str,
    *,
    prefer_lang: str = "",
    settle_seconds: float = 4.0,
    headed: bool = False,
    retries: int = 2,
) -> ExtractResult:
    if not agent_browser_available():
        return ExtractResult(
            ok=False,
            platform="unknown",
            adapter="agent_browser",
            url=url,
            error="agent-browser CLI not on PATH",
            limits=[
                "npm install -g agent-browser",
                "agent-browser install",
            ],
            method="agent-browser",
        )
    if not CORE.is_file():
        return ExtractResult(
            ok=False,
            platform="unknown",
            adapter="agent_browser",
            url=url,
            error=f"Missing inject core: {CORE}",
            method="agent-browser",
        )

    last_err = ""
    for attempt in range(max(1, retries)):
        try:
            # Fresh page each attempt (avoids stale hooks / rate-limit noise)
            try:
                _run(["agent-browser", "close"], timeout=30)
            except AgentBrowserError:
                pass

            open_cmd = [
                "agent-browser",
                "open",
                "--init-script",
                str(CORE),
                url,
            ]
            if headed:
                open_cmd.insert(1, "--headed")
            _run(open_cmd, timeout=60)
            time.sleep(settle_seconds)

            # Re-inject core via temp file (PowerShell-friendly, no stdin issues)
            core_js = CORE.read_text(encoding="utf-8")
            tmp = Path(os.environ.get("TEMP") or ".") / f"ovs-core-{os.getpid()}.js"
            tmp.write_text(core_js, encoding="utf-8")
            try:
                # eval file contents by reading in python and passing as arg can break
                # on size/quotes — use stdin when possible; Windows fallback: -b base64
                import base64

                b64 = base64.b64encode(core_js.encode("utf-8")).decode("ascii")
                _run(["agent-browser", "eval", "-b", b64], timeout=60)
            finally:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

            time.sleep(1.2)
            lang_lit = json.dumps(prefer_lang or "")
            eval_js = (
                "(async () => {"
                "  if (typeof window.__ovsExportSubtitle !== 'function') {"
                "    return JSON.stringify({ok:false,error:'export core not injected'});"
                "  }"
                f"  try {{"
                f"    const r = await window.__ovsExportSubtitle({{ lang: {lang_lit} }});"
                "    return JSON.stringify(r);"
                "  } catch (e) {"
                "    return JSON.stringify({ok:false,error:String(e && e.message || e)});"
                "  }"
                "})()"
            )
            raw_out = _run(["agent-browser", "eval", eval_js], timeout=120).strip()
            data = _parse_eval_json(raw_out)
            result = _result_from_page(data, url=url)
            if result.ok:
                return result
            last_err = result.error or "empty result"
            # retry rate limits
            if "频率" in last_err or "429" in last_err or "rate" in last_err.lower():
                time.sleep(2.5 * (attempt + 1))
                continue
            # non-rate failure: still retry once for flaky SPA
            time.sleep(1.5)
        except AgentBrowserError as e:
            last_err = str(e)
            time.sleep(1.5)
        except Exception as e:
            last_err = str(e)
            time.sleep(1.5)

    return ExtractResult(
        ok=False,
        platform="unknown",
        adapter="agent_browser",
        url=url,
        error=last_err or "agent-browser extract failed",
        method="agent-browser",
        limits=[
            "npm install -g agent-browser",
            "Ensure Chrome/Chromium is available (agent-browser install may fail on slow networks)",
            "Bilibili HTTP path is more reliable: python scripts/extract_subtitles.py BV... ",
            "YouTube: enable CC once in headed mode if timedtext empty: --agent-browser --headed",
        ],
    )


def _parse_eval_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    # agent-browser may wrap output; try direct then scan for JSON object
    try:
        val = json.loads(text)
        if isinstance(val, str):
            return json.loads(val)
        if isinstance(val, dict):
            return val
    except json.JSONDecodeError:
        pass
    # find last {...}
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        blob = text[start : end + 1]
        val = json.loads(blob)
        if isinstance(val, str):
            return json.loads(val)
        return val
    raise AgentBrowserError(f"Could not parse eval JSON: {text[:500]}")


def _result_from_page(data: dict[str, Any], *, url: str) -> ExtractResult:
    if not data.get("ok", True) and data.get("error"):
        return ExtractResult(
            ok=False,
            platform=str(data.get("platform") or "unknown"),
            adapter="agent_browser",
            url=str(data.get("url") or url),
            title=str(data.get("title") or ""),
            error=str(data.get("error")),
            limits=list(data.get("limits") or []),
            method="agent-browser",
        )

    cues_raw = data.get("cues") or []
    cues = [
        Cue(
            start=float(c.get("start", 0) or 0),
            end=float(c["end"]) if c.get("end") is not None else None,
            text=str(c.get("text") or ""),
        )
        for c in cues_raw
        if (c.get("text") or "").strip()
    ]
    track = data.get("track") or {}
    kind = track.get("kind") or "unknown"
    if kind not in ("human", "auto", "unknown"):
        kind = "unknown"

    return ExtractResult(
        ok=bool(cues) or bool(data.get("plain_text")),
        platform=str(data.get("platform") or "unknown"),
        adapter="agent_browser",
        url=str(data.get("url") or url),
        title=str(data.get("title") or ""),
        language=str(data.get("language") or ""),
        track=TrackInfo(
            language=str(track.get("language") or ""),
            kind=kind,  # type: ignore[arg-type]
            source=str(track.get("source") or "page_inject"),
            label=str(track.get("label") or ""),
        ),
        cues=cues,
        plain_text=str(data.get("plain_text") or ""),
        chapters=str(data.get("chapters") or ""),
        method=str(data.get("method") or "agent-browser"),
        limits=list(data.get("limits") or []),
        error="" if cues or data.get("plain_text") else "empty result from page inject",
    )
