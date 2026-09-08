# -*- coding: utf-8 -*-
"""全帧大球检测（饱和+中亮掩码）：输出球心/半径时间线，验证特写周期。"""
import glob
import os

import cv2
import numpy as np

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
rows = []
for f in sorted(glob.glob(os.path.join(SHOTS, "frame_*.png"))):
    img = cv2.imread(f)
    img = cv2.resize(img, (960, 540))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    x0 = int(960 * 0.52)
    y0, y1 = int(540 * 0.06), int(540 * 0.94)
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
        rows.append((os.path.basename(f), round(fa), round(x0 + cx), round(y0 + cy), round(r)))
        print(os.path.basename(f), "ball fill_area=", round(fa), "center=(", round(x0 + cx), ",", round(y0 + cy), ") radius=", round(r))
    else:
        rows.append((os.path.basename(f), 0, 0, 0, 0))
        print(os.path.basename(f), "no ball")
