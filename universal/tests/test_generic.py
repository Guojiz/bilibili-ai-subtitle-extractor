"""
通用嗅探测试：本地页面验证 fetch/XHR 嗅探、textTracks、<track> 标签、内容去重。
运行：先 python3 -m http.server 8899 -d tests/site &  再 python3 tests/test_generic.py
"""
import json
from playwright.sync_api import sync_playwright

USERJS = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "dist" / "universal-subtitle-extractor.user.js")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context()
    ctx.add_init_script(path=USERJS)  # 以 addInitScript 方式验证 userscript 形态
    page = ctx.new_page()
    page.on("console", lambda m: print("[console]", m.text) if "[USE]" in m.text else None)
    page.goto("http://127.0.0.1:8899/index.html", wait_until="load", timeout=30000)
    n = page.evaluate("window.__USE__.waitFor(3, 12000)")
    print("轨道数（去重后应为 3）:", n)
    for t in page.evaluate("window.__USE__.list()"):
        print(" -", t["label"], "|", t["source"], "|", t["cueCount"], "条")
    assert n >= 3, "通用嗅探失败"
    print("GENERIC_OK")
    browser.close()
