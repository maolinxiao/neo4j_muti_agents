# -*- coding: utf-8 -*-
"""t5 体质辨识界面优化 — Playwright 验收脚本（临时，不提交版本库）。"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp-constitution-t5")
os.makedirs(SHOT_DIR, exist_ok=True)

TOKEN = open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens", "fe-constitution.tok"),
    encoding="utf-8",
).read().strip()

console_errors = []
page_errors = []


def shot(page, name):
    page.screenshot(path=os.path.join(SHOT_DIR, f"{name}.png"), full_page=True)
    print(f"[shot] {name}")


def check_no_hscroll(page, name):
    width = page.evaluate("document.documentElement.scrollWidth")
    vw = page.evaluate("window.innerWidth")
    ok = width <= vw + 2
    print(f"[hscroll:{name}] scrollWidth={width} innerWidth={vw} -> {'OK' if ok else 'OVERFLOW'}")
    return ok


def radio_by_text(page, text):
    return page.locator(".el-radio-button", has_text=text)


def click_option_value(page, value):
    rows = page.locator(".option-row")
    count = rows.count()
    for i in range(count):
        row = rows.nth(i)
        v = row.locator(".option-value").inner_text().strip()
        if v == str(value):
            row.click()
            return True
    return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(f"{msg.type}: {msg.text}")
                if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 注入登录态
        page.goto(BASE_URL + "/login")
        page.evaluate(
            "([t, u]) => { localStorage.setItem('ys_auth_token', t); localStorage.setItem('ys_auth_user', u); }",
            [TOKEN, json.dumps({"username": "admin"})],
        )

        # 1) 中文浅色：进入体质辨识
        page.goto(BASE_URL + "/app/constitution")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".constitution-panel", timeout=30000)
        page.wait_for_selector(".question-card", timeout=30000)
        page.wait_for_timeout(800)
        print("[1] constitution page loaded")
        print("    hero stats:", page.locator(".hero-stats .stat-item strong").all_inner_texts())
        print("    result section visible:", page.locator(".result-section").count() > 0)
        print("    score bars:", page.locator(".result-section .score-bar-row").count())
        check_no_hscroll(page, "zh-light-home")
        shot(page, "01-zh-light-home")

        # 2) 手动选择量表：卡片网格
        radio_by_text(page, "手动选择体质").click()
        page.wait_for_selector(".type-grid", timeout=10000)
        cards = page.locator(".type-card")
        print("[2] manual mode cards:", cards.count())
        cards.filter(has_text="气虚质").click()
        active = page.locator(".type-card.active .type-name").inner_text().strip()
        print("    active card:", active)
        assert active == "气虚质", "type card selection failed"
        shot(page, "02-zh-light-manual")

        # 3) 选择后进入对应问卷（筛选）
        page.locator("button", has_text="进入该体质量表").click()
        page.wait_for_selector(".filter-chip", timeout=10000)
        print("[3] filter chip:", page.locator(".filter-chip").inner_text().strip())
        dots = page.locator(".question-dot")
        print("    filtered questions:", dots.count())
        assert dots.count() == 3, f"expected 3 filtered questions, got {dots.count()}"
        # 答 1 题看进度
        click_option_value(page, 3)
        page.wait_for_timeout(300)
        print("    progress after 1:", page.locator(".progress-count").inner_text().strip(),
              page.locator(".progress-percent").inner_text().strip())
        shot(page, "03-zh-light-filtered")

        # 4) 清除筛选回到全部题目
        page.locator(".filter-clear").click()
        page.wait_for_timeout(300)
        dots = page.locator(".question-dot")
        print("[4] after clear filter, questions:", dots.count())
        assert dots.count() == 30, f"expected 30 questions, got {dots.count()}"

        # 5) 逐题作答全部 30 题
        answered = set()
        total = dots.count()
        for i in range(total):
            dot = dots.nth(i)
            if "answered" in (dot.get_attribute("class") or ""):
                answered.add(i)
                continue
            dot.click()
            page.wait_for_timeout(80)
            click_option_value(page, 3)
            page.wait_for_timeout(60)
        # 兜底：剩余未答的（若有）直接点下一题前进
        print("[5] answered via loop:", len(answered), "of", total)
        # 检查进度与未答提示
        prog = page.locator(".progress-count").inner_text().strip()
        pct = page.locator(".progress-percent").inner_text().strip()
        print("    progress:", prog, pct)
        # 手动补答漏网之鱼
        for _ in range(total):
            if "answered" not in (page.locator(".question-dot.active").get_attribute("class") or ""):
                click_option_value(page, 3)
                page.wait_for_timeout(50)
            next_btn = page.locator("button", has_text="下一题")
            if next_btn.is_disabled():
                break
            next_btn.click()
            page.wait_for_timeout(60)
        prog = page.locator(".progress-count").inner_text().strip()
        pct = page.locator(".progress-percent").inner_text().strip()
        print("    progress after fill:", prog, pct)
        print("    completion note:", page.locator(".completion-note").inner_text().strip()[:60])
        shot(page, "04-zh-light-complete")

        # 6) 提交测评 → 结果区
        page.locator("button", has_text="保存测评结果").click()
        page.wait_for_timeout(3000)
        print("[6] result score bars after submit:", page.locator(".result-section .score-bar-row").count())
        print("    diet cards:", page.locator(".diet-card").count())
        shot(page, "05-zh-light-result")

        # 7) 历史测评时间线
        radio_by_text(page, "历史记录").click()
        page.wait_for_selector(".history-timeline", timeout=10000)
        hcards = page.locator(".history-card")
        print("[7] history cards:", hcards.count())
        hcards.first.click()
        page.wait_for_timeout(400)
        print("    expanded score rows:", hcards.first.locator(".score-bar-row").count())
        shot(page, "06-zh-light-history")

        # 8) 英文 + 深色
        page.evaluate(
            "() => { localStorage.setItem('app_locale', 'en-US'); document.documentElement.classList.add('dark'); }"
        )
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".constitution-panel", timeout=30000)
        page.wait_for_timeout(800)
        print("[8] en-dark hero:", page.locator(".hero-copy h3").inner_text().strip())
        radio_by_text(page, "Pick type").click()
        page.wait_for_selector(".type-grid", timeout=10000)
        print("    en manual cards:", page.locator(".type-card").count())
        check_no_hscroll(page, "en-dark-manual")
        shot(page, "07-en-dark-manual")
        radio_by_text(page, "Scale assessment").click()
        page.wait_for_selector(".question-card", timeout=10000)
        print("    en assessment progress:", page.locator(".progress-count").inner_text().strip())
        check_no_hscroll(page, "en-dark-assessment")
        shot(page, "08-en-dark-assessment")

        # 9) 移动端（英文深色，375 宽）
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(600)
        check_no_hscroll(page, "mobile-en-dark")
        shot(page, "09-mobile-en-dark")

        # 10) 移动端中文浅色
        page.evaluate(
            "() => { localStorage.setItem('app_locale', 'zh-CN'); document.documentElement.classList.remove('dark'); }"
        )
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".constitution-panel", timeout=30000)
        page.wait_for_timeout(600)
        check_no_hscroll(page, "mobile-zh-light")
        shot(page, "10-mobile-zh-light")

        browser.close()

    print("\n=== console warnings/errors ===")
    for line in console_errors:
        print(" ", line[:200])
    print("=== page errors ===")
    for line in page_errors:
        print(" ", line[:300])
    if page_errors:
        print("RESULT: PAGE ERRORS PRESENT")
        sys.exit(1)
    # 过滤 element-plus 常规 dev 提示后判断
    real = [e for e in console_errors if not re.search(r"Download the Vue Devtools|devtools", e)]
    if real:
        print("RESULT: console errors present (see above)")
        sys.exit(2)
    print("RESULT: OK")


if __name__ == "__main__":
    main()
