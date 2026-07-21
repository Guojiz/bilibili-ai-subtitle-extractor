"""Minimal HTTP helpers (stdlib only)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def http_get(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> bytes:
    req_headers = {"User-Agent": DEFAULT_UA}
    if headers:
        req_headers.update(headers)
    last_err: Exception | None = None
    for attempt in range(max(1, retries)):
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read() if hasattr(e, "read") else b""
            # Retry rate limits / transient server errors
            if e.code in (429, 502, 503, 504) and attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
                last_err = RuntimeError(
                    f"HTTP {e.code} for {url}: {body[:200]!r}"
                )
                continue
            raise RuntimeError(f"HTTP {e.code} for {url}: {body[:200]!r}") from e
        except urllib.error.URLError as e:
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
                last_err = RuntimeError(f"Request failed for {url}: {e}")
                continue
            raise RuntimeError(f"Request failed for {url}: {e}") from e
    if last_err:
        raise last_err
    raise RuntimeError(f"Request failed for {url}")


def http_get_json(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> Any:
    raw = http_get(url, headers=headers, timeout=timeout, retries=retries)
    return json.loads(raw.decode("utf-8", errors="replace"))


def http_get_text(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> str:
    raw = http_get(url, headers=headers, timeout=timeout, retries=retries)
    return raw.decode("utf-8", errors="replace")
