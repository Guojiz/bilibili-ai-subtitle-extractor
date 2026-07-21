"""Minimal Kimi WebBridge client (original, optional dependency at runtime)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# Never send local daemon traffic through system proxies.
for _k in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(_k, None)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DEFAULT_URL = "http://127.0.0.1:10086/command"


class WebBridgeError(RuntimeError):
    pass


class WebBridge:
    def __init__(self, session: str, *, base_url: str = DEFAULT_URL) -> None:
        self.session = session
        self.base_url = base_url

    def call(self, action: str, args: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        body = {"action": action, "args": args or {}, "session": self.session}
        path = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / (
            f"webbridge-req-{uuid4().hex}.json"
        )
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=path.read_bytes(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _OPENER.open(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
        except Exception as e:
            raise WebBridgeError(f"WebBridge unreachable: {e}") from e
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise WebBridgeError(f"Non-JSON response: {raw[:300]}") from e
        return data

    def wait_ready(self, attempts: int = 15) -> None:
        last: Any = None
        for _ in range(attempts):
            last = self.call("list_tabs")
            if last.get("ok"):
                return
            msg = json.dumps(last, ensure_ascii=False)
            if "no extension" in msg.lower():
                time.sleep(1.2)
                continue
            if "10061" in msg or "refused" in msg.lower():
                time.sleep(1.0)
                continue
            time.sleep(0.8)
        raise WebBridgeError(f"WebBridge extension not ready: {last}")

    def evaluate(self, code: str) -> Any:
        res = self.call("evaluate", {"code": code})
        if not res.get("ok"):
            raise WebBridgeError(f"evaluate failed: {res}")
        data = res.get("data") or {}
        if isinstance(data, dict) and "value" in data:
            return data["value"]
        return data

    def navigate(self, url: str, *, group_title: str = "字幕提取") -> dict[str, Any]:
        res = self.call(
            "navigate",
            {"url": url, "newTab": True, "group_title": group_title},
        )
        if not res.get("ok"):
            # Timeout may still leave a usable tab
            err = res.get("error") or res
            # still return so caller can try evaluate
            return {"warning": err, "raw": res}
        return res.get("data") or res
