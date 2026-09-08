# -*- coding: utf-8 -*-
"""run C section only with extra debugging."""
import sys

sys.path.insert(0, r"D:\python_workspace\neo4j_muti_agents\t7_accept")
import accept_dev as ad  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    browser = ad.launch_edge(p)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("localStorage.setItem('app_locale', 'en-US');")
    page = ad.new_page(ctx)
    ad.attach_console(page, "C")

    # C1
    page.goto(ad.BASE_FE + "/login")
    page.wait_for_selector(".login-form", timeout=30000)
    body = page.locator("body").inner_text()
    ad.check("C1 登录页英文文案", "Sign in" in body and "Enter workspace" in body and "Register" in body)

    # C2
    page.goto(ad.BASE_FE + "/register")
    page.wait_for_selector(".register-form", timeout=30000)
    rbody = page.locator("body").inner_text()
    ad.check("C2 注册页英文渲染", "Register" in rbody and "Back to sign in" in rbody)

    # C3 + C4
    ad.ui_login(page, ad.ADMIN_USER, ad.ADMIN_PW, "C")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.locator(".user-dropdown").click()
    page.wait_for_selector(".el-dropdown-menu__item", timeout=10000)
    menu_txt = page.locator(".el-dropdown-menu__item").all_inner_texts()
    ad.check("C3 英文菜单", any("Change password" in t for t in menu_txt), str(menu_txt))
    for i in range(len(menu_txt)):
        if "Change password" in menu_txt[i]:
            page.locator(".el-dropdown-menu__item").nth(i).click()
            break
    page.wait_for_url("**/app/account?tab=security**", timeout=15000)
    page.wait_for_selector(".security-form", timeout=15000)
    page.wait_for_timeout(1500)
    print("URL:", page.url)
    print("lang:", page.evaluate("() => document.documentElement.lang"))
    sec_txt = page.locator("body").inner_text()
    print("SEC_TXT_SNIPPET:", sec_txt[:500].replace("\n", " | "))
    ad.check("C4 改密安全页英文", "Current password" in sec_txt and "Captcha" in sec_txt)
    browser.close()

print("RESULTS:", ad.RESULTS)
