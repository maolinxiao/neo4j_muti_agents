# -*- coding: utf-8 -*-
"""probe2: 新建会话点击后的路由与会话选择行为。"""
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, r"D:\python_workspace\neo4j_muti_agents\t7_accept")
from accept_dev import ui_login, ADMIN_USER, ADMIN_PW, BASE_FE  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(15000)
    requests = []
    page.on("request", lambda r: requests.append(f"{r.method} {r.url.split('localhost:5173')[-1]}") if "api/" in r.url else None)
    ui_login(page, ADMIN_USER, ADMIN_PW, "probe2")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.goto(BASE_FE + "/app/chat")
    page.wait_for_selector(".input-area textarea", timeout=20000)
    page.wait_for_timeout(2000)
    print("URL after load:", page.url)
    active = page.locator(".session-item.active .session-title").inner_text() if page.locator(".session-item.active").count() else "(none)"
    print("active session:", active)
    requests.clear()
    page.locator(".chat-header .el-button", has_text="新建会话").click()
    page.wait_for_timeout(2500)
    print("URL after new-session click:", page.url)
    active = page.locator(".session-item.active .session-title").inner_text() if page.locator(".session-item.active").count() else "(none)"
    print("active session after click:", active)
    print("requests during click:", requests)
    browser.close()
