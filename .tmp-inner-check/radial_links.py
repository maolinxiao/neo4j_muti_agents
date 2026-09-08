# -*- coding: utf-8 -*-
"""径向连线检测：旧版 innerLinks = 球心↔卫星径向管状线；cage 线框 = 球面切弦。
判定：线段一端距球心 <0.45r 且另一端距球心 >1.05r 且长度 >0.35r。"""
import glob
import math
import os

import cv2
import numpy as np

OLD_SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-login-check\shots"
NEW_SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
OLD_CLOSEUPS = ["home_000s.png", "home_001s.png", "home_002s.png", "home_005s.png", "home_006s.png",
                "home_007s.png", "home_010s.png", "home_011s.png", "home_012s.png", "home_014s.png",
                "home_018s.png", "home_020s.png", "home_026s.png", "home_028s.png", "home_030s.png",
                "home_034s.png", "home_036s.png", "home_040s.png", "home_042s.png", "home_062s.png"]
NEW_CLOSEUPS = ["frame_00.png", "frame_01.png", "frame_03.png", "frame_05.png", "frame_06.png",
                "frame_07.png", "frame_08.png", "frame_09.png", "frame_11.png", "frame_16.png",
                "frame_17.png", "frame_19.png", "frame_21.png", "frame_23.png", "frame_25.png",
                "frame_27.png"]


def radial_links(shots, closeups, label):
    counts = []
    print(f"===== {label} =====")
    for fn in closeups:
        p = os.path.join(shots, fn)
        if not os.path.exists(p):
            continue
        img = cv2.imread(p)
        h, w = img.shape[:2]
        img = cv2.resize(img, (960, int(h * (960.0 / w))))
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        x0 = int(960 * 0.52)
        y0, y1 = int(img.shape[0] * 0.06), int(img.shape[0] * 0.94)
        roi = hsv[y0:y1, x0:]
        mask = ((roi[:, :, 1] > 70) & (roi[:, :, 2] > 110)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        ball = None
        for c in cnts:
            fa = cv2.contourArea(c)
            if fa < 2500:
                continue
            (cx, cy), r = cv2.minEnclosingCircle(c)
            if ball is None or fa > ball[0]:
                ball = (fa, cx, cy, r)
        if not ball:
            continue
        fa, cx, cy, r = ball
        gray_roi = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[y0:y0 + roi.shape[0], x0:]
        edges = cv2.Canny(gray_roi, 60, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=45, maxLineGap=10)
        n_rad = 0
        if lines is not None:
            for l in lines:
                xa, ya, xb, yb = l[0]
                da = math.hypot(xa - cx, ya - cy)
                db = math.hypot(xb - cx, yb - cy)
                length = math.hypot(xb - xa, yb - ya)
                ends = sorted((da, db))
                if length >= 0.35 * r and ends[0] < 0.45 * r and ends[1] > 1.05 * r:
                    n_rad += 1
        counts.append(n_rad)
        print(f"{fn}: r={round(r)} radial_segments={n_rad}")
    arr = np.array(counts) if counts else np.array([0])
    print(f"-- {label}: radial mean={round(arr.mean(),1)} max={arr.max()} total={arr.sum()}")
    return counts


old_c = radial_links(OLD_SHOTS, OLD_CLOSEUPS, "旧版（含 innerLinks）")
new_c = radial_links(NEW_SHOTS, NEW_CLOSEUPS, "新版（去连线）")
