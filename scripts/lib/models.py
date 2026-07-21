"""Shared result types for the platform-agnostic subtitle pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


TrackKind = Literal["human", "auto", "unknown"]


@dataclass
class Cue:
    start: float
    text: str
    end: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"start": self.start, "text": self.text}
        if self.end is not None:
            d["end"] = self.end
        return d


@dataclass
class TrackInfo:
    language: str
    kind: TrackKind
    source: str
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractResult:
    ok: bool
    platform: str
    adapter: str
    url: str
    title: str = ""
    language: str = ""
    track: Optional[TrackInfo] = None
    cues: list[Cue] = field(default_factory=list)
    plain_text: str = ""
    chapters: str = ""
    method: str = ""
    error: str = ""
    limits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "platform": self.platform,
            "adapter": self.adapter,
            "url": self.url,
            "title": self.title,
            "language": self.language,
            "track": self.track.to_dict() if self.track else None,
            "cue_count": len(self.cues),
            "cues": [c.to_dict() for c in self.cues],
            "plain_text": self.plain_text,
            "chapters": self.chapters,
            "method": self.method,
            "error": self.error,
            "limits": self.limits,
        }

    def to_markdown(self) -> str:
        if not self.ok:
            lines = [
                "# Subtitle extraction failed",
                "",
                f"- URL: {self.url}",
                f"- Platform: {self.platform}",
                f"- Adapter: {self.adapter}",
                f"- Error: {self.error}",
            ]
            if self.limits:
                lines.append("- Limits:")
                lines.extend(f"  - {x}" for x in self.limits)
            return "\n".join(lines) + "\n"

        track = self.track
        lines = [
            f"# {self.title or '(untitled)'}",
            "",
            "## Video info",
            "",
            f"- Platform: {self.platform}",
            f"- Adapter: {self.adapter}",
            f"- URL: {self.url}",
            f"- Language: {self.language or '(unspecified)'}",
            f"- Track kind: {track.kind if track else 'unknown'}",
            f"- Track label: {(track.label if track else '') or '-'}",
            f"- Method: {self.method or '-'}",
            f"- Cue count: {len(self.cues)}",
            "",
        ]
        if self.chapters:
            lines += ["## Chapters / description", "", self.chapters.strip(), ""]
        lines += ["## Transcript", "", self.plain_text.strip(), ""]
        if self.limits:
            lines += ["## Limits", ""] + [f"- {x}" for x in self.limits] + [""]
        return "\n".join(lines)
