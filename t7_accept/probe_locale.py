# -*- coding: utf-8 -*-
"""probe3: add_init_script locale 是否生效。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("() => localStorage.setItem('app_locale', 'en-US')")
    page = ctx.new_page()
    page.goto("http://localhost:5173/login")
    page.wait_for_selector(".login-form", timeout=30000)
    page.wait_for_timeout(1500)
    print("lang attr:", page.evaluate("() => document.documentElement.lang"))
    print("storage:", page.evaluate("() => localStorage.getItem('app_locale')"))
    print("h2:", page.locator(".login-card h2").inner_text() if page.locator(".login-card h2").count() else "(no .login-card h2)")
    print("all h2:", page.locator("h2").all_inner_texts())
    print("button:", page.locator(".login-button").inner_text())
    browser.close()
