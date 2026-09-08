# -*- coding: utf-8 -*-
"""临时脚本：固定位置模板匹配求解验证码并登录，输出 token（不提交到版本库）。"""
import base64
import io
import os
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


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123456"
    for attempt in range(8):
        r = requests.get(f"{BASE}/auth/captcha", timeout=10)
        r.raise_for_status()
        data = r.json()
        png = base64.b64decode(data["image_base64"])
        res = solve_png(png)
        text = "".join(c for c, _ in res)
        print(f"[attempt {attempt}] solved: {res} -> {text}")
        login = requests.post(
            f"{BASE}/auth/login",
            json={"username": username, "password": password,
                  "captcha_id": data["captcha_id"], "captcha_text": text},
            timeout=15,
        )
        if login.status_code == 200:
            body = login.json()
            token = body.get("access_token") or body.get("token") or ""
            print("[login ok]")
            print(token)
            out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens")
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "fe-constitution.tok"), "w", encoding="utf-8") as fh:
                fh.write(token.strip())
            print("[token saved] tokens/fe-constitution.tok")
            return
        print(f"[login fail] {login.status_code} {login.text[:200]}")
    sys.exit(1)


if __name__ == "__main__":
    main()
