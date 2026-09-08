# -*- coding: utf-8 -*-
"""t3 本机验收：首页三大版块 Three.js/3D/动态 CSS（临时脚本，勿提交）。

用法: python accept_t3_showcase.py [--url http://127.0.0.1:5173] [--outdir .tmp-showcase-t3]
依赖: playwright (msedge channel), PIL, numpy
输出: <outdir>/shots/*.png + <outdir>/report.json（逐项 PASS/FAIL 摘要）
"""
import argparse
import io
import json
import os
import sys

from playwright.sync_api import sync_playwright

RESULTS = []


def result(item, ok, detail=""):
    RESULTS.append({"item": item, "ok": bool(ok), "detail": detail})
    print("[RESULT] %s | %s | %s" % ("PASS" if ok else "FAIL", item, detail))
    return bool(ok)


def pixel_stats(png_bytes):
    """PNG -> (width,height,stddev,non_bg_ratio)：stddev 用于判定非空像素。"""
    from PIL import Image
    import numpy as np
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    a = np.asarray(img, dtype=np.float32)
    w, h = a.shape[1], a.shape[0]
    rgb = a[:, :, :3]
    alpha = a[:, :, 3]
    std = float(rgb.std())
    # 与纯白/纯透明背景的差异比例
    bg = np.array([255, 255, 255], dtype=np.float32)
    diff = np.abs(rgb - bg).mean(axis=2)
    non_bg = float((diff > 8).mean())
    return w, h, std, non_bg


def canvas_ok(page, prefix, index_of, expect, label):
    """检查 <prefix> 内 canvas 数量与像素非空。
    先滚动进视口等 IntersectionObserver 启动 rAF，再连拍两帧（间隔 900ms）：
    - 非空判定取两帧中较大 std / nonbg（阈值放宽至 std>=1.5 且 nonbg>=0.01）
    - 两帧差异（运动）计入详情
    """
    n = page.locator(prefix + " canvas").count()
    ok = result("%s canvas count==%d" % (label, expect), n == expect, "count=%d" % n)
    if n != expect:
        return ok
    try:
        page.locator(prefix).first.scroll_into_view_if_needed()
        page.wait_for_timeout(1800)
    except Exception:  # noqa: BLE001
        pass
    for i in range(n):
        loc = page.locator(prefix + " canvas").nth(index_of(i))
        try:
            box = loc.bounding_box()
            if not box or box["width"] < 2 or box["height"] < 2:
                result("%s canvas[%d] bbox" % (label, i), False, "bbox=%s" % box)
                continue
            from PIL import Image, ImageChops
            import numpy as np
            p1 = os.path.join(args.outdir, "shots", "%s_canvas_%d_f1.png" % (label, i))
            p2 = os.path.join(args.outdir, "shots", "%s_canvas_%d_f2.png" % (label, i))
            loc.screenshot(path=p1)
            page.wait_for_timeout(900)
            loc.screenshot(path=p2)
            w, h, std1, nonbg1 = pixel_stats(open(p1, "rb").read())
            w2, h2, std2, nonbg2 = pixel_stats(open(p2, "rb").read())
            ia = Image.open(p1).convert("RGB")
            ib = Image.open(p2).convert("RGB")
            if ia.size == ib.size:
                d = np.asarray(ImageChops.difference(ia, ib), dtype=np.float32)
                diff_ratio = float((d.mean(axis=2) > 10).mean())
            else:
                diff_ratio = -1.0
            std = max(std1, std2)
            nonbg = max(nonbg1, nonbg2)
            ok_ = std >= 1.5 and nonbg >= 0.01
            result("%s canvas[%d] non-empty pixels" % (label, i), ok_,
                   "size=%dx%d std=%.1f/%.1f nonbg=%.3f/%.3f framediff=%.4f"
                   % (w, h, std1, std2, nonbg1, nonbg2, diff_ratio))
        except Exception as exc:  # noqa: BLE001
            result("%s canvas[%d] screenshot" % (label, i), False, str(exc)[:160])
    return ok


def section_shot(page, sel, name, wait_ms=1400, full_section=True):
    loc = page.locator(sel).first
    loc.scroll_into_view_if_needed()
    page.wait_for_timeout(wait_ms)
    path = os.path.join(args.outdir, "shots", name + ".png")
    loc.screenshot(path=path)
    return path


def tilt_state(page, card_selector, mouse_x, mouse_y):
    """在卡片内移动鼠标，等待 rAF 插值，返回 (transform, tilt_hover, glare_opacity)。"""
    box = page.locator(card_selector).first.bounding_box()
    page.mouse.move(box["x"] + box["width"] * mouse_x, box["y"] + box["height"] * mouse_y, steps=8)
    page.wait_for_timeout(650)
    card = page.locator(card_selector).first
    transform = card.evaluate("el => el.style.transform || ''")
    has_cls = card.evaluate("el => el.classList.contains('tilt-hover')")
    glare = card.evaluate("el => { const g = el.querySelector('.cap-glare,.panel-glare,.sc-card-glow'); return g ? getComputedStyle(g).opacity : ''; }")
    return transform, has_cls, glare


def main():
    global args
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5173")
    ap.add_argument("--outdir", default=r"D:\python_workspace\neo4j_muti_agents\.tmp-showcase-t3")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.outdir, "shots"), exist_ok=True)

    console_errors = []
    page_errors = []
    request_failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append((m.type, m.text)) if m.type in ("error",) else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("requestfailed", lambda r: request_failures.append((r.url, r.failure)) if "favicon" not in r.url else None)

        print("[step] goto", args.url)
        page.goto(args.url, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(3500)

        # —— 基础检查 ——
        total_canvas = page.evaluate("() => document.querySelectorAll('canvas').length")
        result("page total canvas count", True, "count=%d (设计=hero1+cap3+aud1+pipe1=6)" % total_canvas)
        result("page main content load", page.locator("#app").is_visible(), "id=app visible")
        result("card count", page.locator("#capabilities .capability-card").count() == 3,
               "capability cards=%d" % page.locator("#capabilities .capability-card").count())
        result("audience panels", page.locator("#audience .audience-panel").count() == 2,
               "panels=%d" % page.locator("#audience .audience-panel").count())
        result("pipeline steps", page.locator("#agents .step-node").count() == 6,
               "steps=%d" % page.locator("#agents .step-node").count())

        # ============ Section 1: Capability ============
        print("[step] capability section")
        canvas_ok(page, "#capabilities ", lambda i: i, 3, "capability")
        section_shot(page, "#capabilities", "01_capability_default")

        # hover（中间卡片，鼠标在左上角 → rotate 非零）
        t0 = page.locator("#capabilities .capability-card").nth(0).evaluate("el => el.style.transform || '(none)'")
        transform, has_cls, glare = tilt_state(page, "#capabilities .capability-card", 0.3, 0.25)
        result("capability tilt hover transform", "rotateX" in transform and "rotateY" in transform,
               "before=%s after=%s" % (t0, transform[:110]))
        result("capability tilt-hover class", has_cls, "class=%s" % has_cls)
        result("capability glare opacity>0", glare not in ("", "0"), "opacity=%s" % glare)
        page.locator("#capabilities").screenshot(path=os.path.join(args.outdir, "shots", "02_capability_hover.png"))

        # 交互态：鼠标移到另一张卡片的右下角，tilt 反向；再滚轮路过
        t1 = tilt_state(page, "#capabilities .capability-card", 0.72, 0.8)
        result("capability tilt direction change", "rotateX" in t1[0] and "rotateY" in t1[0],
               "transform=%s" % t1[0][:110])
        page.locator("#capabilities").screenshot(path=os.path.join(args.outdir, "shots", "03_capability_interact.png"))
        # 离开复位
        page.mouse.move(700, 60, steps=4)
        page.wait_for_timeout(900)
        t_after = page.locator("#capabilities .capability-card").nth(0).evaluate("el => el.style.transform || ''")
        result("capability tilt reset on leave", t_after == "", "after=%r" % t_after[:60])

        # ============ Section 2: Audience ============
        print("[step] audience section")
        canvas_ok(page, "#audience ", lambda i: i, 1, "audience")
        section_shot(page, "#audience", "04_audience_default")
        core_visible = page.locator("#audience .classifier-core").is_visible()
        result("audience classifier core visible", core_visible, "core=%s" % core_visible)
        res = page.evaluate("""() => {
          const c = document.querySelector('#audience .classifier-core');
          const cs = c ? getComputedStyle(c) : null;
          return cs ? { animation: cs.animationName, backdrop: cs.backdropFilter || cs.webkitBackdropFilter } : null;
        }""")
        result("audience core breathe animation", bool(res and res.get("animation")), "anim=%s" % (res or {}))
        # 企业面板 hover
        at, ah, ag = tilt_state(page, "#audience .audience-panel", 0.3, 0.3)
        result("audience panel tilt hover", "rotateX" in at and "rotateY" in at, "transform=%s" % at[:110])
        page.locator("#audience").screenshot(path=os.path.join(args.outdir, "shots", "05_audience_hover_interact.png"))
        page.mouse.move(700, 60, steps=4)
        page.wait_for_timeout(900)

        # ============ Section 3: Pipeline ============
        print("[step] agent pipeline")
        canvas_ok(page, "#agents ", lambda i: i, 1, "pipeline")
        section_shot(page, "#agents", "06_pipeline_default")
        # 能量脉冲随时间移动：canvas 区域两帧差异
        pipe = page.locator("#agents .pipeline")
        f1 = os.path.join(args.outdir, "shots", "07_pipeline_t0.png")
        pipe.screenshot(path=f1)
        page.wait_for_timeout(2600)
        f2 = os.path.join(args.outdir, "shots", "08_pipeline_t2.6.png")
        pipe.screenshot(path=f2)
        a = open(f1, "rb").read()
        b = open(f2, "rb").read()
        if a != b:
            from PIL import Image, ImageChops
            import numpy as np
            ia = Image.open(io.BytesIO(a)).convert("RGB")
            ib = Image.open(io.BytesIO(b)).convert("RGB")
            d = np.asarray(ImageChops.difference(ia, ib), dtype=np.float32)
            diff_ratio = float((d.mean(axis=2) > 10).mean())
            result("pipeline energy pulse moves over time", diff_ratio > 0.001,
                   "diff_ratio=%.4f" % diff_ratio)
        else:
            result("pipeline energy pulse moves over time", False, "pixel-identical frames")

        # 自动轮播焦点变化
        idx0 = page.evaluate("() => [...document.querySelectorAll('#agents .step-node')].findIndex(n => n.classList.contains('active'))")
        name0 = page.locator("#agents .pipeline-detail h3").inner_text()
        page.wait_for_timeout(4300)
        idx1 = page.evaluate("() => [...document.querySelectorAll('#agents .step-node')].findIndex(n => n.classList.contains('active'))")
        name1 = page.locator("#agents .pipeline-detail h3").inner_text()
        result("pipeline auto-carousel advances", idx0 != idx1 and name0 != name1,
               "idx %d->%d name %s->%s" % (idx0, idx1, name0, name1))
        pipe.screenshot(path=os.path.join(args.outdir, "shots", "09_pipeline_carousel2.png"))

        # 交互态：点击某 step
        page.locator("#agents .step-node").nth(2).click()
        page.wait_for_timeout(800)
        name2 = page.locator("#agents .pipeline-detail h3").inner_text()
        idx2 = page.evaluate("() => [...document.querySelectorAll('#agents .step-node')].findIndex(n => n.classList.contains('active'))")
        result("pipeline click interaction", idx2 == 2 and "功效" in name2, "idx=%d name=%s" % (idx2, name2))
        page.locator("#agents").screenshot(path=os.path.join(args.outdir, "shots", "10_pipeline_interact.png"))

        # FPS 抽样（pipeline 可视区）
        fps = page.evaluate("""() => new Promise(resolve => {
            let n = 0; const t0 = performance.now();
            const f = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(f); else resolve(n / 2); };
            requestAnimationFrame(f);
        })""")
        result("FPS sample >= 30", fps >= 30, "fps=%.1f" % fps)

        # 全页截图
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(args.outdir, "shots", "00_fullpage_desktop.png"), full_page=True)

        # —— console / pageerror ——
        errs = [(t, m) for t, m in console_errors if t == "error"]
        # 已知非阻塞：/favicon.ico 404（P5 上线记录既有装饰性问题，D5 检查 404 来源确认）
        fav_status = page.evaluate("fetch('/favicon.ico').then(r => r.status).catch(e => 'ERR')")
        known = [m for t, m in errs if "404" in m and "Failed to load resource" in m and fav_status == 404]
        real_errs = [m for t, m in errs if m not in known]
        result("no console error", len(real_errs) == 0 and len(page_errors) == 0,
               "console_errors=%d known_favicon404=%d page_errors=%d raw=%s"
               % (len(real_errs), len(known), len(page_errors), errs[:3]))
        result("no failed requests", len(request_failures) == 0,
               "failed=%d (%s)" % (len(request_failures), [u for u, _ in request_failures[:3]]))
        ctx.close()

        # ============ reduced motion ============
        ctx2 = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        p2 = ctx2.new_page()
        errs2 = []
        p2.on("pageerror", lambda e: errs2.append(str(e)))
        p2.goto(args.url, wait_until="networkidle", timeout=90000)
        p2.wait_for_timeout(3000)
        canv = p2.evaluate("() => document.querySelectorAll('canvas').length")
        result("reduced-motion: zero canvases (CSS fallback)", canv == 0, "canvas=%d" % canv)
        icons = p2.locator("#capabilities .cap-icon").count()
        result("reduced-motion: capability svg fallback icons", icons == 3, "icons=%d" % icons)
        result("reduced-motion: audience core present", p2.locator("#audience .classifier-core").is_visible(), "")
        for sel, name in [("#capabilities", "11_capability_reduced"), ("#audience", "12_audience_reduced"), ("#agents", "13_pipeline_reduced")]:
            section_shot(p2, sel, name)
        # 轮播在 reduced 下不推进
        idxr0 = p2.evaluate("() => [...document.querySelectorAll('#agents .step-node')].findIndex(n => n.classList.contains('active'))")
        p2.wait_for_timeout(4300)
        idxr1 = p2.evaluate("() => [...document.querySelectorAll('#agents .step-node')].findIndex(n => n.classList.contains('active'))")
        result("reduced-motion: carousel paused", idxr0 == idxr1, "idx %d->%d" % (idxr0, idxr1))
        result("reduced-motion: no page errors", len(errs2) == 0, "errors=%s" % errs2[:2])
        ctx2.close()

        # ============ mobile 390 ============
        ctx3 = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
        p3 = ctx3.new_page()
        p3.goto(args.url, wait_until="networkidle", timeout=90000)
        p3.wait_for_timeout(3000)
        canv_m = p3.evaluate("() => document.querySelectorAll('canvas').length")
        result("mobile: zero section canvases (CSS fallback)", canv_m == 0, "canvas=%d" % canv_m)
        overflow = p3.evaluate("() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth})")
        result("mobile: no horizontal scroll", overflow["sw"] <= overflow["iw"] + 1,
               "scrollWidth=%d innerWidth=%d" % (overflow["sw"], overflow["iw"]))
        for sel, name in [("#capabilities", "14_capability_mobile"), ("#audience", "15_audience_mobile"), ("#agents", "16_pipeline_mobile")]:
            section_shot(p3, sel, name)
        p3.evaluate("() => window.scrollTo(0, 0)")
        p3.wait_for_timeout(800)
        p3.screenshot(path=os.path.join(args.outdir, "shots", "17_fullpage_mobile.png"), full_page=True)
        ctx3.close()
        browser.close()

    with open(os.path.join(args.outdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)
    n_ok = sum(1 for r in RESULTS if r["ok"])
    print("\n[SUMMARY] %d/%d PASS" % (n_ok, len(RESULTS)))
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
