# -*- coding: utf-8 -*-
"""生产浏览器级核验（临时）：Edge headless 打开公网首页，检查 canvas/console/最新 JS。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []
    pg.on("console", lambda m: errs.append((m.type, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(("pageerror", str(e))))
    pg.goto("http://118.24.185.45/", wait_until="networkidle", timeout=120000)
    pg.wait_for_timeout(5000)
    canv = pg.evaluate("document.querySelectorAll('canvas').length")
    cards = pg.evaluate("document.querySelectorAll('#capabilities .capability-card').length")
    steps = pg.evaluate("document.querySelectorAll('#agents .step-node').length")
    hero = pg.evaluate("document.querySelector('.hero-knowledge-scene') !== null")
    tg = pg.evaluate("""() => getComputedStyle(document.querySelector('.showcase-page') || document.body).display""")
    print("CANVASES", canv, "CARDS", cards, "STEPS", steps, "HERO_SCENE", hero, "DISPLAY", tg)
    real = [m for t, m in errs if "favicon" not in m.lower() and "Failed to load resource" not in m]
    print("CONSOLE_ERRORS", real)
    print("RAW", errs[:5])
    b.close()
