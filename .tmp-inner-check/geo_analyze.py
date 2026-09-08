# -*- coding: utf-8 -*-
"""特写帧几何验收（cv2）：
- 大球定位（最大亮连通块）
- 卫星 blob 检测：数量、成对最小距离、均匀性（最近邻统计）
- 环带聚类：卫星到大球中心的距离是否聚成多个环带（k=1/2/3 比较）
- 连线密度：HoughLinesP 长线段（ROI=大球附近）
- 标签面板：暗面板 blob 检测 + 两两重叠 IoU
"""
import glob
import json
import os
from collections import deque

import cv2
import numpy as np

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
CLOSEUP_FRAMES = ["frame_03.png", "frame_05.png", "frame_07.png", "frame_10.png",
                  "frame_12.png", "frame_15.png", "frame_17.png", "frame_19.png",
                  "frame_22.png", "frame_01.png"]


def largest_cc(mask):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return None, 0
    best = 1
    for i in range(2, n):
        if stats[i, cv2.CC_STAT_AREA] > stats[best, cv2.CC_STAT_AREA]:
            best = i
    cx = stats[best, cv2.CC_STAT_LEFT] + stats[best, cv2.CC_STAT_WIDTH] / 2
    cy = stats[best, cv2.CC_STAT_TOP] + stats[best, cv2.CC_STAT_HEIGHT] / 2
    r = max(stats[best, cv2.CC_STAT_WIDTH], stats[best, cv2.CC_STAT_HEIGHT]) / 2
    return (cx, cy, r), stats[best, cv2.CC_STAT_AREA]


def analyze_frame(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    scale = 960.0 / w
    img = cv2.resize(img, (960, int(h * scale)))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 亮像素（V>190）：球体 + 卫星 + 辉光
    bright = (hsv[:, :, 2] > 190).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ball, ball_area = largest_cc(bright)
    if ball is None:
        return None
    bcx, bcy, br = ball
    # ROI：大球周围 2.2 倍半径
    roi_r = int(br * 2.4)
    x0, y0 = max(0, int(bcx - roi_r)), max(0, int(bcy - roi_r))
    x1, y1 = min(960, int(bcx + roi_r)), min(540, int(bcy + roi_r))
    roi_bright = bright[y0:y1, x0:x1].copy()
    # 去掉大球本体（中心 0.9r 内）
    mask_ball = np.zeros_like(roi_bright)
    ccy, ccx = int(bcy - y0), int(bcx - x0)
    cv2.circle(mask_ball, (ccx, ccy), max(1, int(br * 0.92)), 1, -1)
    roi_sat = (roi_bright.astype(np.int16) - mask_ball.astype(np.int16)).clip(0, 1).astype(np.uint8)

    n, labels, stats, cents = cv2.connectedComponentsWithStats(roi_sat, 8)
    sats = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if 8 <= area <= 600:
            cx = x0 + cents[i][0]
            cy = y0 + cents[i][1]
            sats.append((cx, cy, area))
    # 卫星间最小距离（排除同 blob 重复）
    min_d = None
    dists = []
    for i in range(len(sats)):
        for j in range(i + 1, len(sats)):
            d = np.hypot(sats[i][0] - sats[j][0], sats[i][1] - sats[j][1])
            dists.append(d)
            min_d = d if min_d is None else min(min_d, d)
    # 卫星到大球中心距离
    rads = sorted(np.hypot(s[0] - bcx, s[1] - bcy) for s in sats)

    # 环带聚类：k 从 1 到 3 的 SSE 下降比例
    rads_arr = np.array(rads, dtype=np.float64).reshape(-1, 1) if rads else None
    sse = {}
    if rads_arr is not None and len(rads_arr) >= 3:
        for k in (1, 2, 3):
            if len(rads_arr) < k:
                continue
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.1)
            compact, label, center = cv2.kmeans(rads_arr, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
            sse[k] = float(compact)
    sse_ratio = (sse.get(3, 0) / sse.get(1, 1)) if sse else None

    # 连线检测：ROI 内长直线段（Canny + HoughLinesP）
    roi_gray = gray[y0:y1, x0:x1]
    edges = cv2.Canny(roi_gray, 40, 120)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=30, maxLineGap=6)
    long_lines = 0
    if lines is not None:
        for l in lines:
            xa, ya, xb, yb = l[0]
            if np.hypot(xb - xa, yb - ya) >= 30:
                long_lines += 1
    line_density = long_lines / max(1, (x1 - x0) * (y1 - y0) / 10000)

    # 标签面板：暗面板（V<70, 面积 300~6000）
    dark = (hsv[:, :, 2] < 70).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    nd, dl, dst, _ = cv2.connectedComponentsWithStats(dark, 8)
    panels = []
    for i in range(1, nd):
        area = dst[i, cv2.CC_STAT_AREA]
        pw, ph = dst[i, cv2.CC_STAT_WIDTH], dst[i, cv2.CC_STAT_HEIGHT]
        if 300 <= area <= 6000 and pw > 20 and ph > 8 and pw / ph < 8:
            panels.append((dst[i, cv2.CC_STAT_LEFT], dst[i, cv2.CC_STAT_TOP], pw, ph))
    overlaps = 0
    for i in range(len(panels)):
        for j in range(i + 1, len(panels)):
            ax1, ay1, aw, ah = panels[i]
            bx1, by1, bw, bh = panels[j]
            ix = max(0, min(ax1 + aw, bx1 + bw) - max(ax1, bx1))
            iy = max(0, min(ay1 + ah, by1 + bh) - max(ay1, by1))
            inter = ix * iy
            if inter > 0:
                uni = aw * ah + bw * bh - inter
                iou = inter / max(1, uni)
                if iou > 0.08:
                    overlaps += 1
    return {
        "ball": [round(bcx, 1), round(bcy, 1), round(br, 1), int(ball_area)],
        "sats": [(round(s[0], 1), round(s[1], 1), s[2]) for s in sats],
        "sat_min_dist": round(min_d, 1) if min_d is not None else None,
        "sat_radii": [round(r, 1) for r in rads],
        "kmeans_sse_ratio_3v1": round(sse_ratio, 3) if sse_ratio is not None else None,
        "long_lines": long_lines,
        "line_density": round(line_density, 3),
        "label_panels": len(panels),
        "label_overlaps": overlaps,
    }


out = {}
for fn in CLOSEUP_FRAMES:
    p = os.path.join(SHOTS, fn)
    if not os.path.exists(p):
        continue
    r = analyze_frame(p)
    out[fn] = r
    if r:
        print(fn, json.dumps(r, ensure_ascii=False))
    else:
        print(fn, "NO BALL FOUND")
with open(os.path.join(SHOTS, "..", "geo_analysis.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved geo_analysis.json")
