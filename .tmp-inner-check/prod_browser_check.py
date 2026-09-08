# -*- coding: utf-8 -*-
"""生产环境浏览器级验证：加载 http://118.24.185.45/，确认 HeroKnowledgeScene chunk 被请求、
canvas 渲染、非 fallback（fallback 是 SVG hero-graph-fallback 而非 canvas），并截图 2 帧。"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check"
URL = "http://118.24.185.45/"

requested = []
errors = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--enable-webgl", "--ignore-gpu-blocklist", "--use-angle=swiftshader",
                  "--enable-unsafe-swiftshader", "--window-size=1600,900"],
        )
        ctx = browser.new_context(viewport={"width": 1600, "height": 900},
                                  reduced_motion="no-preference")
        page = ctx.new_page()
        page.on("request", lambda req: requested.append(req.url)
                if "assets" in req.url else None)
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}")
                if m.type in ("error",) else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(6000)
        canvas = page.locator("canvas").count()
        fallback = page.locator(".hero-graph-fallback, .hero-graph-fallback svg").count()
        chunk = [u for u in requested if "HeroKnowledgeScene" in u]
        print("canvas count:", canvas)
        print("fallback count:", fallback)
        print("HeroKnowledgeScene chunk requested:", chunk)
        print("console errors:", json.dumps(errors[:10], ensure_ascii=False))
        page.screenshot(path=os.path.join(BASE, "prod_check_1.png"))
        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(BASE, "prod_check_2.png"))
        browser.close()
    print("PROD CHECK DONE")


if __name__ == "__main__":
    main()
