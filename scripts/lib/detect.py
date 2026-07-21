"""URL → adapter routing (extensible)."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def detect_adapter(url: str) -> str:
    """Return adapter id: bilibili | youtube | general."""
    u = (url or "").strip()
    if not u:
        return "general"

    # Bare BV id
    if re.fullmatch(r"BV[\w]+", u):
        return "bilibili"

    host = urlparse(u if "://" in u else "https://" + u).netloc.lower()
    path = urlparse(u if "://" in u else "https://" + u).path

    if "bilibili.com" in host or host.endswith("b23.tv") or host == "b23.tv":
        return "bilibili"
    if "youtube.com" in host or "youtu.be" in host or "youtube-nocookie.com" in host:
        return "youtube"
    if re.search(r"/video/BV[\w]+", path):
        return "bilibili"
    return "general"
