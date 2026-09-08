# -*- coding: utf-8 -*-
"""获取服务器 PIL 字体 + 模板匹配识别验证码（临时脚本）。
用法: python solve_captcha.py <png> [--font F] [--charset-file path]
"""
import base64
import io
import json
import os
import sys

import paramiko
from PIL import Image, ImageDraw, ImageFont

CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"


def fetch_font():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686",
                timeout=30, banner_timeout=30, auth_timeout=30)
    _, out, _ = cli.exec_command(
        "/www/server/pyporject_evn/neo4j-agents-backend/bin/python -c \"from PIL import ImageFont; print(ImageFont.truetype('DejaVuSans.ttf', 28).path)\"",
        timeout=60)
    font_path = out.read().decode("utf-8", "replace").strip()
    print("[font path]", font_path)
    sftp = cli.open_sftp()
    local_font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_input", "DejaVuSans.ttf")
    os.makedirs(os.path.dirname(local_font), exist_ok=True)
    sftp.get(font_path, local_font)
    sftp.close()
    cli.close()
    print("[font saved]", local_font)
    return local_font


def char_mask(pixels, w, h):
    """min(r,g,b) < 95 → 字符像素"""
    return [[1 if min(p[0], p[1], p[2]) < 95 else 0 for p in row] for row in pixels]


def load_mask(path):
    im = Image.open(path).convert("RGB")
    px = im.load()
    w, h = im.size
    rows = [[px[xi, yi] for xi in range(w)] for yi in range(h)]
    return char_mask(rows, w, h)


def render_template(font, ch, size=28):
    img = Image.new("L", (60, 60), 0)
    d = ImageDraw.Draw(img)
    d.text((10, 10), ch, font=font, fill=255)
    bb = img.getbbox()
    if bb is None:
        return None
    return img.crop(bb)


def extract_char_boxes(mask, w, h, expected=4):
    """按列投影找字符片段。"""
    cols = [0] * w
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                cols[x] += 1
    # 找连续段
    segs = []
    in_seg = False
    for x in range(w):
        if cols[x] > 0 and not in_seg:
            start = x
            in_seg = True
        elif cols[x] == 0 and in_seg:
            segs.append((start, x))
            in_seg = False
    if in_seg:
        segs.append((start, w))
    segs = [(s, e) for s, e in segs if e - s >= 4]
    return segs


def crop_char(mask, w, h, x0, x1):
    # 找该段的 y 范围
    ys = [y for y in range(h) for x in range(x0, x1) if mask[y][x]]
    if not ys:
        return None
    y0, y1 = min(ys), max(ys)
    return [[mask[y][x] for x in range(x0, x1)] for y in range(y0, y1 + 1)]


def iou(mask_a, mask_b, off_x, off_y, bw, bh):
    """mask_a: (bh x bw) 裁剪, mask_b: 大掩码, off: b 中偏移"""
    inter = union = 0
    for y in range(bh):
        ya = y
        yb = y + off_y
        if yb < 0 or yb >= len(mask_b):
            union += sum(mask_a[y])
            continue
        for x in range(bw):
            xa = x
            xb = x + off_x
            va = mask_a[y][x]
            vb = mask_b[yb][xb] if 0 <= xb < len(mask_b[0]) else 0
            if va and vb:
                inter += 1
                union += 1
            elif va or vb:
                union += 1
    return (inter / union) if union else 0.0


def solve(png_path, font_path, length=4):
    mask = load_mask(png_path)
    h = len(mask)
    w = len(mask[0])
    font = ImageFont.truetype(font_path, 28)
    segs = extract_char_boxes(mask, w, h)
    print("[segments]", segs)
    if len(segs) != length:
        print("[warn] segments != length, merging?")
    # 逐段识别
    result = []
    for (x0, x1) in segs:
        cm = crop_char(mask, w, h, x0, x1)
        bh = len(cm)
        bw = len(cm[0])
        best = (0.0, "?")
        for ch in CHARSET:
            tpl = render_template(font, ch)
            if tpl is None:
                continue
            tm = [[1 if p > 127 else 0 for p in row] for row in _alpha_rows(tpl)]
        # 规范化：将模板 bbox 缩放至与裁剪同尺寸（允许 3 档缩放），做 IoU
        th, tw = len(tm), len(tm[0])
        if tw == 0 or th == 0:
            continue
        for scale in (1.0, 0.9, 1.1, 1.2, 0.8):
            nw = max(1, int(round(tw * scale)))
            nh = max(1, int(round(th * scale)))
            if nw > bw + 4 or nh > bh + 4:
                continue
            tpl_scaled = tpl.resize((nw, nh), Image.LANCZOS)
            tmx = [[1 if p > 127 else 0 for p in row] for row in _alpha_rows(tpl_scaled)]
            for off_x in range(0, max(1, bw - nw + 1) + 2):
                for off_y in range(0, max(1, bh - nh + 1) + 2):
                    inter = union = 0
                    for y in range(nh):
                        yb = y + off_y
                        if yb < 0 or yb >= bh:
                            union += sum(tmx[y])
                            continue
                        for x in range(nw):
                            xa = x + off_x
                            va = tmx[y][x]
                            vb = cm[yb][xa] if xa < bw else 0
                            if va and vb:
                                inter += 1
                                union += 1
                            elif va or vb:
                                union += 1
                    score = inter / union if union else 0.0
                    if score > best[0]:
                        best = (score, ch)
        result.append((best[1], round(best[0], 3)))
    return result


def _alpha_rows(tpl):
    if tpl.mode == "L":
        px = tpl.load()
        w, h = tpl.size
        return [[px[x, y] for x in range(w)] for y in range(h)]
    if tpl.mode == "LA":
        px = tpl.load()
        w, h = tpl.size
        return [[px[x, y][1] for x in range(w)] for y in range(h)]
    w, h = tpl.size
    px = tpl.load()
    return [[px[x, y][0] for x in range(w)] for y in range(h)]


def main():
    args = sys.argv[1:]
    png = args[0]
    font_path = None
    if "--font" in args:
        font_path = args[args.index("--font") + 1]
    if not font_path or not os.path.exists(font_path):
        font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_input", "DejaVuSans.ttf")
    if not os.path.exists(font_path):
        font_path = fetch_font()
    res = solve(png, font_path)
    print("[solution]", res)
    print("[text]", "".join(c for c, _ in res))


if __name__ == "__main__":
    main()
