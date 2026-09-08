# -*- coding: utf-8 -*-
"""t7 第二轮账号与界面优化 — 本机 dev(5173) Playwright(Edge) 验收。

覆盖：
A 中文浅色全流程（登录/改密跳转+验证码/偏好卡片/聊天/历史/研发/体质手动+标准量表/个人中心/管理后台/登出）
B 新账号隔离（A 建会话 → 登出 → B 登录 → 聊天列表不含 A 会话）
C 英文浅色抽查（登录/注册/主菜单/改密/聊天/管理后台）
D 中文深色抽查（登录/聊天/体质，暗色像素检查）
E 英文深色抽查（登录/个人中心）
"""
import base64
import io
import json
import os
import re
import sys
import time

import requests
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

BASE_FE = "http://localhost:5173"
BASE_API = "http://127.0.0.1:8000/api"
ROOT = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.join(ROOT, "shots")
os.makedirs(SHOT_DIR, exist_ok=True)

ADMIN_USER = "admin"
ADMIN_PW = "admin123456"
B_USER = "t7b_" + str(int(time.time()))[-6:]
B_PW = "T7b_Abc1234"
ADMIN_TOKEN_FILE = os.path.join(ROOT, "admin_token.txt")

# ---------- captcha 求解（模板匹配，同 _solve_captcha_local_t5.py） ----------
FONT_PATH = r"C:\WINDOWS\fonts\arial.ttf"
CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
W, H = 120, 40


def mask_of(img):
    px = img.load()
    return [[1 if min(px[x, y][0], px[x, y][1], px[x, y][2]) < 95 else 0 for x in range(W)] for y in range(H)]


def render_char(ch, x, y, font):
    img = Image.new("RGB", (W, H), (245, 247, 250))
    d = ImageDraw.Draw(img)
    d.text((x, y), ch, font=font, fill=(30, 30, 30))
    return mask_of(img)


def solve_mask(mask):
    font = ImageFont.truetype(FONT_PATH, 28)
    out = []
    for i in range(4):
        x0 = 12 + i * 24
        best = (0.0, "?")
        for ch in CHARSET:
            for y in range(3, 14):
                tpl = render_char(ch, x0, y, font)
                inter = union = 0
                for yy in range(H):
                    for xx in range(x0, min(x0 + 30, W)):
                        va = tpl[yy][xx]
                        vb = mask[yy][xx]
                        if va and vb:
                            inter += 1
                            union += 1
                        elif va or vb:
                            union += 1
                score = inter / union if union else 0.0
                if score > best[0]:
                    best = (score, ch)
        out.append((best[1], round(best[0], 3)))
    return out


def solve_png_bytes(png_bytes):
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return solve_mask(mask_of(img))


# ---------- API 辅助 ----------
def api_login(username, password):
    for _ in range(6):
        r = requests.get(f"{BASE_API}/auth/captcha", timeout=10)
        data = r.json()
        text = "".join(c for c, _ in solve_png_bytes(base64.b64decode(data["image_base64"])))
        login = requests.post(
            f"{BASE_API}/auth/login",
            json={"username": username, "password": password,
                  "captcha_id": data["captcha_id"], "captcha_text": text},
            timeout=15,
        )
        if login.status_code == 200:
            return login.json()["access_token"]
    raise RuntimeError(f"api_login failed for {username}")


def api_register(username, password):
    r = requests.get(f"{BASE_API}/auth/captcha", timeout=10)
    data = r.json()
    text = "".join(c for c, _ in solve_png_bytes(base64.b64decode(data["image_base64"])))
    reg = requests.post(
        f"{BASE_API}/auth/register",
        json={"username": username, "password": password,
              "captcha_id": data["captcha_id"], "captcha_text": text},
        timeout=15,
    )
    print(f"[api register] {reg.status_code} {reg.text[:120]}")
    reg.raise_for_status()
    return reg.json()["user_id"]


# ---------- 结果与像素工具 ----------
RESULTS = []


def check(name, ok, note=""):
    RESULTS.append({"name": name, "pass": bool(ok), "note": note})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" :: {note}" if note else ""))


def near_white_ratio(img_path):
    img = Image.open(img_path).convert("RGB")
    px = img.load()
    w, h = img.size
    total = w * h
    nw = sum(1 for y in range(0, h, 2) for x in range(0, w, 2)
             if min(px[x, y][0], px[x, y][1], px[x, y][2]) > 245)
    return nw / ((w // 2 + (1 if w % 2 else 0)) * (h // 2 + (1 if h % 2 else 0)))


def body_bg_luma(page):
    col = page.evaluate(
        "() => { const c = getComputedStyle(document.body).backgroundColor;"
        " const m = c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);"
        " return m ? 0.299*+m[1] + 0.587*+m[2] + 0.114*+m[3] : 255; }")
    return col


# ---------- 浏览器启动 ----------
def launch_edge(p):
    try:
        return p.chromium.launch(headless=True, channel="msedge")
    except Exception as exc:  # Edge 不可用时回退 bundled chromium
        print(f"[warn] msedge 不可用，回退 chromium: {exc}")
        return p.chromium.launch(headless=True)


def new_page(context):
    page = context.new_page()
    page.set_default_timeout(15000)
    return page


def attach_console(page, tag):
    def on_console(msg):
        if msg.type in ("error", "warning"):
            CONSOLE_LOGS.append(f"[{tag}] {msg.type}: {msg.text} @ {msg.location.get('url', '') if msg.location else ''}")
    def on_pageerror(err):
        CONSOLE_LOGS.append(f"[{tag}] pageerror: {err}")
    page.on("console", on_console)
    page.on("pageerror", on_pageerror)


CONSOLE_LOGS = []


def shot(page, name):
    path = os.path.join(SHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"[shot] {name}")


def ui_login(page, username, password, tag=""):
    page.goto(BASE_FE + "/login")
    page.wait_for_selector(".login-form", timeout=30000)
    page.wait_for_selector(".captcha-img", timeout=15000)
    page.wait_for_timeout(300)
    src = page.locator(".captcha-img").get_attribute("src")
    b64 = src.split("base64,", 1)[1]
    res = solve_png_bytes(base64.b64decode(b64))
    text = "".join(c for c, _ in res)
    print(f"[{tag} captcha] {res} -> {text}")
    page.locator(".login-form input[placeholder='admin']").fill(username)
    page.locator(".login-form input[type='password']").fill(password)
    page.locator(".captcha-row input").fill(text)
    page.locator(".login-button").click()
    try:
        page.wait_for_url("**/app/**", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(800)
    return page.url


def logout_ui(page):
    page.locator(".user-dropdown").click()
    page.wait_for_selector(".el-dropdown-menu__item", timeout=10000)
    items = page.locator(".el-dropdown-menu__item")
    for i in range(items.count()):
        if "退出" in items.nth(i).inner_text() or "Sign out" in items.nth(i).inner_text():
            items.nth(i).click()
            break
    page.wait_for_url("**/login**", timeout=15000)
    page.wait_for_timeout(800)


# ---------- 前置：注册并启用 B 用户 ----------
def setup_users():
    admin_tok = api_login(ADMIN_USER, ADMIN_PW)
    with open(ADMIN_TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(admin_tok)
    r = requests.get(f"{BASE_API}/admin/users", headers={"Authorization": f"Bearer {admin_tok}"},
                     params={"page": 1, "page_size": 200}, timeout=15)
    users = r.json().get("items") or []
    # 复用既有 t7b_* 用户（注册限流时避免 429）
    existing = next((u for u in users if u["username"].startswith("t7b_") and u["is_active"]), None)
    if existing:
        global B_USER
        B_USER = existing["username"]
        print(f"[setup] 复用既有 B 用户 {B_USER} id={existing['id']}")
        return admin_tok, existing["id"]
    uid = api_register(B_USER, B_PW)
    r = requests.put(f"{BASE_API}/admin/users/{uid}",
                     headers={"Authorization": f"Bearer {admin_tok}"},
                     json={"is_active": True}, timeout=15)
    print(f"[setup] 启用 B: {r.status_code} {r.text[:120]}")
    r.raise_for_status()
    return admin_tok, uid


# ============================================================
def section_a(page):
    """A 中文浅色全流程"""
    print("\n===== A 中文浅色 =====")
    page.goto(BASE_FE + "/login")
    page.wait_for_selector(".login-form", timeout=30000)
    check("A1 登录页(zh)渲染", page.locator(".captcha-img").count() == 1 and "登录" in page.locator("body").inner_text())
    shot(page, "A1-login-zh-light")

    ui_login(page, ADMIN_USER, ADMIN_PW, "A")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    check("A2 管理员 UI 登录进入主界面", page.url.startswith(BASE_FE + "/app"))

    # 右上角菜单：个人中心/修改密码/退出登录
    page.locator(".user-dropdown").click()
    page.wait_for_selector(".el-dropdown-menu__item", timeout=10000)
    menu_texts = page.locator(".el-dropdown-menu__item").all_inner_texts()
    check("A3 下拉含个人中心/修改密码/退出登录",
          any("个人中心" in t for t in menu_texts) and any("修改密码" in t for t in menu_texts)
          and any("退出登录" in t for t in menu_texts), str(menu_texts))
    # 点修改密码 → 跳转 /app/account?tab=security
    for i in range(len(menu_texts)):
        if "修改密码" in menu_texts[i]:
            page.locator(".el-dropdown-menu__item").nth(i).click()
            break
    page.wait_for_url("**/app/account?tab=security**", timeout=15000)
    check("A4 修改密码跳转个人中心安全页", "tab=security" in page.url)
    page.wait_for_selector(".security-form", timeout=15000)
    page.wait_for_selector(".captcha-img", timeout=15000)
    check("A5 改密表单含验证码图片", page.locator(".security-form .captcha-img").count() == 1)
    shot(page, "A5-account-security-zh")

    # 错误验证码 → 提示 + 自动刷新
    img_before = page.locator(".security-form .captcha-img").get_attribute("src")
    page.locator(".security-form input[type='password']").nth(0).fill(ADMIN_PW)
    page.locator(".security-form input[type='password']").nth(1).fill("NewPass_999")
    page.locator(".security-form input[type='password']").nth(2).fill("NewPass_999")
    page.locator(".security-form .captcha-row input").fill("ZZZZ")
    page.locator(".security-form .el-button--primary").click()
    try:
        page.wait_for_selector(".el-message", timeout=10000)
        msg_text = page.locator(".el-message").last.inner_text()
    except Exception:
        msg_text = ""
    page.wait_for_timeout(1200)
    img_after = page.locator(".security-form .captcha-img").get_attribute("src")
    captcha_cleared = page.locator(".security-form .captcha-row input").input_value() == ""
    check("A6 错误验证码提示+自动刷新",
          "验证码" in msg_text and img_before != img_after and captcha_cleared,
          f"msg={msg_text[:60]!r} img_changed={img_before != img_after} cleared={captcha_cleared}")

    # 正确验证码 + 错误旧密码 → 旧密码错误语义（不改密码）
    src = page.locator(".security-form .captcha-img").get_attribute("src")
    text = "".join(c for c, _ in solve_png_bytes(base64.b64decode(src.split("base64,", 1)[1])))
    page.locator(".security-form input[type='password']").nth(0).fill("wrong-old-pw")
    page.locator(".security-form .captcha-row input").fill(text)
    page.locator(".security-form .el-button--primary").click()
    try:
        page.wait_for_selector(".el-message", timeout=10000)
        msg2 = page.locator(".el-message").last.inner_text()
    except Exception:
        msg2 = ""
    check("A7 旧密码错误 400 语义提示", ("原密码" in msg2 or "旧密码" in msg2 or "当前密码" in msg2), f"msg={msg2[:60]!r}")

    # 偏好设置卡片
    page.goto(BASE_FE + "/app/account?tab=preferences")
    page.wait_for_selector(".pref-theme-grid", timeout=15000)
    theme_cards = page.locator(".pref-theme-grid .pref-card").count()
    lang_cards = page.locator(".pref-lang-grid .pref-card").count()
    check("A8 偏好主题/语言卡片渲染", theme_cards >= 2 and lang_cards >= 2,
          f"theme={theme_cards} lang={lang_cards}")
    # 主题切换：点深色 → html.dark
    for i in range(theme_cards):
        if "深色" in page.locator(".pref-theme-grid .pref-card").nth(i).inner_text():
            page.locator(".pref-theme-grid .pref-card").nth(i).click()
            break
    page.wait_for_timeout(500)
    is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    check("A9 深色卡片切换生效(html.dark)", is_dark)
    shot(page, "A9-account-dark-zh")
    # 切回浅色
    for i in range(theme_cards):
        if "浅色" in page.locator(".pref-theme-grid .pref-card").nth(i).inner_text():
            page.locator(".pref-theme-grid .pref-card").nth(i).click()
            break
    page.wait_for_timeout(500)
    is_light = page.evaluate("() => !document.documentElement.classList.contains('dark')")
    check("A10 浅色卡片切回生效", is_light)
    # 语言切换：点 English → 菜单文案英文
    for i in range(lang_cards):
        if "English" in page.locator(".pref-lang-grid .pref-card").nth(i).inner_text():
            page.locator(".pref-lang-grid .pref-card").nth(i).click()
            break
    page.wait_for_timeout(500)
    lang = page.evaluate("() => document.documentElement.lang")
    check("A11 语言卡片切换英文生效", lang == "en-US", f"lang={lang}")
    shot(page, "A11-account-en")
    # 切回中文
    for i in range(lang_cards):
        if "中文" in page.locator(".pref-lang-grid .pref-card").nth(i).inner_text():
            page.locator(".pref-lang-grid .pref-card").nth(i).click()
            break
    page.wait_for_timeout(500)
    lang = page.evaluate("() => document.documentElement.lang")
    check("A12 语言卡片切回中文", lang == "zh-CN", f"lang={lang}")

    # 聊天：新建会话后发送「孕妇能不能吃人参？」
    page.goto(BASE_FE + "/app/chat")
    page.wait_for_selector(".input-area textarea", timeout=20000)
    # 等待自动选中会话完成（否则新建会话点击会被在途 auto-select 覆盖）
    try:
        page.wait_for_selector(".session-item.active", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    page.locator(".chat-header .el-button", has_text="新建会话").click()
    page.wait_for_function("() => !document.querySelector('.session-item.active')", timeout=10000)
    page.wait_for_timeout(800)
    page.locator(".input-area textarea").fill("孕妇能不能吃人参？")
    page.locator(".input-area").locator("button").last.click()
    try:
        page.wait_for_function(
            "() => [...document.querySelectorAll('.session-title')].some(e => e.textContent.includes('孕妇能不能吃人参'))",
            timeout=120000,
        )
        sid_title = True
    except Exception:
        sid_title = False
    try:
        page.wait_for_function("() => !document.querySelector('.streaming-cursor')", timeout=180000)
        stream_done = True
    except Exception:
        stream_done = False
    asst = page.locator(".msg-row.assistant-row").count()
    check("A13 聊天发送+会话标题生成+流式完成", sid_title and stream_done and asst >= 1,
          f"title={sid_title} stream_done={stream_done} assistant_msgs={asst}")
    shot(page, "A13-chat-zh-light")

    # 历史
    page.goto(BASE_FE + "/app/history")
    page.wait_for_selector(".history-container, .session-item, .el-table", timeout=20000)
    page.wait_for_timeout(800)
    body_txt = page.locator("body").inner_text()
    check("A14 历史页包含新会话", "孕妇能不能吃人参" in body_txt)
    shot(page, "A14-history-zh-light")

    # 研发
    page.goto(BASE_FE + "/app/rnd")
    page.wait_for_selector(".rnd-page", timeout=20000)
    page.wait_for_timeout(800)
    rnd_txt = page.locator("body").inner_text()
    has_input = page.locator("textarea").count() >= 1
    check("A15 研发页渲染(标题+输入)", ("研发" in rnd_txt) and has_input, f"textarea={has_input}")
    shot(page, "A15-rnd-zh-light")

    # 体质：手动选择量表
    page.goto(BASE_FE + "/app/constitution")
    page.wait_for_selector(".constitution-panel", timeout=30000)
    page.wait_for_selector(".mode-row .el-radio-button", timeout=20000)
    page.locator(".mode-row .el-radio-button", has_text="手动选择体质").click()
    page.wait_for_selector(".type-card", timeout=20000)
    n_types = page.locator(".type-card").count()
    check("A16 体质手动量表 9 类型卡片", n_types == 9, f"n={n_types}")
    # 选择气虚质 → 保存档案
    for i in range(n_types):
        if "气虚质" in page.locator(".type-card").nth(i).inner_text():
            page.locator(".type-card").nth(i).click()
            break
    page.wait_for_timeout(400)
    page.locator(".manual-actions .el-button--primary").first.click()  # 保存档案
    try:
        page.wait_for_selector(".el-message", timeout=10000)
        page.wait_for_timeout(1500)
    except Exception:
        pass
    result_txt = page.locator(".result-section").inner_text() if page.locator(".result-section").count() else ""
    check("A17 手动保存档案→结果卡更新", "气虚质" in result_txt, result_txt[:60])
    shot(page, "A17-constitution-manual-zh")

    # 标准量表测评（按类型过滤）
    page.locator(".manual-actions").locator("button", has_text="量表").first.click()
    page.wait_for_selector(".assessment-progress", timeout=15000)
    page.wait_for_selector(".question-card", timeout=15000)
    prog0 = page.locator(".progress-count").inner_text().strip()
    total_q = page.locator(".question-dot").count()
    check("A18 标准量表测评进入(过滤问卷)", int(prog0.split("/")[0].strip()) == 0 and total_q >= 1,
          f"progress={prog0} questions={total_q}")
    # 逐题作答（选项1 + 下一题）
    for _ in range(total_q + 2):
        page.locator(".option-row").first.click()
        page.wait_for_timeout(120)
        nxt = page.locator(".question-actions .el-button").nth(1)
        if nxt.is_enabled():
            nxt.click()
            page.wait_for_timeout(120)
        else:
            break
    page.wait_for_timeout(400)
    prog_end = page.locator(".progress-count").inner_text().strip()
    submit_btn = page.locator(".question-actions .el-button--success")
    ok_submit = submit_btn.is_enabled()
    check("A19 问卷进度到满(可提交)", ok_submit, f"progress={prog_end}")
    submit_btn.click()
    # 切到历史记录模式验证测评已入库
    page.wait_for_timeout(800)
    page.locator(".mode-row .el-radio-button", has_text="历史记录").click()
    try:
        page.wait_for_selector(".history-card", timeout=20000)
        hist_ok = True
    except Exception:
        hist_ok = False
    page.wait_for_timeout(800)
    check("A20 测评提交→结果卡+历史记录", page.locator(".result-section").count() >= 1 and hist_ok,
          f"history_cards={page.locator('.history-card').count()}")
    shot(page, "A20-constitution-assessment-zh")

    # 个人中心 资料/统计
    page.goto(BASE_FE + "/app/account?tab=profile")
    page.wait_for_selector(".account-view, .el-card", timeout=15000)
    page.wait_for_timeout(500)
    check("A21 个人中心资料页渲染", "资料" in page.locator("body").inner_text() or page.locator(".el-card").count() >= 1)
    page.goto(BASE_FE + "/app/account?tab=stats")
    page.wait_for_timeout(1200)
    check("A22 个人中心统计页渲染", "统计" in page.locator("body").inner_text())
    shot(page, "A22-account-stats-zh")

    # 管理后台
    for path, name in [("admin/overview", "总览"), ("admin/users", "用户"), ("admin/prompts", "提示词"), ("admin/logs", "日志")]:
        page.goto(BASE_FE + "/app/" + path)
        page.wait_for_timeout(1500)
        ok = name in page.locator("body").inner_text() or page.locator(".el-card, .el-table, .el-tabs").count() >= 1
        check(f"A23 管理后台 {name} 页渲染", ok)
        if name == "总览":
            shot(page, "A23-admin-overview-zh")

    # 登出
    logout_ui(page)
    token_cleared = page.evaluate("() => !localStorage.getItem('ys_auth_token')")
    check("A24 登出返回登录页+token 清除", page.url.endswith("/login") and token_cleared)


def section_b(page):
    """B 新账号隔离：B 聊天列表不含 A 的会话"""
    print("\n===== B 新账号隔离 =====")
    ui_login(page, B_USER, B_PW, "B")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    check("B1 B 用户 UI 登录成功", page.url.startswith(BASE_FE + "/app"))
    page.goto(BASE_FE + "/app/chat")
    page.wait_for_selector(".session-sidebar", timeout=20000)
    page.wait_for_timeout(2500)  # 等待会话列表拉取
    sidebar_txt = page.locator(".session-sidebar").inner_text()
    check("B2 B 聊天侧栏不含 A 的「孕妇能不能吃人参？」", "孕妇能不能吃人参" not in sidebar_txt,
          f"sidebar_len={len(sidebar_txt)}")
    shot(page, "B2-chat-userb-zh")
    page.goto(BASE_FE + "/app/history")
    page.wait_for_timeout(2500)
    hist_txt = page.locator("body").inner_text()
    check("B3 B 历史页不含 A 会话", "孕妇能不能吃人参" not in hist_txt)
    shot(page, "B3-history-userb-zh")
    # B 体质：新用户无结果卡，手动量表可用
    page.goto(BASE_FE + "/app/constitution")
    page.wait_for_selector(".mode-row .el-radio-button", timeout=30000)
    has_result = page.locator(".result-section").count() > 0
    page.locator(".mode-row .el-radio-button", has_text="手动选择体质").click()
    page.wait_for_selector(".type-card", timeout=20000)
    check("B4 B 体质页无残留档案结果卡(新账号)", (not has_result) and page.locator(".type-card").count() == 9)
    logout_ui(page)


def section_c(page):
    """C 英文浅色抽查"""
    print("\n===== C 英文浅色 =====")
    page.goto(BASE_FE + "/login")
    page.wait_for_selector(".login-form", timeout=30000)
    body = page.locator("body").inner_text()
    check("C1 登录页英文文案", "Sign in" in body and "Enter workspace" in body and "Register" in body)
    shot(page, "C1-login-en-light")

    page.goto(BASE_FE + "/register")
    page.wait_for_selector(".register-form", timeout=30000)
    rbody = page.locator("body").inner_text()
    check("C2 注册页英文渲染", "Register" in rbody and "Back to sign in" in rbody)
    shot(page, "C2-register-en-light")

    ui_login(page, ADMIN_USER, ADMIN_PW, "C")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.locator(".user-dropdown").click()
    page.wait_for_selector(".el-dropdown-menu__item", timeout=10000)
    menu_txt = page.locator(".el-dropdown-menu__item").all_inner_texts()
    check("C3 英文菜单(My Account/Change password/Sign out)",
          any("My Account" in t for t in menu_txt) and any("Change password" in t for t in menu_txt)
          and any("Sign out" in t for t in menu_txt), str(menu_txt))
    for i in range(len(menu_txt)):
        if "Change password" in menu_txt[i]:
            page.locator(".el-dropdown-menu__item").nth(i).click()
            break
    page.wait_for_url("**/app/account?tab=security**", timeout=15000)
    page.wait_for_selector(".security-form", timeout=15000)
    try:
        page.wait_for_selector("text=Current password", timeout=15000)
        page.wait_for_selector("text=Captcha", timeout=10000)
        en_ok = True
    except Exception:
        en_ok = False
    sec_txt = page.locator("body").inner_text()
    check("C4 改密安全页英文(Current password/Captcha)", en_ok and "Change password" in sec_txt)
    shot(page, "C4-account-security-en")

    page.goto(BASE_FE + "/app/chat")
    page.wait_for_selector(".input-area textarea", timeout=20000)
    ph = page.locator(".input-area textarea").get_attribute("placeholder")
    check("C5 聊天输入占位英文", "Ask a question" in (ph or ""), ph or "")
    shot(page, "C5-chat-en-light")

    page.goto(BASE_FE + "/app/admin/overview")
    page.wait_for_timeout(2000)
    abody = page.locator("body").inner_text()
    check("C6 管理后台总览英文抽查", "Overview" in abody or "Admin" in abody)
    shot(page, "C6-admin-overview-en")
    logout_ui(page)


def section_d(page):
    """D 中文深色抽查（含像素检查）"""
    print("\n===== D 中文深色 =====")
    page.goto(BASE_FE + "/login")
    page.wait_for_selector(".login-form", timeout=30000)
    page.wait_for_timeout(800)
    luma = body_bg_luma(page)
    shot(page, "D1-login-zh-dark")
    ratio = near_white_ratio(os.path.join(SHOT_DIR, "D1-login-zh-dark.png"))
    check("D1 深色登录页(背景暗+无大块亮斑)", luma < 128 and ratio < 0.20,
          f"body_luma={luma:.0f} near_white={ratio:.3f}")

    ui_login(page, ADMIN_USER, ADMIN_PW, "D")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.goto(BASE_FE + "/app/chat")
    page.wait_for_selector(".chat-container", timeout=20000)
    page.wait_for_timeout(1200)
    luma2 = body_bg_luma(page)
    shot(page, "D2-chat-zh-dark")
    ratio2 = near_white_ratio(os.path.join(SHOT_DIR, "D2-chat-zh-dark.png"))
    check("D2 深色聊天页(无刺眼浅色块)", luma2 < 128 and ratio2 < 0.12,
          f"body_luma={luma2:.0f} near_white={ratio2:.3f}")

    page.goto(BASE_FE + "/app/constitution")
    page.wait_for_selector(".constitution-panel", timeout=30000)
    page.wait_for_timeout(1200)
    luma3 = body_bg_luma(page)
    shot(page, "D3-constitution-zh-dark")
    ratio3 = near_white_ratio(os.path.join(SHOT_DIR, "D3-constitution-zh-dark.png"))
    check("D3 深色体质页(无刺眼浅色块)", luma3 < 128 and ratio3 < 0.15,
          f"body_luma={luma3:.0f} near_white={ratio3:.3f}")
    logout_ui(page)


def section_e(page):
    """E 英文深色抽查"""
    print("\n===== E 英文深色 =====")
    page.goto(BASE_FE + "/login")
    page.wait_for_selector(".login-form", timeout=30000)
    body = page.locator("body").inner_text()
    luma = body_bg_luma(page)
    check("E1 深色+英文登录页", "Sign in" in body and luma < 128, f"luma={luma:.0f}")
    shot(page, "E1-login-en-dark")

    ui_login(page, ADMIN_USER, ADMIN_PW, "E")
    page.wait_for_selector(".user-dropdown", timeout=20000)
    page.goto(BASE_FE + "/app/account?tab=preferences")
    page.wait_for_selector(".pref-theme-grid", timeout=15000)
    page.wait_for_timeout(800)
    body2 = page.locator("body").inner_text()
    luma2 = body_bg_luma(page)
    check("E2 深色+英文偏好设置页", "Preferences" in body2 and luma2 < 128, f"luma={luma2:.0f}")
    shot(page, "E2-account-preferences-en-dark")
    logout_ui(page)


def main():
    admin_tok, b_uid = setup_users()
    print(f"[setup] admin_token ok, B id={b_uid} user={B_USER}")

    with sync_playwright() as p:
        browser = launch_edge(p)

        # A/B 共用默认上下文（zh 浅色）
        ctx_a = browser.new_context(viewport={"width": 1440, "height": 900})
        page_a = new_page(ctx_a)
        attach_console(page_a, "A/B")
        section_a(page_a)
        section_b(page_a)
        ctx_a.close()

        # C 英文浅色
        ctx_c = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx_c.add_init_script("localStorage.setItem('app_locale', 'en-US');")
        page_c = new_page(ctx_c)
        attach_console(page_c, "C")
        section_c(page_c)
        ctx_c.close()

        # D 中文深色
        ctx_d = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx_d.add_init_script("localStorage.setItem('app_theme', 'dark');")
        page_d = new_page(ctx_d)
        attach_console(page_d, "D")
        section_d(page_d)
        ctx_d.close()

        # E 英文深色
        ctx_e = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx_e.add_init_script(
            "localStorage.setItem('app_locale', 'en-US'); localStorage.setItem('app_theme', 'dark');")
        page_e = new_page(ctx_e)
        attach_console(page_e, "E")
        section_e(page_e)
        ctx_e.close()

        browser.close()

    # 控制台错误汇总（过滤已知非阻塞项）
    blocked = []
    for log in CONSOLE_LOGS:
        low = log.lower()
        if "favicon" in low:
            continue
        # 负面用例触发的 change-password 400（预期）
        if "change-password" in low and ("400" in low or "bad request" in low):
            continue
        if "deprecation" in low or "three" in low:
            continue
        if "404" in low and ("failed to load resource" in low):
            # 仅 favicon 404 属预期；记录 URL 供人工复核
            blocked.append(log)
            continue
        blocked.append(log)
    check("Z1 全流程 console 无错误", not blocked, "; ".join(blocked[:6]) if blocked else "clean")

    passed = sum(1 for r in RESULTS if r["pass"])
    total = len(RESULTS)
    print(f"\n===== 汇总: {passed}/{total} PASS =====")
    with open(os.path.join(ROOT, "results_dev.json"), "w", encoding="utf-8") as fh:
        json.dump({"results": RESULTS, "console_logs": CONSOLE_LOGS, "b_user": B_USER},
                  fh, ensure_ascii=False, indent=2)
    sys.exit(0 if passed == total else 2)


if __name__ == "__main__":
    main()
