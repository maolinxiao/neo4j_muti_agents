# -*- coding: utf-8 -*-
"""特写内部展开重设计 — 本机 Playwright 连拍验收脚本。

- 用本机 Edge（channel='msedge'，headless 新模式，WebGL 走 SwiftShader 兜底）
- 打开 http://127.0.0.1:5173/ ，每 3s 一帧，共 32 帧（约 96s）
- 覆盖：开场（约 7.7s）+ 完整 8 节点特写轮播（8 × 10s = 80s）
- 截图存 .tmp-inner-check/shots/frame_XX.png；控制台错误存 console.log
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")
os.makedirs(SHOTS, exist_ok=True)

URL = "http://127.0.0.1:5173/"
INTERVAL_MS = 3000
FRAMES = 32

console_errors = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=[
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--disable-gpu-sandbox",
                "--force-color-profile=srgb",
                "--window-size=1920,1080",
            ],
        )
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(
                f"[{msg.type}] {msg.text}"
            )
            if msg.type in ("error", "warning")
            else None,
        )
        page.on(
            "pageerror",
            lambda exc: console_errors.append(f"[pageerror] {exc}"),
        )

        print("goto", URL, flush=True)
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("canvas", timeout=30000)
        # 等场景首帧渲染
        page.wait_for_timeout(4000)

        canvas_count = page.locator("canvas").count()
        print(f"canvas count: {canvas_count}", flush=True)

        t0 = time.time()
        for i in range(FRAMES):
            path = os.path.join(SHOTS, f"frame_{i:02d}.png")
            page.screenshot(path=path)
            elapsed = time.time() - t0
            print(
                f"[{i + 1}/{FRAMES}] {os.path.basename(path)}  t={elapsed:.1f}s",
                flush=True,
            )
            if i < FRAMES - 1:
                page.wait_for_timeout(INTERVAL_MS)

        # 页面尺寸/画布信息
        info = page.evaluate(
            """() => {
                const canvases = Array.from(document.querySelectorAll('canvas'));
                return canvases.map(c => ({
                    width: c.width, height: c.height,
                    cssW: c.clientWidth, cssH: c.clientHeight,
                }));
            }"""
        )
        print("canvas info:", json.dumps(info, ensure_ascii=False), flush=True)

        with open(os.path.join(BASE, "console.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(console_errors) if console_errors else "(no console errors)")
        print("console issues:", len(console_errors), flush=True)
        for line in console_errors[:40]:
            print("  ", line, flush=True)

        browser.close()

    print("DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
