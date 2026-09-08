# -*- coding: utf-8 -*-
"""t7 第二轮：公网回归（118.24.185.45）。
1) 首页/登录/注册 200 + index.html 引用新 bundle
2) 新资源 200
3) /api/health 200
4) 登录冒烟：captcha OCR(DejaVuSans) → login admin(服务器 .env 凭据，不回显) → me/chat/rnd/constitution/admin 接口
5) 改密接口冒烟：错误验证码 400；正确验证码+错误旧密码 400（不真改生产密码）
6) 新账号历史隔离：注册测试账号 → 启用 → 登录 → chat/rnd 会话列表为空 → 停用测试账号
7) 生产浏览器级抽查：首页 + 登录页（Playwright Edge，console 零错误）
"""
import base64
import io
import json
import os
import re
import sys
import time
import urllib.request

import paramiko
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

BASE = "http://118.24.185.45"
ROOT = os.path.dirname(os.path.abspath(__file__))
FONT = r"D:\python_workspace\neo4j_muti_agents\captcha_input\DejaVuSans.ttf"
HOST = "118.24.185.45"
USER = "root"
PASSWORD = "mmfh2025KS686"
CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
W, H = 120, 40

RESULTS = []


def check(item, ok, detail=""):
    RESULTS.append({"item": item, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {item}" + (f" :: {detail}" if detail else ""))


def http_get(path, timeout=60, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def http_post(path, payload, token=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def http_put(path, payload, token=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"), method="PUT")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def http_delete(path, token=None, timeout=60):
    req = urllib.request.Request(BASE + path, method="DELETE")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def ssh_run(cmd, timeout=120):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    _, out, err = cli.exec_command(cmd, timeout=timeout)
    o = out.read().decode(errors="replace")
    e = err.read().decode(errors="replace")
    cli.close()
    return o, e


# ---------- captcha OCR ----------
def mask_of(img):
    px = img.load()
    return [[1 if min(px[x, y][0], px[x, y][1], px[x, y][2]) < 95 else 0 for x in range(W)] for y in range(H)]


def render_char(ch, x, y, font):
    img = Image.new("RGB", (W, H), (245, 247, 250))
    d = ImageDraw.Draw(img)
    d.text((x, y), ch, font=font, fill=(30, 30, 30))
    return mask_of(img)


def solve_png_bytes(png_bytes):
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    mask = mask_of(img)
    font = ImageFont.truetype(FONT, 28)
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


def fetch_captcha():
    st, body = http_get("/api/auth/captcha")
    if st != 200:
        return None, None, None, f"captcha http {st}"
    data = json.loads(body)
    res = solve_png_bytes(base64.b64decode(data["image_base64"]))
    text = "".join(c for c, _ in res)
    return data["captcha_id"], text, res, ""


def get_admin_creds():
    o, _ = ssh_run("grep -E '^DEFAULT_ADMIN_(USERNAME|PASSWORD)=' /www/wwwroot/neo4j-agents/backend/.env")
    username = password = None
    for line in o.splitlines():
        if line.startswith("DEFAULT_ADMIN_USERNAME="):
            username = line.split("=", 1)[1].strip()
        if line.startswith("DEFAULT_ADMIN_PASSWORD="):
            password = line.split("=", 1)[1].strip()
    return username, password


def login_as(username, password):
    for _ in range(6):
        cid, text, res, err = fetch_captcha()
        if err:
            continue
        st, body = http_post("/api/auth/login", {
            "username": username, "password": password,
            "captcha_id": cid, "captcha_text": text,
        })
        if st == 200:
            return json.loads(body)["access_token"], res
        if st == 429 or st == 401:
            print(f"  [login blocked] {st}: {body[:120]}")
            return None, res
        print(f"  [login retry] {st} {body[:100]}")
    return None, None


def main():
    # 1) 首页
    st, html = http_get("/")
    check("GET / 200", st == 200, f"status={st}")
    refs = sorted(set(re.findall(r'(?:src|href)="([^"]+)"', html)))
    check("index.html 引用新 bundle", any("index-BVbhVAst.js" in r for r in refs), str(refs))

    # 2) 新资源 200
    for rel in ["/assets/index-BVbhVAst.js", "/assets/index-BnTlgyQe.css",
                "/assets/HeroKnowledgeScene-lkNFM12D.js", "/assets/HeroKnowledgeScene-DVgML9Jm.css",
                "/assets/showcase-3d-BbLLm7wP.js", "/login-bg-still.png"]:
        st, _ = http_get(rel)
        check(f"GET {rel} 200", st == 200, f"status={st}")

    # 3) SPA 页面
    for path in ["/login", "/register"]:
        st, _ = http_get(path)
        check(f"GET {path} 200", st == 200, f"status={st}")

    # 4) health
    st, body = http_get("/api/health")
    ok_h = False
    detail = ""
    if st == 200:
        d = json.loads(body)
        ok_h = all(d.get(k) for k in ("postgres", "neo4j")) and d.get("llm_configured")
        detail = json.dumps(d, ensure_ascii=False)
    check("health 200 (postgres/neo4j/llm)", st == 200 and ok_h, f"status={st} {detail}")

    # 5) 登录冒烟 + 关键接口
    username, password = get_admin_creds()
    token, res = login_as(username, password)
    check("captcha OCR + admin 登录 200", token is not None, f"captcha={res}")
    if token:
        for path in ["/api/auth/me", "/api/chat/sessions", "/api/rnd/sessions",
                     "/api/constitution/types", "/api/admin/overview"]:
            st, _ = http_get(path, headers={"Authorization": f"Bearer {token}"})
            check(f"GET {path} 200", st == 200, f"status={st}")

        # 6) 改密接口冒烟（不真改密码）
        cid, text, _, _ = fetch_captcha()
        st, body = http_post("/api/auth/change-password", {
            "old_password": "x", "new_password": "Yy_123456", "confirm_password": "Yy_123456",
            "captcha_id": cid, "captcha_text": "ZZZZ",
        }, token=token)
        check("改密-错误验证码 400", st == 400, f"status={st} {body[:120]}")
        cid, text, res, _ = fetch_captcha()
        st, body = http_post("/api/auth/change-password", {
            "old_password": "wrong-old-pw-xyz", "new_password": "Yy_123456", "confirm_password": "Yy_123456",
            "captcha_id": cid, "captcha_text": text,
        }, token=token)
        check("改密-正确验证码+错误旧密码 400 语义", st == 400, f"status={st} {body[:120]}")

        # 7) 新账号历史隔离
        b_name = "t7verify_" + str(int(time.time()))[-6:]
        b_pw = "T7v_Abc1234"
        cid, text, _, _ = fetch_captcha()
        st, body = http_post("/api/auth/register", {
            "username": b_name, "password": b_pw,
            "captcha_id": cid, "captcha_text": text,
        })
        reg_ok = st == 200
        uid = ""
        if reg_ok:
            uid = json.loads(body).get("user_id", "")
        check("注册测试账号 200(待审核)", reg_ok, f"status={st} {body[:100]}")
        if uid:
            st, body = http_put(f"/api/admin/users/{uid}", {"is_active": True}, token=token)
            check("启用测试账号 200", st == 200, f"status={st} {body[:100]}")
            b_tok, _ = login_as(b_name, b_pw)
            check("测试账号登录 200", b_tok is not None)
            if b_tok:
                st, body = http_get("/api/chat/sessions", headers={"Authorization": f"Bearer {b_tok}"})
                try:
                    sess = json.loads(body)
                    isolated = st == 200 and isinstance(sess, list) and len(sess) == 0
                    check("新账号 chat 会话列表为空(无他人会话)", isolated, f"status={st} n={len(sess) if isinstance(sess, list) else '?'}")
                except Exception:
                    check("新账号 chat 会话列表为空(无他人会话)", False, f"status={st} {body[:100]}")
                st, body = http_get("/api/rnd/sessions", headers={"Authorization": f"Bearer {b_tok}"})
                try:
                    sess = json.loads(body)
                    isolated2 = st == 200 and isinstance(sess, list) and len(sess) == 0
                    check("新账号 rnd 会话列表为空", isolated2, f"status={st} n={len(sess) if isinstance(sess, list) else '?'}")
                except Exception:
                    check("新账号 rnd 会话列表为空", False, f"status={st} {body[:100]}")
                http_post("/api/auth/logout", {}, token=b_tok)
            # 停用测试账号（保留审计）
            st, _ = http_put(f"/api/admin/users/{uid}", {"is_active": False}, token=token)
            check("测试账号停用(清理) 200", st == 200, f"status={st}")
        http_post("/api/auth/logout", {}, token=token)

    # 8) 生产浏览器级抽查
    console_errs = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="msedge")
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.on("console", lambda m: console_errs.append(f"{m.type}: {m.text}")
                    if m.type == "error" else None)
            page.goto(BASE + "/", wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(3000)
            n_canvas = page.evaluate("() => document.querySelectorAll('canvas').length")
            ok_home = page.locator("#app").count() == 1 and n_canvas >= 1
            check("公网首页渲染(canvas 场景)", ok_home, f"canvas={n_canvas}")
            page.goto(BASE + "/login", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            check("公网登录页渲染(验证码图片)", page.locator(".captcha-img").count() == 1)
            page.screenshot(path=os.path.join(ROOT, "shots", "P1-prod-login.png"))
            page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
            page.screenshot(path=os.path.join(ROOT, "shots", "P2-prod-home.png"))
            browser.close()
        real_errs = [e for e in console_errs if "favicon" not in e.lower()]
        check("公网 console 无错误", not real_errs, "; ".join(real_errs[:5]))
    except Exception as exc:  # noqa: BLE001
        check("公网浏览器级抽查", False, f"exception: {exc}")

    n_ok = sum(1 for r in RESULTS if r["ok"])
    print(f"\n[SUMMARY] {n_ok}/{len(RESULTS)} PASS")
    with open(os.path.join(ROOT, "results_prod.json"), "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=2)
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
