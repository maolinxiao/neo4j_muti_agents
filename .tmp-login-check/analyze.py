"""临时验收脚本：截图像素级指标（白斑/清晰度/色彩结构/帧间变化）。"""
import glob
import os
import re

import numpy as np
from PIL import Image

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-login-check\shots"


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def largest_blob(mask):
    H, W = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best = 0
    for y in range(H):
        for x in range(W):
            if mask[y, x] and not seen[y, x]:
                seen[y, x] = True
                stack = [(y, x)]
                cnt = 0
                while stack:
                    cy, cx = stack.pop()
                    cnt += 1
                    if cy > 0 and mask[cy - 1, cx] and not seen[cy - 1, cx]:
                        seen[cy - 1, cx] = True; stack.append((cy - 1, cx))
                    if cy < H - 1 and mask[cy + 1, cx] and not seen[cy + 1, cx]:
                        seen[cy + 1, cx] = True; stack.append((cy + 1, cx))
                    if cx > 0 and mask[cy, cx - 1] and not seen[cy, cx - 1]:
                        seen[cy, cx - 1] = True; stack.append((cy, cx - 1))
                    if cx < W - 1 and mask[cy, cx + 1] and not seen[cy, cx + 1]:
                        seen[cy, cx + 1] = True; stack.append((cy, cx + 1))
                best = max(best, cnt)
    return best


def metrics(arr, hero_h=700):
    h = arr.shape[0]
    hero = arr[:min(hero_h, h)]
    r, g, b = hero[:, :, 0], hero[:, :, 1], hero[:, :, 2]
    mn = np.minimum(np.minimum(r, g), b)
    white = mn >= 248
    white_ratio = float(white.mean())
    mask = white[::3, ::3]
    blob = largest_blob(mask)
    blob_ratio = blob / float(mask.size)
    gray = (0.299 * r + 0.587 * g + 0.114 * b)
    # Laplacian variance (清晰度/边缘能量)
    lap = (-4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1]
           + gray[1:-1, :-2] + gray[1:-1, 2:])
    lap_var = float(lap.var())
    # 色彩结构：饱和且亮的像素的色相聚类数（节点彩色球/标签应有多个色相簇）
    mx = np.maximum(np.maximum(r, g), b)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    v = mx / 255.0
    sat_bright = (s > 0.35) & (v > 0.45)
    hue = np.zeros_like(r)
    hsv_h = None
    if sat_bright.any():
        rr, gg, bb = r / 255.0, g / 255.0, b / 255.0
        hue = np.arctan2(np.sqrt(3.0) * (gg - bb), 2 * rr - gg - bb)  # -pi..pi
        hh = (hue[sat_bright] + np.pi) / (2 * np.pi) * 12
        hist = np.histogram(hh, bins=12, range=(0, 12))[0]
        hsv_h = int((hist > sat_bright.sum() * 0.02).sum())
    bright = float((v > 0.6).mean())
    return white_ratio, blob_ratio, lap_var, hsv_h, bright, float(s.mean())


def main():
    files = sorted(glob.glob(os.path.join(SHOTS, "home_[0-9]*s.png")),
                   key=lambda p: int(re.search(r"home_(\d+)s", p).group(1)))
    prev = None
    rows = []
    for p in files:
        arr = load(p)
        wr, br, lv, hh, bright, ms = metrics(arr)
        motion = 0.0
        if prev is not None:
            motion = float(np.abs(arr[:700] - prev[:700]).mean())
        prev = arr
        rows.append((os.path.basename(p), wr, br, lv, hh, bright, motion))
    print(f"{'frame':<16}{'white%':>8}{'blob%':>8}{'lapVar':>10}{'hueCl':>7}{'bright%':>8}{'motion':>8}")
    for name, wr, br, lv, hh, bright, motion in rows:
        print(f"{name:<16}{wr*100:>7.2f}%{br*100:>7.2f}%{lv:>10.0f}{hh if hh is not None else '-':>7}{bright*100:>7.1f}%{motion:>8.2f}")
    # 汇总判定
    wr_max = max(r[1] for r in rows)
    br_max = max(r[2] for r in rows)
    lv_min = min(r[3] for r in rows)
    motions = [r[6] for r in rows]
    print("---summary---")
    print(f"max white ratio = {wr_max*100:.2f}%  (过曝白斑警戒线 12%)")
    print(f"max white blob  = {br_max*100:.2f}%  (警戒线 8%)")
    print(f"min lap var     = {lv_min:.0f}")
    print(f"motion range    = {min(motions):.2f} .. {max(motions):.2f} (场景持续动画应 >1)")
    ok = wr_max < 0.12 and br_max < 0.08 and lv_min > 15 and max(motions) > 1.0
    print("PIXEL_CHECK:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
