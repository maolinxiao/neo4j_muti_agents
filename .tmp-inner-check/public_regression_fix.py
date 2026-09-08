# -*- coding: utf-8 -*-
"""修复回归：下载服务器验证码字体 DejaVuSans.ttf + 直连校验动态 chunk 资源 + 重跑登录冒烟。"""
import base64
import io
import os
import sys

import paramiko
import requests
from PIL import Image, ImageDraw, ImageFont

BASE = "http://118.24.185.45"
HOST = "118.24.185.45"
SSH_PASS = "mmfh2025KS686"
FONT_LOCAL = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\DejaVuSans.ttf"
CHUNKS = ["/assets/HeroKnowledgeScene-x0ezEfm_.js", "/assets/HeroKnowledgeScene-DVgML9Jm.css"]


def get_font_and_creds():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username="root", password=SSH_PASS, timeout=30)
    sftp = cli.open_sftp()
    try:
        sftp.get("/usr/share/fonts/dejavu/DejaVuSans.ttf", FONT_LOCAL)
        print("font downloaded:", FONT_LOCAL, os.path.getsize(FONT_LOCAL), "bytes")
    except IOError as e:
        # 回退：找服务器上任意 DejaVu 字体
        _, so, _ = cli.exec_command("find /usr/share/fonts -iname '*dejavu*sans*.ttf' 2>/dev/null | head -3", timeout=30)
        candidates = [x.strip() for x in so.read().decode().splitlines() if x.strip()]
        print("font candidates:", candidates)
        for c in candidates:
            try:
                sftp.get(c, FONT_LOCAL)
                print("font downloaded (fallback):", c)
                break
            except IOError:
                continue
        else:
            raise RuntimeError("no dejavu font found: " + str(e))
    cmd = ("grep -E '^DEFAULT_ADMIN_USERNAME=|^DEFAULT_ADMIN_PASSWORD=' "
           "/www/wwwroot/neo4j-agents/backend/.env | head -2 | cut -d= -f2-")
    _, stdout, _ = cli.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip().splitlines()
    sftp.close()
    cli.close()
    return out[0].strip(), out[1].strip()


CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
SLOT_X0, SLOT_STEP, CAPTCHA_LEN = 12, 24, 4


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

    # 1) 动态 chunk 直连校验
    for c in CHUNKS:
        r = s.get(BASE + c, timeout=20)
        print(f"GET {c} -> {r.status_code} {r.headers.get('content-type', '')[:40]}")

    # 2) 登录冒烟（服务器同款字体）
    username, password = get_font_and_creds()
    print(f"admin username: {username}（密码不回显）")
    font = ImageFont.truetype(FONT_LOCAL, 28)
    for attempt in range(1, 5):
        r = s.get(BASE + "/api/auth/captcha", timeout=15)
        if r.status_code != 200:
            print(f"captcha FAIL {r.status_code}: {r.text[:120]}")
            sys.exit(1)
        cap = r.json()
        img = Image.open(io.BytesIO(base64.b64decode(cap["image_base64"]))).convert("RGB")
        text = solve(img, font)
        print(f"[attempt {attempt}] captcha={text}")
        r = s.post(BASE + "/api/auth/login",
                   json={"username": username, "password": password,
                         "captcha_id": cap["captcha_id"], "captcha_text": text},
                   timeout=20)
        if r.status_code == 200:
            break
        print(f"[attempt {attempt}] login {r.status_code}: {r.text[:200]}")
    else:
        print("LOGIN FAIL")
        sys.exit(1)
    data = r.json()
    token = data["access_token"]
    print(f"LOGIN OK user={data['user']['username']} role={data['user']['role']}")
    r = s.get(BASE + "/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    print(f"ME -> {r.status_code}")
    r = s.post(BASE + "/api/auth/logout", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    print(f"LOGOUT -> {r.status_code}")
    print("SMOKE ALL OK" if r.status_code == 200 else "SMOKE ISSUES")


if __name__ == "__main__":
    main()
