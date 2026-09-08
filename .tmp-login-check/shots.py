"""临时验收脚本：Playwright 截图（首页聚光灯轮播 + 登录页玻璃拟态 + 控制台错误采集）。"""
import sys
import time

from playwright.sync_api import sync_playwright

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else r"D:\python_workspace\neo4j_muti_agents\.tmp-login-check\shots"
BASE = "http://127.0.0.1:5173"


def main():
    console_errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)  # 等场景渲染启动（intro zoom-in 进行中）
        # 前 12s 每秒一张，覆盖 intro 特写 hold 窗口；随后每 2s 一张至 64s，覆盖完整轮播周期
        shots = []
        t = 0
        while t < 64:
            fname = f"{OUT_DIR}\\home_{t:03d}s.png"
            page.screenshot(path=fname)
            shots.append(fname)
            wait = 1 if t < 12 else 2
            t += wait
            page.wait_for_timeout(wait * 1000)
        # 登录页玻璃拟态
        page.goto(BASE + "/login", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT_DIR}\\login_full.png", full_page=True)
        page.screenshot(path=f"{OUT_DIR}\\login_viewport.png")
        # 回到首页抓一次 full_page 布局
        page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        page.screenshot(path=f"{OUT_DIR}\\home_fullpage.png", full_page=True)
        browser.close()
    print(f"shots: {len(shots)}")
    for s in shots:
        print(s)
    print("console errors:", len(console_errors))
    for e in console_errors[:30]:
        print("  ERR:", e[:200])


if __name__ == "__main__":
    main()
