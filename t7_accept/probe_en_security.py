# -*- coding: utf-8 -*-
"""probe4: EN 语境下 /app/account?tab=security 的文案。"""
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, r"D:\python_workspace\neo4j_muti_agents\t7_accept")
from accept_dev import ui_login, ADMIN_USER, ADMIN_PW, BASE_FE  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("localStorage.setItem('app_locale', 'en-US');")
    page = ctx.new_page()
    page.set_default_timeout(15000)
    ui_login(page, ADMIN_USER, ADMIN_PW, "probe4")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.goto(BASE_FE + "/app/account?tab=security")
    page.wait_for_selector(".security-form", timeout=15000)
    page.wait_for_timeout(1500)
    print("URL:", page.url)
    print("lang:", page.evaluate("() => document.documentElement.lang"))
    print("form html:", page.locator(".security-form").inner_text()[:600])
    print("tabs:", page.locator(".el-tabs__item").all_inner_texts())
    browser.close()
