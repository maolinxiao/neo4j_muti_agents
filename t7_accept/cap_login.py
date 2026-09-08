# -*- coding: utf-8 -*-
"""t7: 快速验证 captcha 求解 + admin 登录（本地 dev）。"""
import base64
import io
import sys

import requests
from PIL import Image, ImageDraw, ImageFont

BASE = "http://127.0.0.1:8000/api"
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


def solve_png(png_bytes):
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return solve_mask(mask_of(img))


def try_login(username, password, verbose=True):
    for attempt in range(5):
        r = requests.get(f"{BASE}/auth/captcha", timeout=10)
        data = r.json()
        res = solve_png(base64.b64decode(data["image_base64"]))
        text = "".join(c for c, _ in res)
        if verbose:
            print(f"[{username} attempt {attempt}] solved {res} -> {text}")
        login = requests.post(
            f"{BASE}/auth/login",
            json={"username": username, "password": password,
                  "captcha_id": data["captcha_id"], "captcha_text": text},
            timeout=15,
        )
        if login.status_code == 200:
            body = login.json()
            print(f"[{username}] LOGIN OK, token head: {body['access_token'][:12]}...")
            return body["access_token"]
        print(f"[{username}] fail {login.status_code}: {login.text[:160]}")
    return None


if __name__ == "__main__":
    tok = try_login("admin", "admin123456")
    sys.exit(0 if tok else 1)
