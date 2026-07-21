"""
B站实测：MV3 扩展形态，访问带 AI 字幕的视频并读取 window.__USE__。
运行：xvfb-run -a python3 tests/test_bilibili.py   （需 playwright + chromium）
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

EXT_DIR = str(Path(__file__).resolve().parent.parent / "extension")
BV_URL = "https://www.bilibili.com/video/BV1P6KA6NEDq"  # 有 ai-zh 字幕，可按需更换

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        "/tmp/use-test-profile",
        headless=False,  # 扩展需要 headful（无显示环境用 xvfb-run）
        args=[f"--load-extension={EXT_DIR}", f"--disable-extensions-except={EXT_DIR}", "--no-sandbox"],
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("console", lambda m: print("[console]", m.text) if "[USE]" in m.text else None)
    page.goto(BV_URL, wait_until="load", timeout=60000)

    ok = False
    for _ in range(30):  # B站可能二次跳转，容忍上下文销毁
        try:
            if page.evaluate("typeof window.__USE__ === 'object'"):
                ok = True
                break
        except Exception:
            pass
        page.wait_for_timeout(1000)
    assert ok, "__USE__ 未注入"

    n = page.evaluate("window.__USE__.waitFor(1, 25000)")
    print("轨道数:", n)
    print(json.dumps(page.evaluate("window.__USE__.list()"), ensure_ascii=False, indent=2))
    print("meta:", json.dumps(page.evaluate("window.__USE__.meta()"), ensure_ascii=False)[:200])
    if n:
        print("text 前 300 字:", (page.evaluate("window.__USE__.text()") or "")[:300])
        print("srt 前 200 字:", (page.evaluate("window.__USE__.srt()") or "")[:200])
    ctx.close()
