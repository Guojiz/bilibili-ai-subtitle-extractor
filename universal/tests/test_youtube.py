"""
YouTube 路径端到端测试（待测试项）：mock captionTracks + 路由拦截 timedtext，
不需要真实访问 YouTube。覆盖：
  1. captionTracks -> baseUrl(fmt=json3) -> 解析上报（人工 + asr 两条轨）
  2. aAppend 碎片事件被过滤（回归）
  3. baseUrl 返回空 body 时自动打开 CC、走嗅探路径，且不上报假轨道
运行：python3 tests/test_youtube.py   （无需本地 http server）
"""
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
USERJS = str(ROOT / "dist" / "universal-subtitle-extractor.user.js")
JSON3 = json.loads((ROOT / "tests" / "site" / "youtube-json3.json").read_text(encoding="utf-8"))
JSON3_ASR = copy.deepcopy(JSON3)
JSON3_ASR["events"][0]["segs"] = [{"utf8": "Auto hello"}, {"utf8": "world"}]

TIMEDTEXT = "https://www.youtube.com/api/timedtext"
CAPTION_TRACKS = [
    {"baseUrl": TIMEDTEXT + "?v=test1234567&lang=en",
     "name": {"simpleText": "English"}, "languageCode": "en"},
    {"baseUrl": TIMEDTEXT + "?v=test1234567&lang=en&kind=asr",
     "name": {"simpleText": "English (auto-generated)"}, "languageCode": "en", "kind": "asr"},
]

PAGE_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Mock - YouTube</title></head>
<body>
<div id="movie_player"></div>
<button class="ytp-subtitles-button" aria-pressed="false"
        onclick="window.__ccClicked=(window.__ccClicked||0)+1">CC</button>
<script>
window.ytInitialPlayerResponse = %s;
</script>
</body></html>""" % json.dumps({
    "videoDetails": {"title": "Mock Video", "lengthSeconds": "42"},
    "captions": {"playerCaptionsTracklistRenderer": {"captionTracks": CAPTION_TRACKS}},
})


def make_ctx(p, timedtext_body):
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context()
    ctx.add_init_script(path=USERJS)

    def handler(route):
        url = route.request.url
        if "timedtext" in url:
            body = timedtext_body(url)
            route.fulfill(status=200, content_type="application/json", body=body)
        else:
            route.fulfill(status=200, content_type="text/html", body=PAGE_HTML)

    ctx.route("https://www.youtube.com/**", handler)
    return browser, ctx


def test_full_chain(p):
    def body(url):
        return json.dumps(JSON3_ASR if "kind=asr" in url else JSON3)

    browser, ctx = make_ctx(p, body)
    page = ctx.new_page()
    page.goto("https://www.youtube.com/watch?v=test1234567", wait_until="load")
    page.evaluate("window.__USE__.waitFor(2, 15000)")
    tracks = page.evaluate("window.__USE__.list()")
    yt = [t for t in tracks if t["site"] == "youtube" and t["source"] == "api"]
    assert len(yt) == 2, tracks
    assert sorted(t["isAI"] for t in yt) == [False, True], yt
    for t in yt:
        cues = page.evaluate("window.__USE__.get(%s).cues" % json.dumps(t["id"]))
        assert len(cues) == 3, cues  # aAppend 事件已过滤，否则是 4 条
        assert cues[0]["start"] == 0 and cues[0]["end"] == 1.5, cues[0]
    text = page.evaluate("window.__USE__.text()")
    assert "Hello world" in text, text
    meta = page.evaluate("window.__USE__.meta()")
    assert meta.get("site") == "youtube" and meta.get("title") == "Mock Video", meta
    assert page.evaluate("window.__ccClicked || 0") == 0  # 直取成功不应动 CC
    browser.close()
    print("YOUTUBE_FULL_CHAIN_OK", json.dumps(yt, ensure_ascii=False))


def test_empty_body_fallback(p):
    browser, ctx = make_ctx(p, lambda url: "")
    page = ctx.new_page()
    page.goto("https://www.youtube.com/watch?v=test1234567", wait_until="load")
    page.wait_for_function("() => (window.__ccClicked || 0) >= 1", timeout=15000)
    tracks = page.evaluate("window.__USE__.list()")
    assert not [t for t in tracks if t["source"] == "api"], tracks  # 空 body 不能上报假轨道
    browser.close()
    print("YOUTUBE_EMPTY_FALLBACK_OK (auto CC clicked)")


with sync_playwright() as p:
    test_full_chain(p)
    test_empty_body_fallback(p)
    print("YOUTUBE_ALL_OK")
