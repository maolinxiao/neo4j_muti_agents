"""临时验收脚本：图形验证码模板匹配识别 + 登录接口回归。
用法: python login_check.py <base_url> <username> <password> <font|auto>
font: 'auto' 走服务端同款字体查找顺序；或显式 ttf 路径（如 DejaVuSans.ttf）。
"""
import base64
import io
import sys
import time

import requests
from PIL import Image, ImageDraw, ImageFont

CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
SLOT_X0 = 12
SLOT_STEP = 24
CAPTCHA_LEN = 4


def load_font(explicit=None, size=28):
    if explicit:
        return ImageFont.truetype(explicit, size)
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
    base = sys.argv[1].rstrip("/")
    username = sys.argv[2]
    password = sys.argv[3]
    font_arg = sys.argv[4] if len(sys.argv) > 4 else "auto"
    font = load_font(None if font_arg == "auto" else font_arg)

    s = requests.Session()
    for attempt in range(1, 4):
        r = s.get(f"{base}/api/auth/captcha", timeout=15)
        if r.status_code != 200:
            print(f"CAPTCHA FAIL http {r.status_code}: {r.text[:200]}")
            sys.exit(1)
        cap = r.json()
        img = Image.open(io.BytesIO(base64.b64decode(cap["image_base64"]))).convert("RGB")
        text = solve(img, font)
        print(f"[attempt {attempt}] captcha solved: {text}")
        r = s.post(
            f"{base}/api/auth/login",
            json={"username": username, "password": password,
                  "captcha_id": cap["captcha_id"], "captcha_text": text},
            timeout=20,
        )
        if r.status_code == 200:
            break
        print(f"[attempt {attempt}] login {r.status_code}: {r.text[:300]}")
        time.sleep(1)
    else:
        print("LOGIN FAIL after retries")
        sys.exit(1)

    data = r.json()
    token = data["access_token"]
    print(f"LOGIN OK user={data['user']['username']} role={data['user']['role']}")
    r = s.get(f"{base}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    print(f"ME {r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        sys.exit(1)
    r = s.post(f"{base}/api/auth/logout", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    print(f"LOGOUT {r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        sys.exit(1)
    print("ALL OK")


if __name__ == "__main__":
    main()
