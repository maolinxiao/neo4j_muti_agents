# -*- coding: utf-8 -*-
"""旧版 home_*.png 大球时间线：找出旧特写帧作基线。"""
import glob
import os

import cv2
import numpy as np

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-login-check\shots"
for f in sorted(glob.glob(os.path.join(SHOTS, "home_*.png"))):
    img = cv2.imread(f)
    h, w = img.shape[:2]
    scale = 960.0 / w
    img = cv2.resize(img, (960, int(h * scale)))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    x0 = int(960 * 0.52)
    y0, y1 = int(img.shape[0] * 0.06), int(img.shape[0] * 0.94)
    roi = hsv[y0:y1, x0:]
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
    if best:
        fa, cx, cy, r = best
        print(os.path.basename(f), "ball r=", round(r), "area=", round(fa), "center=(", round(x0 + cx), ",", round(y0 + cy), ")")
    else:
        print(os.path.basename(f), "no ball")
