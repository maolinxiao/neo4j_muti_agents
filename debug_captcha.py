# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solve_captcha import load_mask, extract_char_boxes, crop_char, render_template, CHARSET
from PIL import ImageFont, Image


def alpha_rows(tpl):
    px = tpl.load()
    w, h = tpl.size
    return [[px[x, y] for x in range(w)] for y in range(h)]


def iou(a, b):
    inter = union = 0
    ha, wa = len(a), len(a[0])
    hb, wb = len(b), len(b[0])
    y0 = -min(0, hb - ha)
    for y in range(ha):
        for x in range(wa):
            va = a[y][x]
            vb = 0
            by = y + y0
            if 0 <= by < hb and 0 <= x < wb:
                vb = b[by][x]
            if va and vb:
                inter += 1
                union += 1
            elif va or vb:
                union += 1
    return inter / union if union else 0.0


path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp-rnd-t3", "captcha.png")
mask = load_mask(path)
h = len(mask)
w = len(mask[0])
segs = extract_char_boxes(mask, w, h)
print("segs", segs)
font = ImageFont.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_input", "DejaVuSans.ttf"), 28)

for i, (x0, x1) in enumerate(segs):
    cm = crop_char(mask, w, h, x0, x1)
    bh = len(cm)
    bw = len(cm[0])
    best = []
    for ch in CHARSET:
        tpl = render_template(font, ch)
        if tpl is None:
            continue
        tm = [[1 if p > 127 else 0 for p in row] for row in alpha_rows(tpl)]
        if len(tm) == 0 or len(tm[0]) == 0:
            continue
        # 直接让模板 bbox 与裁剪同尺寸（先缩放到相同高，比例可稍差）
        tw = len(tm[0])
        th = len(tm)
        scale = bh / th
        nw = max(1, int(round(tw * scale)))
        tpl2 = tpl.resize((nw, bh), Image.LANCZOS)
        tm2 = [[1 if p > 127 else 0 for p in row] for row in alpha_rows(tpl2)]
        # 水平对中比较
        off = (bw - nw) // 2
        a = [[0] * bw for _ in range(bh)]
        for y in range(bh):
            for x in range(nw):
                tx = x + off
                if 0 <= tx < bw:
                    a[y][tx] = tm2[y][x]
        s = iou(cm, a)
        best.append((round(s, 3), ch))
    best.sort(reverse=True)
    print(f"seg{i} bw={bw} bh={bh} top5={best[:5]}")
