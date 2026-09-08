# -*- coding: utf-8 -*-
"""逐像素复刻渲染的验证码求解器（临时脚本）。

原理：服务器 render_base64 的绘制逻辑已知：
  x = 12 + index * ((120-24)//length)（length=4 时步长 24）
  y = 6 + random.randint(-2, 6)   → y ∈ [4, 12]
  font = ImageFont.truetype(字体候选, 28)；本机用从服务器取回的 DejaVuSans.ttf
  fill = (随机 20-90, ...)
用相同字体、相同尺寸、相同坐标逐字符渲染，与真实图像做暗像素 IoU 比对，
每个字符枚举 charset × y∈[4,12] 取最优，全程无位置偏移搜索。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_input", "DejaVuSans.ttf")
W, H = 120, 40


def load_mask(path):
    im = Image.open(path).convert("RGB")
    px = im.load()
    return [[1 if min(px[x, y]) < 95 else 0 for x in range(W)] for y in range(H)]


def render_chars(font, text_y_pairs):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for ch, x, y in text_y_pairs:
        d.text((x, y), ch, font=font, fill=(50, 50, 50))
    px = img.load()
    return [[1 if min(px[x, y]) < 95 else 0 for x in range(W)] for y in range(H)]


def iou_window(actual, render, x0, x1):
    inter = union = 0
    for y in range(H):
        for x in range(x0, x1):
            a = actual[y][x]
            r = render[y][x]
            if a and r:
                inter += 1
                union += 1
            elif a or r:
                union += 1
    return (inter / union) if union else 0.0


def solve(png, font_path=FONT, length=4):
    actual = load_mask(png)
    font = ImageFont.truetype(font_path, 28)
    result = []
    step = (W - 8) // length  # 与服务器一致（length=4 → 步长 28）
    pos = [8 + i * step for i in range(length)]
    # 服务器源码: x = 12 + index * ((120-24)//len)  → [12, 36, 60, 84]
    pos = [12 + i * ((W - 24) // length) for i in range(length)]
    for i, x in enumerate(pos):
        best = (0.0, "?", None)
        for ch in CHARSET:
            for y in range(4, 13):
                r = render_chars(font, [(ch, x, y)])
                score = iou_window(actual, r, max(0, x - 3), min(W, x + 27))
                if score > best[0]:
                    best = (score, ch, y)
        result.append((best[1], round(best[0], 3)))
    return result


if __name__ == "__main__":
    png = sys.argv[1]
    res = solve(png)
    print("[solution]", res)
    print("[text]", "".join(c for c, _ in res))
