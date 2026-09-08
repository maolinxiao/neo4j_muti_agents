# -*- coding: utf-8 -*-
"""probe: 登录后进入 /app/chat，dump .chat-header HTML。"""
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, r"D:\python_workspace\neo4j_muti_agents\t7_accept")
from accept_dev import ui_login, ADMIN_USER, ADMIN_PW, BASE_FE  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(15000)
    ui_login(page, ADMIN_USER, ADMIN_PW, "probe")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.goto(BASE_FE + "/app/chat")
    page.wait_for_selector(".input-area textarea", timeout=20000)
    page.wait_for_timeout(1000)
    html = page.locator(".chat-header").inner_html()
    print("HEADER_HTML:", html[:1200])
    btns = page.locator(".chat-header button").count()
    print("buttons in header:", btns)
    for i in range(btns):
        print(i, repr(page.locator(".chat-header button").nth(i).inner_text()))
    browser.close()
