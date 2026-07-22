#!/usr/bin/env python3
"""
Standalone CLI: online video URL → existing captions/transcript.

Part of the platform-agnostic Agent Recipe.
- Works alone from the command line (no GitLearnOS required).
- GitLearnOS / other apps are optional callers only.
- Stdlib only. Original code for this repository.

Examples:
  python scripts/extract_subtitles.py "https://www.bilibili.com/video/BVxxxxxxxx"
  python scripts/extract_subtitles.py BV1SA7B6iEJg --lang zh -o out.md
  python scripts/extract_subtitles.py "https://www.youtube.com/watch?v=..." --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/extract_subtitles.py` without installing a package.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.agent_browser import (  # noqa: E402
    agent_browser_available,
    extract_with_agent_browser,
)
from lib.bilibili import extract_bilibili  # noqa: E402
from lib.backblaze import B2Config, object_key, upload_bytes  # noqa: E402
from lib.detect import detect_adapter  # noqa: E402
from lib.general import extract_general  # noqa: E402
from lib.models import ExtractResult  # noqa: E402
from lib.youtube import extract_youtube  # noqa: E402


def extract(
    url: str,
    *,
    lang: str = "",
    adapter: str = "auto",
    browser: bool = False,
    agent_browser: bool = False,
    headed: bool = False,
) -> ExtractResult:
    """
    Access backends (generic):
      1) agent-browser inject (preferred when requested / installed for page sites)
      2) HTTP adapters (bilibili full, youtube best-effort)
      3) WebBridge browser fallback (--browser)
    """
    # Force agent-browser path (any site: inject page core)
    if agent_browser:
        return extract_with_agent_browser(
            url, prefer_lang=lang, headed=headed
        )

    ad = adapter if adapter and adapter != "auto" else detect_adapter(url)

    if ad == "bilibili":
        return extract_bilibili(url, prefer_lang=lang)

    if ad == "youtube":
        result = extract_youtube(url, prefer_lang=lang, use_browser=False)
        if result.ok:
            return result
        # Only escalate when user asked for a browser backend
        if not browser:
            result.limits = list(result.limits or []) + [
                "HTTP timedtext often empty without player session tokens",
                "Retry with: --agent-browser   (recommended)",
                "Or:          --browser         (agent-browser if installed, else WebBridge)",
            ]
            return result
        if agent_browser_available():
            ab = extract_with_agent_browser(
                url, prefer_lang=lang, headed=headed
            )
            if ab.ok:
                return ab
            # fall through to WebBridge with both errors
            wb = extract_youtube(url, prefer_lang=lang, use_browser=True)
            if not wb.ok:
                wb.limits = list(wb.limits or []) + [
                    f"agent-browser also failed: {ab.error}"
                ]
            return wb
        return extract_youtube(url, prefer_lang=lang, use_browser=True)

    # Unknown site: HTTP has no adapter; browser only if requested
    if browser and agent_browser_available():
        return extract_with_agent_browser(url, prefer_lang=lang, headed=headed)
    gen = extract_general(url, prefer_lang=lang)
    if browser:
        gen.limits = list(gen.limits or []) + [
            "Install agent-browser for page inject: npm i -g agent-browser && agent-browser install",
            "python scripts/extract_subtitles.py <url> --agent-browser",
        ]
    return gen


def _should_escalate_to_page(result: ExtractResult) -> bool:
    err = (result.error or "").lower()
    return (
        "empty" in err
        or "no usable cues" in err
        or "timedtext" in err
        or "blocked" in err
        or "failed to fetch" in err
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Extract existing subtitles/transcripts from an online video URL. "
            "Standalone tool; no external learning app required."
        )
    )
    p.add_argument("url", help="Video URL, BV id, or YouTube id/URL")
    p.add_argument(
        "--lang",
        default="",
        help="Preferred language code or hint (e.g. zh, en)",
    )
    p.add_argument(
        "--adapter",
        default="auto",
        choices=["auto", "bilibili", "youtube", "general"],
        help="Force adapter (default: auto-detect)",
    )
    p.add_argument(
        "-o",
        "--output",
        default="",
        help="Write markdown (or JSON if --json) to this path",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of markdown",
    )
    p.add_argument(
        "--cues-json",
        default="",
        help="Optional path to write raw cue list JSON",
    )
    p.add_argument(
        "--browser",
        action="store_true",
        help=(
            "Escalate to a real browser when HTTP fails. Prefers agent-browser inject "
            "if installed; else Kimi WebBridge."
        ),
    )
    p.add_argument(
        "--agent-browser",
        action="store_true",
        help=(
            "Force vercel-labs agent-browser: open URL, inject page_inject/export_core.js, "
            "call window.__ovsExportSubtitle. Best for generic page injection."
        ),
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window when using agent-browser",
    )
    p.add_argument(
        "--b2-upload",
        action="store_true",
        help="Upload the emitted transcript artifact to Backblaze B2",
    )
    p.add_argument(
        "--b2-prefix",
        default="transcripts",
        help="Backblaze object-key prefix (default: transcripts)",
    )
    p.add_argument(
        "--b2-dry-run",
        action="store_true",
        help="Print the planned Backblaze object key without uploading",
    )
    args = p.parse_args(argv)

    try:
        result = extract(
            args.url,
            lang=args.lang,
            adapter=args.adapter,
            browser=args.browser,
            agent_browser=args.agent_browser,
            headed=args.headed,
        )
    except Exception as e:
        result = ExtractResult(
            ok=False,
            platform="unknown",
            adapter=args.adapter,
            url=args.url,
            error=str(e),
        )

    if args.json:
        payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    else:
        payload = result.to_markdown()

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")

    if args.cues_json and result.cues:
        Path(args.cues_json).write_text(
            json.dumps([c.to_dict() for c in result.cues], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if (args.b2_upload or args.b2_dry_run) and result.ok:
        filename = Path(args.output).name if args.output else (
            "transcript.json" if args.json else "transcript.md"
        )
        raw = payload.encode("utf-8")
        if args.b2_dry_run:
            print(
                json.dumps(
                    {
                        "provider": "Backblaze B2",
                        "dry_run": True,
                        "key": object_key(args.b2_prefix, filename, raw),
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
        else:
            receipt = upload_bytes(
                raw,
                filename=filename,
                content_type=(
                    "application/json; charset=utf-8"
                    if args.json
                    else "text/markdown; charset=utf-8"
                ),
                metadata={
                    "platform": result.platform,
                    "language": result.language,
                    "adapter": result.adapter,
                    "cue-count": str(len(result.cues)),
                },
                prefix=args.b2_prefix,
                config=B2Config.from_env(),
            )
            print(json.dumps(receipt, indent=2), file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
