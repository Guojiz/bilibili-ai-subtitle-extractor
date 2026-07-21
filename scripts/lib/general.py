"""Generic web adapter placeholder: honest failure with discovery guidance."""

from __future__ import annotations

from .models import ExtractResult


def extract_general(url: str, *, prefer_lang: str = "") -> ExtractResult:
    _ = prefer_lang
    return ExtractResult(
        ok=False,
        platform="unknown",
        adapter="general",
        url=url,
        error=(
            "No dedicated adapter for this URL. "
            "Use the shared discovery checklist in SKILL.md "
            "(tracks, VTT/SRT, transcript UI, player network, then browser fallback)."
        ),
        limits=[
            "This CLI implements bilibili + best-effort youtube only",
            "Agents can still follow SKILL.md generic discovery without this script",
        ],
        method="none",
    )
