# -*- coding: utf-8 -*-
"""右半区亮 rim 轮廓填充面积：大球 = 闭合亮环（菲涅尔 rim）围出的大圆盘。"""
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
    bright = (roi[:, :, 2] > 180).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = []
    for c in cnts:
        fa = cv2.contourArea(c)  # 填充面积
        per = cv2.arcLength(c, True)
        circ = 4 * np.pi * fa / max(1.0, per * per)
        if fa > 3000:
            m = cv2.moments(c)
            cx = x0 + m["m10"] / max(1e-6, m["m00"])
            cy = y0 + m["m01"] / max(1e-6, m["m00"])
            best.append((round(fa), round(circ, 2), round(cx), round(cy)))
    best.sort(reverse=True)
    print(os.path.basename(f), "candidates=", best[:4])
