# -*- coding: utf-8 -*-
"""特写帧验收对比：
A. 连线密度（球心近端直线段）：旧版（有 innerLinks） vs 新版（已去连线）
B. 卫星分布：数量 / 最小成对距离 / 角度间隙均匀性（新版）
C. 标签面板重叠（新版）
"""
import glob
import json
import math
import os

import cv2
import numpy as np

OLD_SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-login-check\shots"
NEW_SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"

NEW_CLOSEUPS = ["frame_00.png", "frame_01.png", "frame_03.png", "frame_05.png", "frame_06.png",
                "frame_07.png", "frame_08.png", "frame_09.png", "frame_11.png", "frame_16.png",
                "frame_17.png", "frame_19.png", "frame_21.png", "frame_23.png", "frame_25.png",
                "frame_27.png"]
OLD_CLOSEUPS = ["home_000s.png", "home_001s.png", "home_002s.png", "home_005s.png", "home_006s.png",
                "home_007s.png", "home_010s.png", "home_011s.png", "home_012s.png", "home_014s.png",
                "home_018s.png", "home_020s.png", "home_026s.png", "home_028s.png", "home_030s.png",
                "home_034s.png", "home_036s.png", "home_040s.png", "home_042s.png", "home_062s.png"]


def load_frame(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    scale = 960.0 / w
    return cv2.resize(img, (960, int(h * scale))), scale


def right_roi(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    x0 = int(960 * 0.52)
    y0, y1 = int(img.shape[0] * 0.06), int(img.shape[0] * 0.94)
    return hsv[y0:y1, x0:], x0, y0


def find_ball(roi):
    mask = ((roi[:, :, 1] > 70) & (roi[:, :, 2] > 110)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cnts:
        fa = cv2.contourArea(c)
        if fa < 2500:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(c)
        if best is None or fa > best[0]:
            best = (fa, cx, cy, r)
    return best


def lines_near_ball(roi_gray, bcx, bcy, br):
    edges = cv2.Canny(roi_gray, 60, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=45, maxLineGap=10)
    if lines is None:
        return 0, 0
    n_near, n_far = 0, 0
    for l in lines:
        xa, ya, xb, yb = l[0]
        length = math.hypot(xb - xa, yb - ya)
        # 线段到球心距离
        vx, vy = xb - xa, yb - ya
        wx, wy = bcx - xa, bcy - ya
        denom = vx * vx + vy * vy
        t = max(0, min(1, (wx * vx + wy * vy) / max(1e-6, denom)))
        px, py = xa + t * vx, ya + t * vy
        d = math.hypot(bcx - px, bcy - py)
        if length >= 0.25 * br:
            if d < 0.62 * br:
                n_near += 1
            elif d < 1.3 * br:
                n_far += 1
    return n_near, n_far


def sats_around(roi, bcx, bcy, br, x0, y0):
    hsv = roi
    mask = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 110)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # 扣除大球盘面
    mask2 = mask.copy()
    cv2.circle(mask2, (int(bcx), int(bcy)), max(1, int(br * 0.82)), 0, -1)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(mask2, 8)
    sats = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if 25 <= area <= 1400:
            cx, cy = cents[i]
            d = math.hypot(cx - bcx, cy - bcy)
            if 0.85 * br <= d <= 2.3 * br:
                sats.append((cx, cy, area))
    return sats


def label_panels(img, bcx, bcy, br):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    dark = (hsv[:, :, 2] < 70).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cv2.circle(dark, (int(bcx), int(bcy)), max(1, int(br * 0.7)), 0, -1)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    panels = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        pw, ph = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if 200 <= area <= 6000 and pw > 15 and ph > 8 and pw / ph < 8:
            panels.append((stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], pw, ph))
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
                if inter / max(1, uni) > 0.08:
                    overlaps += 1
    return len(panels), overlaps


def analyze_set(shots, closeups, label):
    print(f"===== {label} =====")
    stats = {"near": [], "far": [], "sat_counts": [], "sat_min_dists": [],
             "gap_var": [], "panels": [], "overlaps": []}
    for fn in closeups:
        p = os.path.join(shots, fn)
        if not os.path.exists(p):
            continue
        img, scale = load_frame(p)
        roi, x0, y0 = right_roi(img)
        ball = find_ball(roi)
        if not ball:
            print(fn, "no ball, skip")
            continue
        fa, cx, cy, r = ball
        bcx, bcy = x0 + cx, y0 + cy
        gray_roi = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[y0:y0 + roi.shape[0], x0:]
        near, far = lines_near_ball(gray_roi, cx, cy, r)
        stats["near"].append(near)
        stats["far"].append(far)
        sats = sats_around(roi, cx, cy, r, x0, y0)
        stats["sat_counts"].append(len(sats))
        min_d = None
        gaps = []
        if len(sats) >= 2:
            for i in range(len(sats)):
                for j in range(i + 1, len(sats)):
                    d = math.hypot(sats[i][0] - sats[j][0], sats[i][1] - sats[j][1])
                    min_d = d if min_d is None else min(min_d, d)
            angles = sorted(math.atan2(s[1] - cy, s[0] - cx) for s in sats)
            ang_gaps = [(angles[(k + 1) % len(angles)] - angles[k]) % (2 * math.pi) for k in range(len(angles))]
            gaps = ang_gaps
        if min_d is not None:
            stats["sat_min_dists"].append(round(min_d / r, 2))
        if gaps:
            g = np.array(gaps)
            stats["gap_var"].append(round(float(np.std(g) / (2 * math.pi / len(gaps))), 2) if len(gaps) > 1 else 0)
        panels, overlaps = label_panels(img, bcx, bcy, r)
        stats["panels"].append(panels)
        stats["overlaps"].append(overlaps)
        print(f"{fn}: r={round(r)} near_lines={near} far_lines={far} sats={len(sats)} "
              f"min_d/r={stats['sat_min_dists'][-1] if stats['sat_min_dists'] else '-'} "
              f"gap_var={stats['gap_var'][-1] if stats['gap_var'] else '-'} "
              f"panels={panels} overlaps={overlaps}")
    print(f"-- {label} 汇总 --")
    for k in ("near", "far"):
        v = stats[k]
        print(f"  {k}: mean={round(np.mean(v),1) if v else '-'} max={max(v) if v else '-'}")
    if stats["sat_min_dists"]:
        print(f"  sat_min_dists/r: mean={round(np.mean(stats['sat_min_dists']),2)} min={round(min(stats['sat_min_dists']),2)}")
    if stats["gap_var"]:
        print(f"  gap_var(归一化): mean={round(np.mean(stats['gap_var']),2)}")
    print(f"  panels: mean={round(np.mean(stats['panels']),1)}  重叠计数总和={sum(stats['overlaps'])}")
    return stats


new_stats = analyze_set(NEW_SHOTS, NEW_CLOSEUPS, "新版（去连线+三环）")
old_stats = analyze_set(OLD_SHOTS, OLD_CLOSEUPS, "旧版（含 innerLinks 基线）")
with open(r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\compare_stats.json", "w", encoding="utf-8") as f:
    json.dump({"new": {k: (v if not isinstance(v, list) or all(isinstance(x, (int, float)) for x in v) else v) for k, v in new_stats.items()},
               "old": {k: (v if not isinstance(v, list) or all(isinstance(x, (int, float)) for x in v) else v) for k, v in old_stats.items()}},
              f, ensure_ascii=False, indent=1, default=str)
