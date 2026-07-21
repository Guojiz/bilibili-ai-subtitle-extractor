"""Normalize cue lists into readable paragraphs (site-agnostic)."""

from __future__ import annotations

from .models import Cue


def cues_to_paragraphs(
    cues: list[Cue],
    *,
    gap_seconds: float = 1.5,
    max_chars: int = 260,
    join_without_space: bool = False,
) -> list[str]:
    """Merge short timed fragments into paragraphs."""
    paragraphs: list[str] = []
    current: list[str] = []
    last_to: float | None = None
    char_count = 0

    for cue in cues:
        text = (cue.text or "").strip()
        if not text:
            continue
        start = float(cue.start)
        end = float(cue.end if cue.end is not None else start)
        gap = start - last_to if last_to is not None else 0.0

        if current and (gap > gap_seconds or char_count >= max_chars):
            paragraphs.append(_join(current, join_without_space))
            current = []
            char_count = 0

        current.append(text)
        char_count += len(text)
        last_to = end

    if current:
        paragraphs.append(_join(current, join_without_space))

    cleaned: list[str] = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p[-1] not in "。！？!?….":
            # Light terminal punctuation only; agents may refine further.
            p += "。" if _looks_cjk(p) else "."
        cleaned.append(p)
    return cleaned


def paragraphs_to_text(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraphs)


def _join(parts: list[str], join_without_space: bool) -> str:
    if join_without_space:
        return "".join(parts).strip()
    # Prefer no space for CJK-heavy chunks; space for latin-heavy.
    sample = "".join(parts[:3])
    if _looks_cjk(sample):
        return "".join(parts).strip()
    return " ".join(parts).strip()


def _looks_cjk(text: str) -> bool:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk >= max(1, len(text) // 4)
