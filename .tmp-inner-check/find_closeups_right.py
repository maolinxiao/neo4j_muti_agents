# -*- coding: utf-8 -*-
"""右半区（场景可见区）主导亮斑统计：定位特写帧。"""
import glob
import os

import cv2
import numpy as np

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
for f in sorted(glob.glob(os.path.join(SHOTS, "frame_*.png"))):
    img = cv2.imread(f)
    img = cv2.resize(img, (960, 540))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    x0 = int(960 * 0.52)
    y0, y1 = int(540 * 0.06), int(540 * 0.94)
    roi = hsv[y0:y1, x0:]
    bright = (roi[:, :, 2] > 175).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, cents = cv2.connectedComponentsWithStats(bright, 8)
    areas = [(int(stats[i, cv2.CC_STAT_AREA]), i) for i in range(1, n)]
    areas.sort(reverse=True)
    roi_area = (y1 - y0) * (960 - x0)
    top = []
    for area, i in areas[:4]:
        mask = (labels == i).astype(np.uint8)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)
        per = cv2.arcLength(c, True)
        circ = 4 * np.pi * cv2.contourArea(c) / max(1.0, per * per)
        top.append((area, round(circ, 2), int(x0 + cents[i][0]), int(y0 + cents[i][1])))
    print(
        os.path.basename(f),
        "roi_bright%=", round(bright.sum() / roi_area * 100, 1),
        "top4=", top,
    )
