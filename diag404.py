# -*- coding: utf-8 -*-
"""诊断 404 console error 来源（临时）。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("response", lambda r: print("RSP", r.status, r.url) if r.status != 200 else None)
    pg.goto("http://127.0.0.1:5173", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(4000)
    urls = pg.evaluate(
        'performance.getEntriesByType("resource").map(e => e.name + " dur=" + Math.round(e.duration)).filter(n => n.toLowerCase().includes("favicon"))'
    )
    print("PERF-FAVICON", urls)
    # 主动请求 favicon
    st = pg.evaluate("fetch('/favicon.ico', {method: 'GET'}).then(r => r.status).catch(e => 'ERR:' + e)")
    print("FETCH-FAVICON", st)
    b.close()
