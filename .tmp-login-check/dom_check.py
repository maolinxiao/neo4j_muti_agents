"""临时验收脚本：DOM 级验收（首页 hero 文案可读/无重叠 + 登录页玻璃拟态结构）。"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = {}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # ---- 首页 hero 文案 DOM 检查 ----
        page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        hero = page.evaluate(
            """() => {
                const q = (s) => document.querySelector(s);
                const info = (el) => {
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    const cs = getComputedStyle(el);
                    return { tag: el.tagName, cls: el.className?.toString?.().slice(0,80),
                             text: (el.textContent||'').trim().slice(0,60),
                             x: r.x, y: r.y, w: r.width, h: r.height,
                             opacity: cs.opacity, visibility: cs.visibility,
                             display: cs.display, color: cs.color, fontSize: cs.fontSize };
                };
                const items = ['.hero-eyebrow', '.hero-title', '.hero-lead', '.hero-tags', '.hero-actions', '.hero-capability-rail'];
                const out = {};
                for (const s of items) out[s] = info(q(s));
                // 重叠检查：eyebrow/title/lead 两两 bounding box 相交率
                const sel = ['.hero-eyebrow', '.hero-title', '.hero-lead'];
                const boxes = sel.map(s => q(s)).filter(Boolean).map(el => {
                    const r = el.getBoundingClientRect();
                    return { s: sel[sel.indexOf('.' + el.className.split(' ')[0])] || el.className, x: r.x, y: r.y, w: r.width, h: r.height };
                });
                let overlaps = [];
                for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
                    const a = boxes[i], b = boxes[j];
                    const ix = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
                    const iy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
                    const inter = ix * iy;
                    const minArea = Math.min(a.w * a.h, b.w * b.h);
                    if (minArea > 0 && inter / minArea > 0.05) overlaps.push({ a: a.s, b: b.s, inter, minArea });
                }
                out.overlap = { boxes, overlaps };
                return out;
            }"""
        )
        OUT["hero"] = hero

        # ---- 登录页玻璃拟态 DOM 检查 ----
        page.goto(BASE + "/login", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        login = page.evaluate(
            """() => {
                const q = (s) => document.querySelector(s);
                const card = q('.login-card');
                const cs = card ? getComputedStyle(card) : null;
                const title = q('.brand-panel h1');
                const titleCs = title ? getComputedStyle(title) : null;
                const cardH2 = q('.card-header h2');
                const captchaImg = q('.captcha-img');
                const captchaRow = q('.captcha-row');
                const bg = q('.login-bg, .login-video-bg, video');
                const brand = q('.brand-panel');
                const brandCs = brand ? getComputedStyle(brand) : null;
                return {
                    cardFound: !!card,
                    cardBackdropFilter: cs ? cs.backdropFilter || cs.webkitBackdropFilter : null,
                    cardBackground: cs ? cs.background : null,
                    cardBackgroundColor: cs ? cs.backgroundColor : null,
                    cardBorderRadius: cs ? cs.borderRadius : null,
                    titleFound: !!title,
                    titleText: title ? (title.textContent || '').trim().slice(0, 40) : null,
                    titleBackgroundImage: titleCs ? titleCs.backgroundImage : null,
                    titleWebkitTextFill: titleCs ? titleCs.webkitTextFillColor : null,
                    cardH2Found: !!cardH2,
                    cardH2Text: cardH2 ? (cardH2.textContent || '').trim() : null,
                    brandPanelBackdropFilter: brandCs ? (brandCs.backdropFilter || brandCs.webkitBackdropFilter) : null,
                    captchaRowFound: !!captchaRow,
                    captchaImgFound: !!captchaImg,
                    captchaImgLoaded: captchaImg ? (captchaImg.complete && captchaImg.naturalWidth > 0) : false,
                    captchaImgSize: captchaImg ? [captchaImg.naturalWidth, captchaImg.naturalHeight] : null,
                    videoBgFound: !!bg,
                };
            }"""
        )
        OUT["login"] = login
        browser.close()

    print(json.dumps(OUT, ensure_ascii=False, indent=2))

    # 判定
    h = OUT["hero"]
    all_visible = all(
        v and float(v["opacity"]) > 0.5 and v["visibility"] == "visible" and v["display"] != "none"
        for v in [h.get(".hero-eyebrow"), h.get(".hero-title"), h.get(".hero-lead")]
    )
    hero_ok = all_visible and len(h["overlap"]["overlaps"]) == 0
    l = OUT["login"]
    glass = (
        l["cardFound"]
        and (("blur" in (l["cardBackdropFilter"] or "")))
        and l["titleFound"]
        and ("gradient" in (l["titleBackgroundImage"] or ""))
        and l["captchaRowFound"]
        and bool(l["captchaImgLoaded"])
    )
    print("DOM_HERO:", "PASS" if hero_ok else "FAIL")
    print("DOM_LOGIN_GLASS:", "PASS" if glass else "FAIL")
    if not hero_ok or not glass:
        sys.exit(1)


if __name__ == "__main__":
    main()
