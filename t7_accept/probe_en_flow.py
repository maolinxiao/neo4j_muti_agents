# -*- coding: utf-8 -*-
"""probe5: 复现 run8 C4 流程（EN 下拉点 Change password）。"""
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
    ui_login(page, ADMIN_USER, ADMIN_PW, "probe5")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.locator(".user-dropdown").click()
    page.wait_for_selector(".el-dropdown-menu__item", timeout=10000)
    items = page.locator(".el-dropdown-menu__item")
    menu_txt = items.all_inner_texts()
    print("menu:", menu_txt)
    for i in range(len(menu_txt)):
        if "Change password" in menu_txt[i]:
            items.nth(i).click()
            break
    try:
        page.wait_for_url("**/app/account?tab=security**", timeout=15000)
        print("URL ok:", page.url)
    except Exception as exc:
        print("URL timeout:", page.url, exc)
    page.wait_for_selector(".security-form", timeout=15000)
    page.wait_for_timeout(1200)
    print("active tab:", page.locator(".el-tabs__item.is-active").inner_text() if page.locator(".el-tabs__item.is-active").count() else "(none)")
    sec = page.locator("body").inner_text()
    print("has Current password:", "Current password" in sec)
    print("has Captcha:", "Captcha" in sec)
    print("form:", page.locator(".security-form").inner_text()[:300])
    browser.close()
