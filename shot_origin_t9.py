# -*- coding: utf-8 -*-
"""截图 t9 run 最终方案 tab 的「原方依据」区块（滚动到该区块）。"""
import json
import os

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, ".tmp-rnd-t3", "shots")
with open(os.path.join(ROOT, ".tmp-rnd-t3", "run_result.json"), "r", encoding="utf-8") as f:
    d = json.load(f)
token = open(os.path.join(ROOT, ".tmp-rnd-t3", "token.txt"), encoding="utf-8").read().strip()
sid = d["session_id"]
rid = d.get("run_id") or d.get("id")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    ctx.add_init_script(
        "localStorage.setItem('ys_auth_token', %s);"
        "localStorage.setItem('ys_auth_user', JSON.stringify({username:'admin',role:'admin'}));" % json.dumps(token)
    )
    page = ctx.new_page()
    page.goto(f"http://118.24.185.45/app/rnd/{sid}?runId={rid}", wait_until="networkidle", timeout=60000)
    page.wait_for_selector(".step-card", timeout=60000)
    page.wait_for_timeout(2500)
    page.locator(".step-card", has_text="主控汇总 Agent").first.click()
    page.wait_for_timeout(2500)
    # 滚动到 原方依据 区块
    sec = page.locator(".tab-content .report-section", has_text="原方依据").first
    sec.scroll_into_view_if_needed()
    page.wait_for_timeout(800)
    page.screenshot(path=os.path.join(OUT, "t9_origin_formula_section.png"))
    txt = sec.text_content() or ""
    print("原方依据 section text:", txt[:400])
    browser.close()
print("saved t9_origin_formula_section.png")
