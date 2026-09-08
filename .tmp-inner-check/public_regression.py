# -*- coding: utf-8 -*-
"""T2 公网回归：/ 200 + 新 bundle、/login 200、/api/health 200、登录冒烟（captcha→login→me→logout）。
凭据从服务器 .env 读取，不打印密码。结果写 .tmp-inner-check/public_regression.txt。
"""
import base64
import io
import re
import sys

import paramiko
import requests
from PIL import Image, ImageDraw, ImageFont

BASE = "http://118.24.185.45"
HOST = "118.24.185.45"
SSH_PASS = "mmfh2025KS686"
EXPECT_REFS = ["index-DhdqM3mh.js", "index-CAw3ZOu8.css",
               "HeroKnowledgeScene-x0ezEfm_.js", "HeroKnowledgeScene-DVgML9Jm.css",
               "showcase-3d-CjTivXqx.js"]
OUT = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\public_regression.txt"
lines = []


def log(s):
    lines.append(s)
    print(s, flush=True)


def get_admin_creds():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username="root", password=SSH_PASS,
                timeout=30, banner_timeout=30, auth_timeout=30)
    cmd = ("grep -E '^DEFAULT_ADMIN_USERNAME=|^DEFAULT_ADMIN_PASSWORD=' "
           "/www/wwwroot/neo4j-agents/backend/.env | head -2 | cut -d= -f2-")
    _, stdout, _ = cli.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip().splitlines()
    cli.close()
    if len(out) != 2:
        raise RuntimeError("admin creds not found: " + repr(out))
    return out[0].strip(), out[1].strip()


CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
SLOT_X0, SLOT_STEP, CAPTCHA_LEN = 12, 24, 4


def load_font(size=28):
    for name in ("arial.ttf", "DejaVuSans.ttf", "msyh.ttc", "simhei.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def dark_pixels(img, thresh=95):
    px = img.load()
    pts = set()
    for y in range(img.height):
        for x in range(img.width):
            p = px[x, y]
            if p[0] <= thresh and p[1] <= thresh and p[2] <= thresh:
                pts.add((x, y))
    return pts


def render_dark(font, char):
    img = Image.new("RGB", (40, 46), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((0, 0), char, font=font, fill=(0, 0, 0))
    return dark_pixels(img)


def solve(img, font):
    W = img.width
    out = ""
    for i in range(CAPTCHA_LEN):
        x0 = SLOT_X0 + i * ((W - 2 * SLOT_X0) // max(1, CAPTCHA_LEN))
        region = img.crop((x0 - 1, 0, x0 + 26, img.height))
        rp = dark_pixels(region)
        best, best_score = "?", -1
        for c in CHARSET:
            tp = render_dark(font, c)
            for yoff in range(-4, 11):
                shifted = {(x, y + yoff) for x, y in tp}
                score = len(rp & shifted)
                if score > best_score:
                    best_score, best = score, c
        out += best
    return out


def main():
    s = requests.Session()

    # 1) 首页
    r = s.get(BASE + "/", timeout=20)
    log(f"GET / -> {r.status_code} content-type={r.headers.get('content-type')}")
    html = r.text
    refs = sorted(set(re.findall(r'(?:src|href)="([^"]+)"', html)))
    log(f"index.html 引用: {refs}")
    ok_all = True
    for ref in EXPECT_REFS:
        hit = any(ref in x for x in refs)
        ok_all &= hit
        log(f"  期望引用 {ref}: {'PASS' if hit else 'FAIL'}")
    log(f"新 bundle 生效: {'PASS' if r.status_code == 200 and ok_all else 'FAIL'}")

    # 2) 新资源 200
    for x in refs:
        if x.startswith("/assets/") or x.endswith(".js") or x.endswith(".css"):
            r2 = requests.get(BASE + x, timeout=20)
            log(f"GET {x} -> {r2.status_code} ({r2.headers.get('content-type', '')[:30]})")

    # 3) /login
    r = s.get(BASE + "/login", timeout=20)
    log(f"GET /login -> {r.status_code}")

    # 4) /api/health
    r = s.get(BASE + "/api/health", timeout=30)
    body = r.text[:300]
    log(f"GET /api/health -> {r.status_code} {body}")

    # 5) 登录冒烟
    username, password = get_admin_creds()
    log(f"admin username: {username}（密码不回显）")
    font = load_font()
    token = None
    for attempt in range(1, 4):
        r = s.get(BASE + "/api/auth/captcha", timeout=15)
        if r.status_code != 200:
            log(f"captcha FAIL {r.status_code}: {r.text[:120]}")
            sys.exit(1)
        cap = r.json()
        img = Image.open(io.BytesIO(base64.b64decode(cap["image_base64"]))).convert("RGB")
        text = solve(img, font)
        log(f"[attempt {attempt}] captcha={text}")
        r = s.post(BASE + "/api/auth/login",
                   json={"username": username, "password": password,
                         "captcha_id": cap["captcha_id"], "captcha_text": text},
                   timeout=20)
        if r.status_code == 200:
            break
        log(f"[attempt {attempt}] login {r.status_code}: {r.text[:200]}")
    else:
        log("LOGIN FAIL")
        sys.exit(1)
    data = r.json()
    token = data["access_token"]
    log(f"LOGIN OK user={data['user']['username']} role={data['user']['role']}")
    r = s.get(BASE + "/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    log(f"ME -> {r.status_code}")
    r = s.post(BASE + "/api/auth/logout", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    log(f"LOGOUT -> {r.status_code}")
    log("REGRESSION ALL OK" if all(
        x in " ".join(lines) and "FAIL" not in x for x in ["GET / -> 200", "GET /login -> 200", "GET /api/health -> 200", "LOGIN OK", "LOGOUT -> 200"]
    ) else "REGRESSION HAS ISSUES")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
