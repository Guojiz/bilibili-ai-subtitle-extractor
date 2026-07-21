"""
解析器单元测试：json3 / TTML / VTT / SRT，通过 __USE__.parse 在页面内执行。
运行：先 python3 -m http.server 8899 -d tests/site &  再 python3 tests/test_parsers.py
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

USERJS = str(Path(__file__).resolve().parent.parent / "dist" / "universal-subtitle-extractor.user.js")

JSON3 = {"events": [
    {"tStartMs": 0, "dDurationMs": 1500, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
    {"tStartMs": 1500, "aAppend": 1, "segs": [{"utf8": " (append fragment)"}]},
    {"tStartMs": 1600, "dDurationMs": 1400, "segs": [{"utf8": "second\n"}, {"utf8": "cue"}]},
    {"tStartMs": 3200, "dDurationMs": 1000, "segs": [{"utf8": "third"}]},
]}
TTML = """<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div>
<p begin="00:00:01.000" end="00:00:03.500">clock time</p>
<p begin="4s" end="6.5s">offset time</p>
<p begin="7s" dur="2s">dur attr</p></div></body></tt>"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = b.new_context()
    ctx.add_init_script(path=USERJS)
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1:8899/index.html", wait_until="load")
    pg.wait_for_function("() => !!window.__USE__")
    r1 = pg.evaluate("window.__USE__.parse(%s, 'https://www.youtube.com/api/timedtext?fmt=json3')" % json.dumps(json.dumps(JSON3)))
    assert r1["format"] == "youtube-json3" and len(r1["cues"]) == 3, r1
    r2 = pg.evaluate("window.__USE__.parse(%s, 'https://x.com/a.ttml')" % json.dumps(TTML))
    assert r2["format"] == "ttml" and len(r2["cues"]) == 3, r2
    print("PARSERS_OK", json.dumps(r1, ensure_ascii=False), json.dumps(r2, ensure_ascii=False))
    b.close()
